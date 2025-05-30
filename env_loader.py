# env_loader.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
DB_FILE = os.getenv("DB_FILE", "olx_ads.db")
URLS_FILE = os.getenv("URLS_FILE", "tracked_urls.json")


CHAT_IDS = [int(chat_id) for chat_id in CHAT_IDS if chat_id.strip()]
ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS if admin_id.strip()]
