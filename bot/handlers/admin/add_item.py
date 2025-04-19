import logging
import validators

from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from sqlalchemy import select
from database.session import async_session
from database.models import Item, ItemCategory, User
from filters import AdminOperatorFilter

logger = logging.getLogger(__name__)

# --- FSM States for item creation ---
class ItemCreation(StatesGroup):
    waiting_for_category = State()
    waiting_for_item_name = State()
    waiting_for_weight = State()
    waiting_for_area = State()
    waiting_for_photo1 = State()
    waiting_for_description1 = State()
    waiting_for_additional_photos_count = State()
    waiting_for_additional_photo = State()
    waiting_for_description2 = State()
    waiting_for_price = State()
    confirmation = State()


STATIC_PHOTOS_PATH = "static/photos"


def is_valid_url(url: str) -> bool:
    return bool(validators.url(url))


def generate_item_preview(data: dict) -> str:
    """Формирует текст предварительного просмотра товара."""
    lines = ["**Item Preview:**"]
    if "category_name" in data:
        lines.append(f"<b>Category:</b> {data['category_name']}")
    if "item_name" in data:
        lines.append(f"<b>Name:</b> {data['item_name']}")
    if "weight" in data:
        lines.append(f"<b>Weight:</b> {data['weight']}")
    if "area" in data:
        lines.append(f"<b>Area:</b> {data['area']}")
    if "photo1_url" in data:
        lines.append(f"<b>Item photo:</b> ✅")
    if "description1" in data:
        lines.append(f"<b>Item description:</b> {data['description1']}")
    if "additional_photos_urls" in data and data.get("additional_photos_urls"):
        for idx, photo in enumerate(data["additional_photos_urls"], start=1):
            lines.append(f"<b>Location photo{idx}:</b> ✅")
    if "description2" in data:
        lines.append(f"<b>Location description:</b> {data['description2']}")
    if "price" in data:
        lines.append(f"Price: {data['price']}$")
    return "\n".join(lines)


async def update_preview(message: types.Message, state: FSMContext, prompt: str, reply_markup=None):
    """
    Удаляет предыдущее сообщение-превью (если есть) и отправляет новое.
    Сохраняет message_id нового сообщения в состоянии (ключ "preview_msg_id").
    """
    data = await state.get_data()
    preview_text = generate_item_preview(data)
    full_text = f"{preview_text}\n\n{prompt}"
    if "preview_msg_id" in data and data["preview_msg_id"]:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["preview_msg_id"])
        except Exception as e:
            logger.error(f"Error deleting previous preview: {e}")
            pass
    sent = await message.answer(full_text, reply_markup=reply_markup)
    await state.update_data(preview_msg_id=sent.message_id)


def get_navigation_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура для навигации: только кнопка Cancel."""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_item")]])


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура для подтверждения: Confirm и Cancel."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_item"),
         InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_item")]
    ])


def get_category_keyboard(categories) -> InlineKeyboardMarkup:
    """
    Генерирует inline клавиатуру для выбора категории.
    Каждая строка содержит две кнопки с категориями.
    Последняя строка содержит кнопку "❌ Cancel".
    Категории передаются как список словарей.
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[], row_width=2)
    row = []
    for i, cat in enumerate(categories, start=1):
        row.append(InlineKeyboardButton(text=cat["category_name"], callback_data=f"select_cat:{cat['id']}"))
        if i % 2 == 0:
            kb.inline_keyboard.append(row)
            row = []
    if row:
        kb.inline_keyboard.append(row)
    kb.inline_keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_item")])
    return kb


# --- Registration function ---
def register_add_item_handlers(router) -> None:
    """Регистрирует все хэндлеры для добавления товара через админ-роутер."""

    @router.message(Command("add_item"), AdminOperatorFilter())
    async def add_item_command_handler(message: types.Message, state: FSMContext):
        await state.clear()
        async with async_session() as session:
            result = await session.execute(select(ItemCategory))
            categories = result.scalars().all()
        if not categories:
            await message.answer("No categories found. Please add a new category with /add_category.")
            return
        # Преобразуем объекты категорий в список словарей
        cat_list = [{"id": cat.id, "category_name": cat.category_name} for cat in categories]
        await state.update_data(additional_photos=[], preview_msg_id=None, categories=cat_list)
        kb = get_category_keyboard(cat_list)
        sent = await message.answer("Please choose a category for the item:", reply_markup=kb)
        await state.update_data(preview_msg_id=sent.message_id)
        await state.set_state(ItemCreation.waiting_for_category)

    @router.callback_query(lambda cb: cb.data.startswith("select_cat"), AdminOperatorFilter())
    async def category_select_handler(callback: types.CallbackQuery, state: FSMContext):
        try:
            _, cat_id_str = callback.data.split(":")
            category_id = int(cat_id_str)
        except Exception as e:
            logging.info(f"ERROR: {e}")
            await callback.answer("Invalid category selection.")
            return
        data = await state.get_data()
        categories = data.get("categories", [])
        category = next((cat for cat in categories if cat["id"] == category_id), None)
        if not category:
            await callback.answer("Category not found.")
            return
        await state.update_data(category_id=category_id, category_name=category["category_name"])
        prompt = "Enter the item name:"
        await update_preview(callback.message, state, prompt, reply_markup=get_navigation_keyboard())
        await state.set_state(ItemCreation.waiting_for_item_name)
        await callback.answer()

    @router.message(ItemCreation.waiting_for_item_name, AdminOperatorFilter())
    async def item_name_handler(message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not message.text or not message.text.strip():
            await message.answer("Please enter text")
            return
        data["item_name"] = message.text.strip()
        await state.update_data(**data)
        prompt = "Enter the weight:"
        await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
        await state.set_state(ItemCreation.waiting_for_weight)

    @router.message(ItemCreation.waiting_for_weight, AdminOperatorFilter())
    async def weight_handler(message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not message.text or not message.text.strip():
            await message.answer("Please enter text")
            return
        data["weight"] = message.text.strip()
        await state.update_data(**data)
        prompt = "Enter the area:"
        await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
        await state.set_state(ItemCreation.waiting_for_area)

    @router.message(ItemCreation.waiting_for_area, AdminOperatorFilter())
    async def area_handler(message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not message.text or not message.text.strip():
            await message.answer("Please enter text")
            return
        data["area"] = message.text.strip()
        await state.update_data(**data)
        prompt = "Send Photo1 (as a photo):"
        await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
        await state.set_state(ItemCreation.waiting_for_photo1)

    @router.message(ItemCreation.waiting_for_photo1, AdminOperatorFilter())
    async def photo1_handler(message: types.Message, state: FSMContext):
        if not message.text:
            await message.answer("Please send a valid URL.")
            return
        photo1_url = message.text
        if is_valid_url(photo1_url):
            await state.update_data(photo1_url=photo1_url)
            prompt = "Enter item description (visible before purchase):"
            await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
            await state.set_state(ItemCreation.waiting_for_description1)
        else:
            await message.answer("Please send a valid URL")
            return

    @router.message(ItemCreation.waiting_for_description1, AdminOperatorFilter())
    async def description1_handler(message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not message.text:
            await message.answer("Please enter text")
            return
        data["description1"] = message.text
        await state.update_data(**data)
        prompt = "Enter the number of additional photos (0-3):"
        await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
        await state.set_state(ItemCreation.waiting_for_additional_photos_count)

    @router.message(ItemCreation.waiting_for_additional_photos_count, AdminOperatorFilter())
    async def additional_photos_count_handler(message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not message.text:
            await message.answer("Please enter a valid number.")
            return
        try:
            count = int(message.text.strip())
        except ValueError:
            await message.answer("Please enter a valid number.")
            return
        if count < 0 or count > 3:
            await message.answer("The number must be between 0 and 3. Please try again.")
            return
        data["additional_photos_count"] = count
        data["additional_photos_urls"] = []
        await state.update_data(**data)
        if count > 0:
            prompt = "Send location photo 1 (as a photo):"
            await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
            await state.set_state(ItemCreation.waiting_for_additional_photo)

    @router.message(ItemCreation.waiting_for_additional_photo, AdminOperatorFilter())
    async def additional_photo_handler(message: types.Message, state: FSMContext):
        if not message.text:
            await message.answer("Please send a valid URL.")
            return
        photo_url = message.text
        if is_valid_url(photo_url):
            data = await state.get_data()
            photos_urls = data.get("additional_photos_urls", [])
            photos_urls.append(photo_url)
            data["additional_photos_urls"] = photos_urls
            await state.update_data(**data)
            count = data.get("additional_photos_count", 0)
            if len(photos_urls) < count:
                prompt = f"Send location photo{len(photos_urls)+1} (as a URL):"
                await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
                await state.set_state(ItemCreation.waiting_for_additional_photo)
            else:
                prompt = "Enter location description (visible after purchase):"
                await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
                await state.set_state(ItemCreation.waiting_for_description2)
        else:
            await message.answer("Please send a valid URL link")
            return

    @router.message(ItemCreation.waiting_for_description2, AdminOperatorFilter())
    async def description2_handler(message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not message.text:
            await message.answer("Please enter text")
            return
        data["description2"] = message.text
        await state.update_data(**data)
        prompt = "Enter the price:"
        await update_preview(message, state, prompt, reply_markup=get_navigation_keyboard())
        await state.set_state(ItemCreation.waiting_for_price)

    @router.message(ItemCreation.waiting_for_price, AdminOperatorFilter())
    async def price_handler(message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not message.text or not message.text.strip():
            await message.answer("Please enter a valid number for price")
            return
        try:
            price = int(message.text.strip())
        except ValueError:
            await message.answer("Please enter a valid number for price.")
            return
        MAX_PRICE = 99999999.99  # Максимальное значение
        if price > MAX_PRICE:
            await message.answer("Price exceeds the allowed maximum value.")
            return
        data["price"] = price
        await state.update_data(**data)
        confirmation_kb = get_confirmation_keyboard()
        await update_preview(message, state, "Please confirm or cancel the item entry:", reply_markup=confirmation_kb)
        await state.set_state(ItemCreation.confirmation)

    @router.callback_query(F.data == "confirm_item", AdminOperatorFilter())
    async def confirmation_callback_handler(callback: types.CallbackQuery, state: FSMContext):

        data = await state.get_data()
        additional_photos_urls = data.get("additional_photos_urls")
        category_id = data.get("category_id")
        item_name = data.get("item_name")
        weight = data.get("weight")
        area = data.get("area")
        price = data.get("price")
        description1 = data.get("description1")
        description2 = data.get("description2")
        photo1 = data.get("photo1_url")
        photo2 = additional_photos_urls[0] if len(additional_photos_urls) >= 1 else None
        photo3 = additional_photos_urls[1] if len(additional_photos_urls) >= 2 else None
        photo4 = additional_photos_urls[2] if len(additional_photos_urls) >= 3 else None

        async with async_session() as session:
            try:
                result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
                user = result.scalar_one_or_none()
                if not user:
                    await callback.message.edit_text("User not found in DB. Please send /start.")
                    await state.clear()
                    return
                new_item = Item(
                    category_id=category_id,
                    item_name=item_name,
                    weight=weight,
                    area=area,
                    photo1=photo1,
                    description1=description1,
                    photo2=photo2,
                    photo3=photo3,
                    photo4=photo4,
                    description2=description2,
                    price=price*100,
                    added_by=user.id
                )
                session.add(new_item)
                await session.commit()
                await session.refresh(new_item)
            except Exception as e:
                logging.info(f"ERROR: {e}")
                await session.rollback()
                await callback.message.answer("An error occurred while adding the category, please try again. 🙂")
                return

        await callback.message.edit_text(f"The product has been successfully added")
        preview_caption = ("*** ITEM PREVIEW CARD ***\n\n"
                           f"🆔 <b>Item ID: </b>{new_item.id}\n"
                           f"🛍 <b>Product:</b>{item_name}\n"
                           f"⚖️ <b>Weight:</b> {weight}\n"
                           f"🏘 <b>Area:</b> {area}\n"
                           f"💴 <b>Price:</b> {price}$\n"
                           f"📄 <b>Description: {description1}</b>")
        await callback.message.answer_photo(photo=photo1, caption=preview_caption, parse_mode='HTML')

        item_receipt = ("*** ITEM ORDER DETAILS CARD ***\n\n"
                        f"🛍 <b>Product:</b>{item_name}\n"
                        f"⚖️ <b>Weight:</b> {weight}\n"
                        f"🏘 <b>Area:</b> {area}\n"
                        f"📄 <b>Location description: {description2}</b>")
        await callback.message.answer(item_receipt, parse_mode='HTML')
        if photo2:
            await callback.message.answer_photo(photo2)
        if photo3:
            await callback.message.answer_photo(photo3)
        if photo4:
            await callback.message.answer_photo(photo4)
        await state.clear()

    @router.callback_query(F.data == "cancel_item", AdminOperatorFilter())
    async def nav_cancel_callback_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.delete()
        await state.clear()
        await callback.answer("Item creation canceled.")
