import os
import ssl


from dotenv import load_dotenv
from aiogram.types import FSInputFile

load_dotenv()  # Загружает переменные из файла .env

MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
API_URL = os.getenv("API_URL")
REDIS_URL = os.getenv("REDIS_URL")
TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY")
CRYPTO_API_KEY = os.getenv("CRYPTO_API_KEY")
PATH_TO_VIDEO = os.getenv("PATH_TO_VIDEO")
PATH_TO_CERTIFICATE = os.getenv("PATH_TO_CERTIFICATE")

PATH_TO_API_CERTIFICATE = os.getenv("PATH_TO_API_CERTIFICATE")

headers = {
    "Content-Type": "application/json",
    "access_token": CRYPTO_API_KEY
}

VIDEO = FSInputFile(PATH_TO_VIDEO)
certificate = FSInputFile(PATH_TO_CERTIFICATE)

ssl_context = ssl.create_default_context(cafile=PATH_TO_API_CERTIFICATE)



