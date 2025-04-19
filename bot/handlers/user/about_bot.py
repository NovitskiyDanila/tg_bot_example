from aiogram import F, types
from aiogram.types import Message


def register_about_bot_handlers(router):

    @router.message(F.text == "ℹ️ About bot")
    async def send_bot_info_message(message: Message):
        about_bot_message = (
            "🤖 <b>About the Bot</b>\n\n"
            "To ensure smooth operation, you must have at least <b>one active mirror bot</b> running.\n\n"
            "<b>Referral Program:</b>\n"
            "Earn a <b>10% bonus</b> on each deposit made by your direct referrals and a <b>3% bonus</b> on deposits from users invited by your direct referrals.\n"
            "Bonus balance becomes available after completing <b>three purchases</b>.\n"
            "Bonuses can be used to purchase products, and you will eventually be able to withdraw them to your TRC20 wallet (currently in development).\n\n"
            "<b>Deposit Verification:</b>\n"
            "Deposits are verified automatically. Please ensure that the amount you send is <b>exactly equal</b> to the requested deposit amount.\n\n"
            "If you have any questions, please contact our operator.\n\n"
        )

        await message.answer(about_bot_message, parse_mode='HTML')
