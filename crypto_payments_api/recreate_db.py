import asyncio
from db.session import engine
from models import Base


async def recreate_db():
    async with engine.begin() as conn:
        # Сбрасываем (удаляем) все таблицы
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Создаём таблицы заново
    await engine.dispose()


async def main():
    await recreate_db()


if __name__ == '__main__':
    asyncio.run(main())
