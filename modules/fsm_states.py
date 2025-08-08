from aiogram.fsm.state import StatesGroup, State


# Состояния FSM
class FeedbackStates(StatesGroup):
    AUTHENTICATION = State()
    MAIN_MENU = State()
    COMPANY_INPUT = State()
    FEEDBACK_INPUT = State()
    CONFIRMATION = State()
    EDIT_FEEDBACK = State()
    EDIT_FEEDBACK_TEXT = State()
    GO_BACK = State()