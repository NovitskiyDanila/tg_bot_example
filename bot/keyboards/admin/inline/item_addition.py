import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_category_keyboard(categories) -> InlineKeyboardMarkup:
    """
    Генерирует inline клавиатуру для выбора категории без пагинации.

    Каждая строка содержит максимум 2 кнопки с категориями (с callback_data вида "select_cat:<id>").
    Последняя строка содержит кнопку "❌ Cancel" с callback_data "cancel_add_item".

    :param categories: Список объектов категорий (у каждого должен быть атрибут id и category_name).
    :return: InlineKeyboardMarkup
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[], row_width=2)
    row = []
    for i, cat in enumerate(categories, start=1):
        row.append(InlineKeyboardButton(text=cat.category_name, callback_data=f"select_cat:{cat.id}"))
        if i % 2 == 0:
            kb.inline_keyboard.append(row)
            row = []
    if row:  # Если осталась неполная строка
        kb.inline_keyboard.append(row)
    # Добавляем последнюю строку с кнопкой Cancel
    kb.inline_keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_add_item")])
    return kb


def get_navigation_keyboard(back_allowed: bool = True) -> InlineKeyboardMarkup:
    """
    Возвращает inline клавиатуру для навигации с кнопками Back и Cancel.

    :param back_allowed: Если True, включается кнопка "⬅️ Back", иначе — только Cancel.
    :return: InlineKeyboardMarkup с кнопками.
    """
    buttons = []
    if back_allowed:
        buttons.append(InlineKeyboardButton(text="⬅️ Back", callback_data="back_item"))
    buttons.append(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_item"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает inline клавиатуру для подтверждения введённых данных.
    Клавиатура содержит кнопки: Confirm, Edit, Cancel.

    :return: InlineKeyboardMarkup с кнопками подтверждения.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_item"),
            InlineKeyboardButton(text="✏️ Edit", callback_data="edit_item"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_item")
        ]
    ])


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_edit_keyboard(additional_count: int = 0) -> InlineKeyboardMarkup:
    """
    Возвращает inline клавиатуру для редактирования полей товара.
    Основные поля:
      - "Item Name", "Weight", "Area", "Photo1", "Description1"
    Затем, если additional_count >= 1, добавляются кнопки для:
      - Photo2 (если >=1), Photo3 (если >=2), Photo4 (если ==3)
    Далее добавляются:
      - "Description2", "Price"
    В последней строке добавляется кнопка "⬅️ Back" для возврата к клавиатуре подтверждения.
    Callback data имеет формат "edit_<field>", например, "edit_item_name".
    """
    fields = [
        ("Item Name", "edit_item_name"),
        ("Weight", "edit_weight"),
        ("Area", "edit_area"),
        ("Photo1", "edit_photo1"),
        ("Description1", "edit_description1"),
    ]
    # Динамически добавляем кнопки для дополнительных фотографий
    if additional_count >= 1:
        fields.append(("Photo2", "edit_photo2"))
    if additional_count >= 2:
        fields.append(("Photo3", "edit_photo3"))
    if additional_count >= 3:
        fields.append(("Photo4", "edit_photo4"))
    fields.extend([
        ("Description2", "edit_description2"),
        ("Price", "edit_price")
    ])

    keyboard = []
    row = []
    for index, (label, callback_data) in enumerate(fields, start=1):
        row.append(InlineKeyboardButton(text=label, callback_data=callback_data))
        if index % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    # Добавляем строку с кнопкой "⬅️ Back"
    keyboard.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_confirm")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


