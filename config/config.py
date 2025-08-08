import os
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [407808584]  # Telegram ID администраторов
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Feedback"  # Название листа в таблице
BANNED_USERS = set()  # Множество забаненных пользователей
MAINTENANCE_MODE = False  # Флаг режима обслуживания

