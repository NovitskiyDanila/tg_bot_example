from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_create_mirror_kb():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Create Mirror", callback_data="create_mirror")]
    ])
    return keyboard