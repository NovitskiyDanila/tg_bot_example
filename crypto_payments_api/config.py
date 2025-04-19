import os
from dotenv import load_dotenv
load_dotenv()  # Загружает переменные из файла .env

DATABASE_URL = os.getenv("DATABASE_URL")
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
USDT_CONTRACT_ADDRESS = os.getenv("USDT_CONTRACT_ADDRESS")
TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY")

