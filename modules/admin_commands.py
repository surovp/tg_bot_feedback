import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from config.config import BOT_TOKEN, ADMIN_IDS


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
BANNED_USERS = set()  # Множество забаненных пользователей
MAINTENANCE_MODE = False  # Флаг режима обслуживания


# 1. Бан пользователя
@dp.message(Command("ban"))
async def ban_user(message: types.Message):
    """Вечный бан пользователей"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    try:
        user_id = int(message.text.split()[1])  # /ban 123456789
        BANNED_USERS.add(user_id)
        await message.answer(f"✅ Пользователь {user_id} заблокирован навсегда")
        await notify_admins(f"🚨 Пользователь {user_id} заблокирован админом {message.from_user.id}")
    except (IndexError, ValueError):
        await message.answer("ℹ️ Использование: /ban [user_id]")


# 2. Разбан пользователя
@dp.message(Command("unban"))
async def unban_user(message: types.Message):
    """Разбан пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    try:
        user_id = int(message.text.split()[1])  # /unban 123456789
        if user_id in BANNED_USERS:
            BANNED_USERS.remove(user_id)
            await message.answer(f"✅ Пользователь {user_id} разблокирован")
            await notify_admins(f"🔓 Пользователь {user_id} разблокирован админом {message.from_user.id}")
        else:
            await message.answer(f"ℹ️ Пользователь {user_id} не был заблокирован")
    except (IndexError, ValueError):
        await message.answer("ℹ️ Использование: /unban [user_id]")


# 3. Просмотр черного списка
@dp.message(Command("blacklist"))
async def show_blacklist(message: types.Message):
    """Показать список забаненных пользователей"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    if not BANNED_USERS:
        await message.answer("📭 Список забаненных пользователей пуст")
        return

    # Создаем интерактивный список с кнопками
    builder = InlineKeyboardBuilder()
    for user_id in sorted(BANNED_USERS):
        builder.button(
            text=f"Разбанить {user_id}",
            callback_data=f"unban_{user_id}"
        )
    builder.adjust(1)  # По одной кнопке в строке

    banned_list = "\n".join([f"🔹 {user_id}" for user_id in sorted(BANNED_USERS)])
    await message.answer(
        f"🚫 Список забаненных пользователей (всего {len(BANNED_USERS)}):\n{banned_list}",
        reply_markup=builder.as_markup()
    )


# 4. Режим обслуживания
@dp.message(Command("maintenance"))
async def toggle_maintenance(message: types.Message):
    """Включение/выключение режима обслуживания"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    global MAINTENANCE_MODE
    MAINTENANCE_MODE = not MAINTENANCE_MODE

    status = "включен" if MAINTENANCE_MODE else "выключен"
    await message.answer(f"✅ Режим обслуживания {status}")
    await notify_admins(f"🔧 Режим обслуживания {status} админом {message.from_user.id}")


# 5. Очистка очереди
@dp.message(Command("flush_queue"))
async def flush_queue(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return

    try:
        # Новый способ сброса состояния в aiogram 3.x
        await dp.emit_startup()
        await message.answer("✅ Состояние бота сброшено")
        await notify_admins(f"🔄 Очередь команд сброшена админом {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при сбросе состояния: {e}")
        await message.answer("❌ Не удалось сбросить состояние")


# Обработчик кнопок разбана
@dp.callback_query(F.data.startswith("unban_"))
async def unban_callback(callback: CallbackQuery):
    """Обработка кнопки разбана из черного списка"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав для этого действия")
        return

    user_id = int(callback.data.split("_")[1])
    if user_id in BANNED_USERS:
        BANNED_USERS.remove(user_id)
        await callback.message.edit_text(
            f"✅ Пользователь {user_id} разблокирован\n" +
            callback.message.text,
            reply_markup=None
        )
        await callback.answer(f"Пользователь {user_id} разблокирован")
        await notify_admins(f"🔓 Пользователь {user_id} разблокирован через черный список")
    else:
        await callback.answer("ℹ️ Пользователь уже разблокирован")


# Вспомогательная функция
async def notify_admins(text: str):
    """Уведомление всех администраторов"""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")


class SecurityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data):
        # Всегда пропускаем служебные сообщения и команду start
        if not isinstance(event, types.Message) or event.text.startswith('/start'):
            return await handler(event, data)

        user_id = event.from_user.id

        # Проверка бана
        if user_id in BANNED_USERS:
            await event.answer("🚫 Ваш аккаунт заблокирован")
            return

        # Проверка режима обслуживания
        if MAINTENANCE_MODE and user_id not in ADMIN_IDS:
            await event.answer("🔧 Бот на техническом обслуживании")
            return

        return await handler(event, data)