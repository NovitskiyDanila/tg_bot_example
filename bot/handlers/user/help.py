from aiogram import types, F


def register_help_handlers(router):

    @router.message(F.text == "💬 Support")
    async def help_handler(message: types.Message):
        await message.answer("If you have any questions, please contact @operator")
