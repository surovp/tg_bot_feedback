import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import Command
from datetime import datetime
from config.config import BOT_TOKEN
from modules.fsm_states import FeedbackStates
from modules.admin_commands import ban_user, unban_user, show_blacklist, toggle_maintenance, flush_queue, \
    SecurityMiddleware
from modules.init_google_sheets import save_to_google_sheets, temp_storage

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="feedback_bot.log"
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ------------------------------------ Кнопки ------------------------------------
def get_main_menu_keyboard():
    """Создает клавиатуру главного меню"""
    builder = ReplyKeyboardBuilder()

    builder.button(text="📝 Новый фидбэк")
    builder.button(text="✏️ Редактировать фидбэк")
    builder.button(text="✅ Завершить сбор фидбэков")

    builder.adjust(1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="▼ Выберите действие ▼"
    )


@dp.message(FeedbackStates.MAIN_MENU, F.text == "📝 Новый фидбэк")
async def new_feedback(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите название компании (при желании укажите ФИО делегата):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(FeedbackStates.COMPANY_INPUT)


@dp.message(FeedbackStates.MAIN_MENU, F.text == "✏️ Редактировать фидбэк")
async def edit_feedback_start(message: types.Message, state: FSMContext):

    if not temp_storage.get(message.from_user.id):
        await message.answer("ℹ️ У вас нет сохраненных фидбеков для редактирования.")
        return

    feedbacks_list = "\n".join(
        f"{i + 1}. {fb['company_info']} - {fb['feedback_text'][:30]}..."
        for i, fb in enumerate(temp_storage[message.from_user.id]))

    builder = ReplyKeyboardBuilder()
    builder.button(text="Назад")

    await message.answer(
        f"Выберите фидбэк для редактирования:\n{feedbacks_list}\n\n"
        "Введите номер фидбека:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

    await state.set_state(FeedbackStates.EDIT_FEEDBACK)

    @dp.message(FeedbackStates.EDIT_FEEDBACK)
    async def edit_feedback_select(message: types.Message, state: FSMContext):
        try:
            feedback_num = int(message.text)
            if 1 <= feedback_num <= len(temp_storage[message.from_user.id]):
                feedback = temp_storage[message.from_user.id][feedback_num - 1]
                await state.update_data(
                    edit_feedback_num=feedback_num - 1,
                    current_feedback_text=feedback["feedback_text"]
                )

                await message.answer(
                    f"Текущий текст фидбека:\n{feedback['feedback_text']}\n\n"
                    "Введите новый текст:",
                    reply_markup=ReplyKeyboardRemove()
                )
                await state.set_state(FeedbackStates.EDIT_FEEDBACK_TEXT)
            else:
                await message.answer("⚠️ Некорректный номер фидбека. Попробуйте снова.")
        except ValueError:
            await message.answer("⚠️ Пожалуйста, введите число.")

    @dp.message(FeedbackStates.EDIT_FEEDBACK_TEXT)
    async def edit_feedback_text(message: types.Message, state: FSMContext):
        user_data = await state.get_data()
        feedback_num = user_data["edit_feedback_num"]

        # Обновляем фидбек в хранилище
        temp_storage[message.from_user.id][feedback_num]["feedback_text"] = message.text
        temp_storage[message.from_user.id][feedback_num]["timestamp"] = str(datetime.now())

        await message.answer(
            "✅ Фидбэк успешно обновлен!",
            reply_markup=get_main_menu_keyboard()
        )
        await state.set_state(FeedbackStates.MAIN_MENU)


@dp.message(FeedbackStates.MAIN_MENU, F.text == "✅ Завершить сбор фидбэков")
async def finish_feedback(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да")
    builder.button(text="Нет")

    await message.answer(
        f"Вы уверены, что хотите завершить сбор фидбэков? "
        f"(Сохранено фидбэков: {len(temp_storage.get(message.from_user.id, []))})",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(FeedbackStates.CONFIRMATION)


@dp.message(FeedbackStates.CONFIRMATION, F.text == "Да")
async def confirm_finish(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id in temp_storage and temp_storage[user_id]:
        success = await save_to_google_sheets(temp_storage[user_id])
        if success:
            await message.answer(
                f"✅ Все {len(temp_storage[user_id])} фидбэков успешно сохранены в Google Таблицу!\n"
                "Выберите дальнейшее действие:",
                reply_markup=get_main_menu_keyboard()
            )
            temp_storage[user_id] = []  # Очищаем фидбеки, но оставляем запись пользователя
        else:
            await message.answer(
                "❌ Произошла ошибка при сохранении. Ваши данные остались в памяти.\n"
                "Выберите дальнейшее действие:",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        await message.answer(
            "ℹ️ Нет данных для сохранения.\n"
            "Выберите дальнейшее действие:",
            reply_markup=get_main_menu_keyboard()
        )

    await state.set_state(FeedbackStates.MAIN_MENU)


@dp.message(FeedbackStates.CONFIRMATION, F.text == "Нет")
async def cancel_finish(message: types.Message, state: FSMContext):
    await message.answer(
        f"Продолжаем сбор фидбэков. (Сохранено в памяти: {len(temp_storage.get(message.from_user.id, []))})",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(FeedbackStates.MAIN_MENU)


@dp.message(FeedbackStates.EDIT_FEEDBACK, F.text == "Назад")
async def edit_feedback_back(message: types.Message, state: FSMContext):
    await message.answer(
        "Возвращаемся в главное меню:",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(FeedbackStates.MAIN_MENU)


# ------------------------------------ Старт ------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    temp_storage.pop(message.from_user.id, None)  # Очищаем временное хранилище

    welcome_text = (
        "👋 Добро пожаловать в бот для сбора фидбэков!\n\n"
        "📋 Инструкция:\n"
        "1. Заполните ваше ФИО\n"
        "2. Выберите 'Новый фидбэк' для начала записи\n"
        "3. Введите название компании и фидбэк\n"
        "4. Подтвердите сохранение\n\n"
        "✅ Чек-лист вопросов для фидбэка:\n"
        "- Что понравилось на мероприятии?\n"
        "- Что можно улучшить?\n"
        "- Ваши общие впечатления"
    )

    await message.answer(welcome_text)
    await message.answer("Пожалуйста, введите ваше ФИО:")
    await state.set_state(FeedbackStates.AUTHENTICATION)


@dp.message(FeedbackStates.AUTHENTICATION)
async def process_authentication(message: types.Message, state: FSMContext):
    if len(message.text.split()) < 2:
        await message.answer("Пожалуйста, введите полное ФИО (например: Иванов Иван Иванович):")
        return

    await state.update_data(lpm_name=message.text)
    temp_storage[message.from_user.id] = []  # Инициализируем хранилище для пользователя

    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(FeedbackStates.MAIN_MENU)


# ------------------------------------ Инпуты ------------------------------------
@dp.message(FeedbackStates.COMPANY_INPUT)
async def process_company(message: types.Message, state: FSMContext):
    await state.update_data(company_info=message.text)
    await message.answer("Запишите свой фидбэк:")
    await state.set_state(FeedbackStates.FEEDBACK_INPUT)


@dp.message(FeedbackStates.FEEDBACK_INPUT)
async def process_feedback(message: types.Message, state: FSMContext):
    user_data = await state.get_data()

    # Сохраняем фидбек во временное хранилище
    feedback_data = {
        "lpm_name": user_data.get("lpm_name", ""),
        "company_info": user_data.get("company_info", ""),
        "feedback_text": message.text,
        "timestamp": str(datetime.now()),
        "user_name": message.from_user.full_name,
        "user_id": message.from_user.id
    }

    temp_storage[message.from_user.id].append(feedback_data)

    await message.answer(
        f"✅ Фидбэк №{len(temp_storage[message.from_user.id])} сохранен. Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(FeedbackStates.MAIN_MENU)


async def main():
    # Сначала регистрируем обработчики
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(ban_user, Command("ban"))
    dp.message.register(unban_user, Command("unban"))
    dp.message.register(show_blacklist, Command("blacklist"))
    dp.message.register(toggle_maintenance, Command("maintenance"))
    dp.message.register(flush_queue, Command("flush_queue"))

    # Затем middleware
    dp.message.middleware(SecurityMiddleware())

    # Проверка доступности бота
    try:
        bot_info = await bot.get_me()
        logger.info(f"Бот @{bot_info.username} запущен")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
        return

    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
