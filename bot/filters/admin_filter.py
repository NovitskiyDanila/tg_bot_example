from aiogram.filters import BaseFilter
from aiogram import types
from sqlalchemy import select
from database.session import async_session
from database.models import User

class AdminFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
            user = result.scalar_one_or_none()
        if not user:
            return False
        return user.role == "admin"
