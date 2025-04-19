import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api.deposit import router as deposit_router

from db.session import engine
from models import Base
from tasks import startup_monitor_pending_deposits


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код, выполняемый при запуске
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    asyncio.create_task(startup_monitor_pending_deposits())

    yield
    # Код, выполняемый при завершении работы
    await engine.dispose()

app = FastAPI(lifespan=lifespan, title="Crypto Payment API", version="1.0.0")

app.include_router(deposit_router, prefix="/api", tags=["Deposits"])


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
