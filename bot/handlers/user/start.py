import logging
from aiogram import types
from aiogram.filters import Command
from sqlalchemy import select, update
from database.session import async_session
from database.models import User, MirrorBot
from keyboards.user.reply.main_menu_kb import get_main_menu_kb
from middlewares.mirror_active import check_mirror_token

logger = logging.getLogger(__name__)


def register_start_handlers(router) -> None:
    @router.message(Command("start"))
    async def start_handler(message: types.Message):
        parts = message.text.split()
        referrer_tg_id = None
        if len(parts) > 1:
            try:
                referrer_tg_id = int(parts[1])
            except ValueError:
                logger.error("Invalid referral parameter: not an integer.")

        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
            user = result.scalar_one_or_none()

            if user:
                users_mirror_bots_result = await session.execute(
                    select(MirrorBot).where(MirrorBot.owner_id == user.id, MirrorBot.active == True))
                users_mirror_bots = users_mirror_bots_result.scalars().all()
                if users_mirror_bots:
                    valid_found = False
                    for mirror_bot in users_mirror_bots:
                        if await check_mirror_token(mirror_bot.token):
                            valid_found = True
                            break
                        else:
                            await session.execute(
                                update(MirrorBot)
                                .where(MirrorBot.id == mirror_bot.id)
                                .values(active=False)
                            )
                    if valid_found:
                        user.mirror_created = True
                        await session.commit()

            if not user:
                referrer_id = None
                if referrer_tg_id:
                    result_ref = await session.execute(select(User).where(User.tg_id == referrer_tg_id))
                    referrer = result_ref.scalar_one_or_none()
                    if referrer:
                        referrer_id = referrer.id
                new_user = User(
                    tg_id=message.from_user.id,
                    username=message.from_user.username,
                    mirror_created=False,
                    referrer_id=referrer_id
                )
                session.add(new_user)
                await session.commit()

        start_text = (
            "Welcome!"
        )

        main_menu = get_main_menu_kb()
        await message.answer(text=start_text, reply_markup=main_menu, parse_mode='HTML')
