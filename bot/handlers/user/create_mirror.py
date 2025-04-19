import aiohttp
import logging
from aiogram import types
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from database.session import async_session
from database.models import User, MirrorBot
from config import WEBHOOK_URL
from aiogram import Bot
from cache import mirror_cache
from config import VIDEO, certificate

logger = logging.getLogger(__name__)
mirror_bots_cache = mirror_cache

class MirrorCreation(StatesGroup):
    waiting_for_token = State()


async def validate_token(token: str) -> dict:
    """
    Проверяет токен через вызов метода getMe.
    Если токен валиден, возвращает данные бота, иначе возбуждает исключение.
    """
    url = f"https://api.telegram.org/bot{token}/getMe"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if data.get("ok"):
                return data["result"]
            else:
                raise ValueError("Invalid token")


async def create_mirror_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия кнопки "Create Mirror".
    Отправляет инструкции и переводит пользователя в состояние ожидания токена.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➡️BotFather", url="https://t.me/BotFather" ))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_mirror_creation"))
    try:
        video_message = await callback.message.answer_video(VIDEO)
        await state.update_data(video_message_id=video_message.message_id)
    except Exception as Video_sending_error:
        logging.info(f"ERROR DURING VIDEO SENDING: {Video_sending_error}")
    await callback.message.answer("1️⃣ Please press the button below the message and then click <b>Start</b>.\n"
                                  "2️⃣ Type <b>/newbot</b>\n"
                                  "3️⃣ Send bot name\n"
                                  "4️⃣ Send bot username (without @)\n"
                                  "5️⃣ Send a <b>token</b> from BotFather to the current chat", parse_mode='HTML', reply_markup=builder.as_markup())

    await state.set_state(MirrorCreation.waiting_for_token)
    await callback.answer()  # Закрывает всплывающее окно callback


async def token_handler(message: types.Message, state: FSMContext):
    """
    Обработчик сообщения с токеном.
    Проверяет токен, сохраняет данные зеркального бота, устанавливает вебхук и активирует зеркало.
    """
    logger.info(f"Token handler triggered, state: {await state.get_state()}")
    try:
        token = message.text.strip()
    except Exception as e:
        await message.answer("Invalid token. Please try again.")
        return
    async with async_session() as session:
        curr_user_result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
        curr_user = curr_user_result.scalar_one_or_none()
        users_mirror_bots_result = await session.execute(select(MirrorBot).where(MirrorBot.owner_id == curr_user.id))
        users_mirror_bots = users_mirror_bots_result.scalars().all()
        if users_mirror_bots:
            for mirror_bot in users_mirror_bots:
                if mirror_bot.token == token:
                    await message.answer("⚠️ The bot with this token is already registered. Please send a different token.")
                    return

    try:
        bot_info = await validate_token(token)
    except Exception as e:
        await message.answer("Invalid token. Please try again.")
        return

    async with async_session() as session:
        try:
            result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
            user = result.scalar_one_or_none()
            if not user:
                await message.answer("User not found. Please send /start")
                await state.clear()
                return

            mirror_bot = MirrorBot(
                owner_id=user.id,
                token=token,
                username=bot_info.get("username", "unknown"),
                active=True
            )
            session.add(mirror_bot)
            await session.commit()
        except Exception as e:
            logging.info(f"ERROR: {e}")
            await session.rollback()
            await message.answer("An error occurred while creating mirror bot, please try again. 🙂")
            return

    # Устанавливаем вебхук для зеркального бота, используя NGROK_URL
    webhook_url = f"{WEBHOOK_URL}/webhook/mirror/{mirror_bot.id}"
    mirror_bot_instance = Bot(token=token)
    mirror_bots_cache[mirror_bot.id] = mirror_bot_instance
    try:
        await mirror_bot_instance.set_webhook(webhook_url, certificate=certificate)
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        await message.answer("⚠️ Something went wrong. Please check your token and try again.")
        await state.clear()
        return
    builder = InlineKeyboardBuilder()
    bot_username = bot_info.get("username")
    builder.row(InlineKeyboardButton(text=f"➡️@{bot_username}", url=f"https://t.me/{bot_username}"))
    await message.answer(
        "✅ The mirror has been created! Now launch the bot by going to the button below and clicking “Start”.", reply_markup=builder.as_markup(), parse_mode='HTML')
    await state.clear()


async def cancel_mirror_creation(callback: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    video_message_id = state_data.get("video_message_id")
    if video_message_id:
        bot = callback.bot
        await bot.delete_message(callback.from_user.id, video_message_id)
    await callback.message.delete()
    await state.clear()
    await callback.message.answer("Mirror bot creation was canceled")


def register_create_mirror_handlers(dp):
    dp.callback_query.register(create_mirror_callback_handler, lambda cb: cb.data == "create_mirror")
    dp.message.register(token_handler, MirrorCreation.waiting_for_token)
    dp.callback_query.register(cancel_mirror_creation, lambda cb: cb.data == "cancel_mirror_creation")
