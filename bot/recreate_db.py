import asyncio
from database.session import engine
from database.models import Base
from sqlalchemy import text

async def recreate_db():
    async with engine.begin() as conn:
        # Drop the public schema along with all dependent objects
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        # Recreate the public schema
        await conn.execute(text("CREATE SCHEMA public"))
        # Now create tables according to your metadata
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def main():
    await recreate_db()


if __name__ == '__main__':
    asyncio.run(main())