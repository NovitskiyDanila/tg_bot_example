from aiogram.filters import BaseFilter
from aiogram import types
from sqlalchemy import select
from database.session import async_session
from database.models import User


class AdminOperatorFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
            user = result.scalar_one_or_none()
        if not user:
            return False
        # Возвращает True, если роль пользователя либо "admin", либо "operator"
        return user.role in ("admin", "operator")
