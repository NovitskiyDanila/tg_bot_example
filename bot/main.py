import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import MAIN_BOT_TOKEN
from database.session import engine
from database.models import Base
from handlers.user.deposit import monitor_existing_pending_deposits
from routers import create_admin_router, create_user_router

logging.basicConfig(
    level=logging.INFO,
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)

storage = MemoryStorage()
bot = Bot(token=MAIN_BOT_TOKEN)
dp = Dispatcher(storage=storage)
dp.include_routers(create_user_router(), create_admin_router())


async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await monitor_existing_pending_deposits()
    logging.info("Database tables created.")


async def main():
    try:
        await on_startup()
        logging.info("Starting main bot polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()  # если необходимо, или await engine.dispose() для асинхронного метода
        logging.info("Main bot shutdown: Bot session closed and engine disposed.")

if __name__ == "__main__":
    asyncio.run(main())
