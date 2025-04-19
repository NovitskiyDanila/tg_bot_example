import aiohttp
import logging
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from database.session import async_session
from database.models import User, MirrorBot
from keyboards.user.inline.create_mirror import get_create_mirror_kb

logger = logging.getLogger(__name__)


async def check_mirror_token(token: str) -> bool:
    """
    Проверяет токен через вызов метода getMe.
    Если токен валиден, возвращает True, иначе – False.
    """
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return data.get("ok", False)
    except Exception as e:
        logger.error(f"Error checking token: {e}")
        return False

class MirrorActiveMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: dict):
        # Разрешаем всегда обработку команды /start
        if event.text and event.text.startswith("/start"):
            return await handler(event, data)

        # Если пользователь находится в состоянии ожидания токена (например, MirrorCreation), пропускаем проверку
        if "state" in data:
            state: FSMContext = data["state"]
            current_state = await state.get_state()
            if current_state and current_state.startswith("MirrorCreation"):
                if isinstance(event, types.CallbackQuery) and event.data == "cancel_mirror_creation":
                    return await handler(event, data)
                if event.text and await check_mirror_token(event.text):
                    return await handler(event, data)

        # Получаем Telegram ID пользователя
        user_id = event.from_user.id

        # Проверяем, зарегистрирован ли пользователь
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == user_id))
            user: User = result.scalar_one_or_none()

        if not user:
            instruction = (
                "User not found. Please use /start command to register."
            )
            await event.answer(instruction)
            return

        if user.mirror_created is False:
            instruction = (
                "⚠️ To use the bot, you must create your own mirror.\n\n"
                "Please create your mirror bot via BotFather, then click the 'Create Mirror' button and send your bot token."
            )
            await event.answer(instruction, reply_markup=get_create_mirror_kb())
            return

        # Получаем список активных зеркальных ботов пользователя
        async with async_session() as session:
            result = await session.execute(
                select(MirrorBot).where(MirrorBot.owner_id == user.id, MirrorBot.active == True)
            )
            active_mirrors = result.scalars().all()

        if not active_mirrors:
            await session.execute(update(User).where(User.id == user.id).values(mirror_created=False))
            await session.commit()
            await session.close()
            await event.answer(
                "⚠️ You do not have any active mirror bot. Please create one.",
                reply_markup=get_create_mirror_kb()
            )
            return

        # Проверяем, есть ли хотя бы один активный бот с действительным токеном
        valid_found = False
        for mirror in active_mirrors:
            if await check_mirror_token(mirror.token):
                valid_found = True
                break
            else:
                await session.execute(
                    update(MirrorBot)
                    .where(MirrorBot.id == mirror.id)
                    .values(active=False)
                )
                await session.commit()
                await session.close()

        if not valid_found:
            # Если ни один активный бот не валиден, сбрасываем флаг и просим создать новый
            await session.execute(update(User).where(User.id == user.id).values(mirror_created=False))
            await session.commit()
            await session.close()
            await event.answer(
                "⚠️ None of your mirror bots are active. Please create a new mirror and send your token.",
                reply_markup=get_create_mirror_kb()
            )
            return

        return await handler(event, data)
