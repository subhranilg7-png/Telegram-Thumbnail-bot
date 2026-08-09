import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Only this user can add/remove admins.
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# MongoDB (stores admin list + watermark override)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "thumbnail_bot")
