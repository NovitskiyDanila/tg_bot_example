import logging
from aiogram import types, F, Bot
from sqlalchemy import select, func
from database.session import async_session
from database.models import User, Purchase, Deposit

logger = logging.getLogger(__name__)


def build_personal_account_keyboard() -> types.InlineKeyboardMarkup:
    """
    Формирует inline-клавиатуру для личного кабинета пользователя:
      - Ряд 1: Deposit
      - Ряд 2: Last deposits, Last purchases
      - Ряд 3: My bots
    """
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💵 Deposit", callback_data="deposit"),
         types.InlineKeyboardButton(text="💳 Withdraw", callback_data="withdraw")],
        [
            types.InlineKeyboardButton(text="💰 My deposits", callback_data="my_deposits"),
            types.InlineKeyboardButton(text="🛒 My purchases", callback_data="my_purchases")
        ],
        [types.InlineKeyboardButton(text="🤖 My bots", callback_data="my_bots")]
    ])
    return kb


async def get_personal_account_info(user: User, bot: Bot) -> tuple:
    """
    Возвращает кортеж (text, reply_markup) для личного кабинета пользователя.

    Выполняет запросы в БД для подсчета количества покупок и рефералов, формирует реферальную ссылку и
    собирает итоговое сообщение с inline-клавиатурой.
    """
    # Подсчет количества покупок
    async with async_session() as session:

        amount_of_deposits_result = await session.execute(
            select(func.sum(Deposit.amount)).where(Deposit.user_id == user.id, Deposit.status == "confirmed")
        )
        total_deposit = amount_of_deposits_result.scalar() or 0

        amount_of_purchases_result = await session.execute(
            select(func.sum(Purchase.amount)).where(Purchase.user_id == user.id)
        )

        total_purchase = amount_of_purchases_result.scalar() or 0

        purchase_result = await session.execute(
            select(func.count()).select_from(Purchase).where(Purchase.user_id == user.id)
        )
        purchase_quantity = purchase_result.scalar() or 0

        referrals_result = await session.execute(
            select(func.count()).select_from(User).where(User.referrer_id == user.id)
        )
        referrals_count = referrals_result.scalar() or 0

    # Формируем реферальную ссылку для текущего бота
    try:
        bot_info = await bot.get_me()
        referral_link = f"https://t.me/{bot_info.username}?start={user.tg_id}"
        text = (
            f"👤 <b>User:</b> @{user.username}\n"
            f"🪪 <b>ID:</b> {user.tg_id}\n"
            f"🔗 <b>Referral link:</b> <code><i>{referral_link}</i></code>\n"
            f"💰 <b>Balance:</b> {float(user.balance / 100)}$\n"
            f"💰 <b>Bonus balance:</b> {float(user.bonus_balance / 100)}$\n"
            f"💸 <b>Amount of deposits:</b> {float(total_deposit / 100)}$\n"
            f"💸 <b>Amount of purchases:</b> {float(total_purchase / 100)}$\n"
            f"📊 <b>Purchase quantity:</b> {purchase_quantity}\n"
            f"👤 <b>Amount of referrals:</b> {referrals_count}"
        )

        # Формируем inline-клавиатуру для личного кабинета
        kb = build_personal_account_keyboard()
        return text, kb
    except Exception as e:
        logging.info("Bot doesn't exist ERROR")



def register_personal_account_handlers(router) -> None:
    @router.message(F.text == "ℹ Personal account")
    async def personal_account_handler(message: types.Message):
        user_tg_id = message.from_user.id
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.tg_id == user_tg_id)
            )
            user = result.scalar_one_or_none()

        if not user:
            await message.answer("User not found. Please, send /start.")
            return

        text, kb = await get_personal_account_info(user, message.bot)
        await message.answer(text, reply_markup=kb, parse_mode="HTML")