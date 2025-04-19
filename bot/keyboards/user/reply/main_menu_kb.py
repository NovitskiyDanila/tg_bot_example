from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_kb():
    """
    Создаёт ReplyKeyboardMarkup с тремя строками кнопок:
      1) [💲 Buy, 🛒 Catalog]
      2) [ℹ Personal account]
      3) [💬 Help]
    """
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💲 Buy"), KeyboardButton(text="🛒 Catalog")],
            [KeyboardButton(text="ℹ Personal account")],
            [KeyboardButton(text="ℹ️ About bot"),KeyboardButton(text="💬 Support")]
        ],
        resize_keyboard=True
    )
    return kb
