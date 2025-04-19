import logging
from aiogram import types, F, Bot
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from database.session import async_session
from database.models import User, MirrorBot
from .create_mirror import create_mirror_callback_handler
from .personal_account import get_personal_account_info
from cache import mirror_cache
logger = logging.getLogger(__name__)

# FSM для обновления токена зеркального бота
class MirrorManagement(StatesGroup):
    waiting_for_new_token = State()


def register_my_bot_handlers(router) -> None:
    @router.callback_query(F.data == "my_bots")
    async def my_bots_menu_handler(callback: types.CallbackQuery, state: FSMContext):
        user_tg_id = callback.from_user.id
        # Получаем пользователя из БД
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == user_tg_id))
            user = result.scalar_one_or_none()
        if not user:
            await callback.message.edit_text("Пользователь не найден, отправьте /start")
            await callback.answer()
            return

        # Получаем список зеркальных ботов пользователя
        async with async_session() as session:
            result = await session.execute(
                select(MirrorBot).where(MirrorBot.owner_id == user.id, MirrorBot.active == True)
            )
            mirror_bots = result.scalars().all()

        text = (
            "🤖 <b>Create your own personal bot</b>\n"
            "ℹ️ This is just in case your main bot is deleted or unavailable, you'll have your own, working bot.\n\n"
        )
        if mirror_bots:
            text += "<b>Your bots:</b>\n"
            for mb in mirror_bots:
                text += f"• @{mb.username}\n"
        else:
            text += "You have no mirror bots yet."

        # Строим клавиатуру с помощью InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="➕ Create bot", callback_data="create_bot")
        )
        if mirror_bots:
            # Для каждого зеркального бота добавляем кнопку управления
            for mb in mirror_bots:
                builder.row(
                    types.InlineKeyboardButton(text=f"@{mb.username}", callback_data=f"manage_bot_{mb.id}")
                )
        # Кнопка Back возвращает в основное меню личного кабинета (personal account)
        builder.row(
            types.InlineKeyboardButton(text="🔙 Back", callback_data="personal_account")
        )
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data.startswith('manage_bot_'))
    async def manage_bot_handler(callback: types.CallbackQuery, state: FSMContext):
        # Извлекаем id бота из callback_data, например, "manage_bot_123"
        try:
            bot_id = int(callback.data.split("_")[-1])
        except Exception:
            logging.info(f"ERROR: {e}")
            await callback.answer("Wrong data.")
            return

        async with async_session() as session:
            result = await session.execute(select(MirrorBot).where(MirrorBot.id == bot_id))
            mirror_bot = result.scalar_one_or_none()
        if not mirror_bot:
            await callback.message.edit_text("Mirror bot not found.")
            await callback.answer()
            return

        detail_text = (
            f"🤖 <b>Bot @{mirror_bot.username}</b>\n"
            f"⚙️ <b>Token:</b> <code>{mirror_bot.token}</code>\n"
        )
        builder = InlineKeyboardBuilder()
        # Кнопка Back возвращает в меню списка зеркальных ботов (my_bots)
        builder.row(
            types.InlineKeyboardButton(text="🔙 Back", callback_data="back_to_bots"),
            types.InlineKeyboardButton(text="🗑 Delete bot", callback_data=f"delete_bot_{mirror_bot.id}")
        )

        await callback.message.edit_text(detail_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data == "back_to_bots")
    async def back_to_bots_handler(callback: types.CallbackQuery, state: FSMContext):
        # Возвращаем пользователя в меню "My bots"
        await my_bots_menu_handler(callback, state)
        await callback.answer()

    @router.callback_query(F.data.startswith('delete_bot_'))
    async def delete_bot_confirmation(callback: types.CallbackQuery):
        bot_id = int(callback.data.split("_")[-1])
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="⬅️ Back", callback_data=f"manage_bot_{bot_id}"),
            types.InlineKeyboardButton(text="✅ Confirm", callback_data=f'confirmed_delete_bot_{bot_id}')
        )
        await callback.message.edit_text("❗️ Confirm deletion of mirror bot", reply_markup=builder.as_markup())

    @router.callback_query(F.data.startswith('confirmed_delete_bot_'))
    async def delete_bot_handler(callback: types.CallbackQuery, state: FSMContext):
        try:
            bot_id = int(callback.data.split("_")[-1])
        except Exception:
            logging.info(f"ERROR: {e}")
            await callback.answer("Something went wrong.")
            return

        async with async_session() as session:
            # Полное удаление или пометка как неактивного
            result = await session.execute(
                                 select(MirrorBot)
                                 .where(MirrorBot.id == bot_id)
                                )
            bot_to_delete: Bot = result.scalar_one_or_none()

            mirror_bot: Bot = mirror_cache[bot_id]
            if mirror_bot:
                await mirror_bot.delete_webhook()
            else:
                mirror_bot = Bot(bot_to_delete.token)
                await mirror_bot.delete_webhook()
            await session.delete(bot_to_delete)
            await session.commit()


        await callback.message.edit_text("Mirror bot deleted.")
        await callback.answer()
        # Возвращаемся в меню "My bots"
        await my_bots_menu_handler(callback, state)

    @router.callback_query(F.data == 'personal_account')
    async def return_personal_account(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == user_id))
            user = result.scalar_one_or_none()
        if not user:
            await callback.message.edit_text("User not found. Send /start")
            await callback.answer()
            return
        text, kb = await get_personal_account_info(user, callback.bot)
        await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")

    @router.callback_query(F.data=="create_bot")
    async def create_new_bot(callback: types.CallbackQuery, state: FSMContext):
        await create_mirror_callback_handler(callback, state)