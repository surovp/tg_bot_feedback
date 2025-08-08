import gspread
import logging
from typing import Dict, List
from config.config import GOOGLE_SHEET_ID
from oauth2client.service_account import ServiceAccountCredentials

# Хранилище фидбеков в памяти (user_id: list_of_feedbacks)
temp_storage: Dict[int, List[Dict]] = {}

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="feedback_bot.log"
)
logger = logging.getLogger(__name__)


# Инициализация Google Sheets
def init_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEET_ID).worksheet("Feedback")


async def save_to_google_sheets(feedbacks: List[Dict]):
    """Функция для сохранения всех фидбеков в Google Таблицу"""
    try:
        sheet = init_google_sheet()
        rows = []
        for feedback in feedbacks:
            rows.append([
                feedback.get("lpm_name", ""),
                feedback.get("company_info", ""),
                feedback.get("feedback_text", ""),
                feedback.get("timestamp", ""),
                feedback.get("user_name", ""),
                str(feedback.get("user_id", ""))
            ])
        if rows:
            sheet.append_rows(rows)
            return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении в Google Sheets: {e}")
    return False