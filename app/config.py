import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

WB_API_TOKEN = os.getenv("WB_API_TOKEN", "")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

DB_PATH = BASE_DIR / "wb_dashboard.sqlite3"
DATABASE_URL = f"sqlite:///{DB_PATH}"

STATISTICS_API = "https://statistics-api.wildberries.ru"
FEEDBACKS_API = "https://feedbacks-api.wildberries.ru"
ADVERT_API = "https://advert-api.wildberries.ru"
