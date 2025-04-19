import logging

from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types
from sqlalchemy import select

from database.session import async_session, engine
from database.models import MirrorBot
from routers import create_admin_router, create_user_router
from cache import mirror_cache
import uvicorn

# logging.basicConfig(level=logging.INFO)

logging.basicConfig(
    level=logging.INFO,  # или DEBUG для более подробного вывода
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI()

# Кэш для хранения экземпляров Bot для зеркальных ботов
mirror_bots_cache = mirror_cache
mirror_storage = MemoryStorage()

def get_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=mirror_storage)
    dp.include_routers(create_user_router(), create_admin_router())
    return dp


@app.post("/webhook/mirror/{mirror_bot_id}")
async def mirror_webhook(mirror_bot_id: int, request: Request):
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    async with async_session() as session:
        result = await session.execute(
            select(MirrorBot).where(MirrorBot.id == mirror_bot_id)
        )
        mirror_bot = result.scalar_one_or_none()

    if not mirror_bot:
        raise HTTPException(status_code=404, detail="Mirror bot not found")

    if mirror_bot_id in mirror_bots_cache:
        bot_instance = mirror_bots_cache[mirror_bot_id]
    else:
        bot_instance = Bot(token=mirror_bot.token)
        mirror_bots_cache[mirror_bot_id] = bot_instance

    dp = get_dispatcher()
    try:
        update = types.Update.parse_obj(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid update format") from e

    await dp.feed_update(bot_instance, update)
    return JSONResponse({"ok": True})


@app.on_event("shutdown")
async def shutdown_event():
    # Закрываем клиентские сессии для всех зеркальных ботов, если они созданы
    for bot_instance in mirror_bots_cache.values():
        await bot_instance.session.close()
    # Если используется асинхронный engine, возможно, его тоже нужно закрыть:
    await engine.dispose()  # если engine имеет асинхронный метод dispose, используйте await engine.dispose()
    logging.info("Shutdown: All bot sessions closed and engine disposed.")


if __name__ == "__main__":
    uvicorn.run("main_webhook:app", host="0.0.0.0", port=8001, reload=True)
