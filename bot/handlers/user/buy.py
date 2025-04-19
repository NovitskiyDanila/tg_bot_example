import logging
from datetime import datetime

from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InputFile, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update, func

from database.session import async_session
from database.models import Item, ItemCategory, User, Purchase  # предполагается, что модель Items называется Item

logger = logging.getLogger(__name__)


class ItemBuy(StatesGroup):
    waiting_for_area = State()
    waiting_for_category = State()
    waiting_for_item = State()
    waiting_for_weight = State()
    waiting_for_bonus_usage = State()
    waiting_for_bonus_decision = State()
    waiting_for_bonus_amount = State()
    waiting_for_confirmation = State()


async def get_user_by_callback(callback: types.CallbackQuery):
    try:
        async with async_session() as session:
            user_query = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
            user = user_query.scalar_one_or_none()
            return user
    except Exception as e:
        await callback.answer("User not registered")
        return None


async def get_new_item(state: FSMContext):
    state_data = await state.get_data()
    selected_item_name = state_data.get("selected_item_name")
    selected_item_weight = state_data.get("selected_item_weight")
    selected_item_area = state_data.get("selected_item_area")
    selected_item_category_id = state_data.get("selected_category_id")
    selected_item_price = state_data.get("selected_item_price")

    try:
        async with async_session() as session:
            result = await session.execute(
                select(Item)
                .where(
                    Item.area == selected_item_area,
                    Item.category_id == selected_item_category_id,
                    Item.item_name == selected_item_name,
                    Item.weight == selected_item_weight,
                    Item.price == selected_item_price,
                    Item.is_bought == False,
                    Item.is_deleted == False
                )
            )
            selected_item = result.scalars().first()
            return selected_item
    except Exception as e:
        logging.info(f"BUILDING CONFIRMATION KEYBOARD ERROR: {e}")



async def can_use_bonus(user_tg_id: int) -> bool:
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.tg_id == user_tg_id))
        user = user_result.scalar_one_or_none()

        purchases_result = await session.execute(
            select(func.count(Purchase.id)).where(Purchase.user_id == user.id)
        )
        purchase_count = purchases_result.scalar() or 0
        return purchase_count > 4


async def get_item_by_id(item_id):
    try:
        async with async_session() as session:
            item_query = await session.execute(select(Item).where(Item.id == item_id, Item.is_bought == False, Item.is_deleted == False))
            item = item_query.scalars().first()
            return item
    except Exception as e:
        logging.info(f"ERROR: {e}")
        return None


async def process_purchase(state: FSMContext, callback: types.CallbackQuery, new_balance: int, new_bonus_balance: int = 0):
    """
    Функция проводит покупку товара.
    Если use_bonus == True, предполагается, что бонусы используются для уменьшения цены.
    Здесь можно сохранить как исходную цену, так и итоговую (после применения бонусов).
    """

    state_data = await state.get_data()
    item_id = state_data.get("selected_item_id")
    curr_user = await get_user_by_callback(callback)
    selected_item = await get_item_by_id(item_id)

    if not selected_item:
        selected_item = await get_new_item(state)
        if not selected_item:
            await callback.message.delete()
            await callback.message.answer("❌ This item was purchased by another user.")
            await state.clear()
            return

    try:
        async with async_session.begin() as session:
        # Обновляем статус товара: помечаем как купленный и фиксируем время покупки
            await session.execute(
                update(Item)
                .where(Item.id == selected_item.id)
                .values(is_bought=True, purchase_date=datetime.utcnow())
            )
            # Создаем запись о покупке (amount можно сохранить как исходную цену или итоговую)
            purchase = Purchase(
                user_id=curr_user.id,
                item_id=selected_item.id,
                amount=selected_item.price  # здесь можно записать итоговую цену, если требуется
            )
            session.add(purchase)
            # Обновляем баланс пользователя
            await session.execute(
                update(User)
                .where(User.id == curr_user.id)
                .values(balance=new_balance,
                        bonus_balance=new_bonus_balance)
            )

            await session.commit()
            await callback.answer()

    except Exception as e:
        await session.rollback()
        logger.error(f"Error during purchase transaction: {e}")
        await callback.message.answer("An error occurred while completing your purchase. Please, try again")
        return

        # Если транзакция завершилась успешно:
    await callback.message.answer("Purchase completed successfully!")
    await callback.message.answer(f"******ITEM CARD******\n"
                                  f"🆔 <b>Purchase ID:</b> <code>{selected_item.id}</code>\n"
                                  f"🛍 <b>Product</b>: {selected_item.item_name} \n"
                                  f"⚖️ <b>Weight</b>: {selected_item.weight}\n"
                                  f"🏘 <b>Area</b>: {selected_item.area}\n"
                                  f"📄 <b>Location description</b>: {selected_item.description2}", parse_mode='HTML')
    if selected_item.photo2:
        await callback.message.answer_photo(photo=selected_item.photo2)
    if selected_item.photo3:
        await callback.message.answer_photo(photo=selected_item.photo3)
    if selected_item.photo4:
        await callback.message.answer_photo(photo=selected_item.photo4)

    return purchase


async def build_buy_keyboard(state: FSMContext):
    """
    Формирует inline-клавиатуру, где каждая кнопка представляет собой город (area),
    кнопки расположены по 2 в ряд. Добавляется также кнопка Cancel.
    """
    try:
        async with async_session() as session:

            result = await session.execute(
                select(Item.area)
                .where(Item.is_bought == False, Item.is_deleted == False)
                .group_by(Item.area)
            )
            areas = [row[0] for row in result.all()]

    except Exception as e:
        logger.error(f"Error during purchase transaction: {e}")
        return

    builder = InlineKeyboardBuilder()
    for i in range(0, len(areas), 2):
        row_buttons = []
        for area in areas[i:i+2]:
            row_buttons.append(
                types.InlineKeyboardButton(text='🏠 ' + area, callback_data=f"buy_area_{area}")
            )
        builder.row(*row_buttons)
    builder.row(
        types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_buying")
    )
    if len(areas) > 0:
        text = "🛍 Choose the area where you want to buy the product"
    else:
        text = "All items are currently out of stock"

    await state.set_state(ItemBuy.waiting_for_area)

    return builder.as_markup(), text


async def build_category_keyboard(area: str, state: FSMContext):

    try:
        async with async_session() as session:
            result = await session.execute(
                select(ItemCategory.id, ItemCategory.category_name)
                .join(Item, ItemCategory.id == Item.category_id)
                .where(
                    Item.area == area,
                    Item.is_bought == False,
                    Item.is_deleted == False
                )
                .group_by(ItemCategory.id, ItemCategory.category_name)
            )
            # Извлекаем список категорий (строк)
        categories = [(row[0], row[1]) for row in result.all()]
    except Exception as e:
        logger.error(f"Error during purchase transaction: {e}")
        return

    await state.update_data(selected_item_area=area)
    await state.update_data(area_categories=categories)

    # Строим inline клавиатуру: кнопки по 2 в ряд + кнопки Back и Cancel
    builder = InlineKeyboardBuilder()
    for i in range(0, len(categories), 2):
        row_buttons = []
        for category in categories[i:i + 2]:
            cat_id, cat_name = category  # распаковываем кортеж
            row_buttons.append(
                types.InlineKeyboardButton(text='📦 ' + cat_name, callback_data=f"buy_category_{cat_id}")
            )
        builder.row(*row_buttons)
    builder.row(
        types.InlineKeyboardButton(text="🔙 Back", callback_data="back_buy_area")
    )
    builder.row(
        types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_buying")
    )

    if len(categories) > 0:
        text = f"🛍 The following categories are available in the area of <b>{area}</b>:"
    else:
        text = "There are no items available right now"

    await state.set_state(ItemBuy.waiting_for_category)

    return builder.as_markup(), text


async def build_item_keyboard(category_id, state: FSMContext):

    state_data = await state.get_data()
    area = state_data.get("selected_item_area")
    area_categories = state_data.get("area_categories")
    category_name = next((name for id_, name in area_categories if id_ == category_id), None)

    try:
        async with async_session() as session:
            result = await session.execute(
                select(Item.item_name)
                .where(
                    Item.area == area,
                    Item.category_id == category_id,
                    Item.is_bought == False,
                    Item.is_deleted == False
                )
                .group_by(Item.item_name)
            )
            items: list = [row[0] for row in result.all()]
        logger.info(f"Current parameters: area = {area}, category_id: {category_id}, category_name: {category_name}, items: {items} ")
    except Exception as e:
        logger.error(f"Error during purchase transaction: {e}")
        return

    builder = InlineKeyboardBuilder()
    # Формируем сообщение и inline-клавиатуру (2 кнопки в ряд)
    if len(items) > 0:
        text = f"🛍 The following products are available in the area of <b>{area}</b> in category <b>{category_name}</b>"
    else:
        text = "There are no items available right now"

    for i in range(0, len(items), 2):
        row_buttons = []
        for item_name in items[i:i + 2]:
            row_buttons.append(
                types.InlineKeyboardButton(text=item_name, callback_data=f"buy_item_{item_name}")
            )
        builder.row(*row_buttons)
    # Кнопка Back: возвращает к выбору категории (обработчик, например, должен редактировать сообщение на меню с категориями)
    builder.row(
        types.InlineKeyboardButton(text="🔙 Back", callback_data="back_buy_category")
    )
    # Кнопка Cancel
    builder.row(
        types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_buying")
    )

    # Сохраняем выбранную категорию в состоянии, если потребуется дальше
    await state.update_data(selected_category_name=category_name, selected_category_id=category_id)
    await state.set_state(ItemBuy.waiting_for_item)

    return builder.as_markup(), text


async def build_weights_keyboard(selected_item_name, state: FSMContext):

    state_data = await state.get_data()
    selected_item_area = state_data.get("selected_item_area")
    selected_category_id = state_data.get("selected_category_id")

    try:
        async with async_session() as session:
            result = await session.execute(
                select(Item.weight)
                .where(
                    Item.area == selected_item_area,
                    Item.category_id == selected_category_id,
                    Item.item_name == selected_item_name,
                    Item.is_bought == False,
                    Item.is_deleted == False
                ).group_by(Item.weight)
            )
            selected_item_weights = [row[0] for row in result.all()]
    except Exception as e:
        logging.info(f"ERROR: {e}")
        return None

    # Формируем сообщение и inline-клавиатуру (2 кнопки в ряд)
    text = f"🛍 How much do you want to buy"
    builder = InlineKeyboardBuilder()
    for i in range(0, len(selected_item_weights), 2):
        row_buttons = []
        for item_weight in selected_item_weights:
            row_buttons.append(
                types.InlineKeyboardButton(text=item_weight, callback_data=f"buy_weight_{item_weight}")
            )
        builder.row(*row_buttons)
    # Кнопка Back: возвращает к выбору категории (обработчик, например, должен редактировать сообщение на меню с категориями)
    builder.row(
        types.InlineKeyboardButton(text="🔙 Back", callback_data="back_buy_item")
    )
    # Кнопка Cancel
    builder.row(
        types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_buying")
    )

    await state.set_state(ItemBuy.waiting_for_weight)
    return builder.as_markup(), text


async def build_confirmation_keyboard(selected_item_weight, state: FSMContext):
    await state.update_data(selected_item_weight=selected_item_weight)
    state_data = await state.get_data()
    logging.debug(f"state data: {state_data}")
    selected_item_area = state_data.get("selected_item_area")
    selected_category_id = state_data.get("selected_category_id")
    selected_item_name = state_data.get("selected_item_name")

    try:
        async with async_session() as session:
            result = await session.execute(
                select(Item)
                .where(
                    Item.area == selected_item_area,
                    Item.category_id == selected_category_id,
                    Item.item_name == selected_item_name,
                    Item.weight == selected_item_weight,
                    Item.is_bought == False,
                    Item.is_deleted == False
                )
            )
            selected_item = result.scalars().first()
    except Exception as e:
        logging.info(f"BUILDING CONFIRMATION KEYBOARD ERROR: {e}")
    if selected_item is None:
        text = "item not available"
        photo = None
    else:
        selected_item_price = selected_item.price
        selected_item_description1 = selected_item.description1
        await state.update_data(selected_item_id=selected_item.id)
        await state.update_data(selected_item_price=selected_item_price)



        # Формируем сообщение и inline-клавиатуру (2 кнопки в ряд)
        text = (f"🛍 <b>Product</b>: {selected_item_name} \n"
                f"⚖️ <b>Weight</b>: {selected_item_weight}\n"
                f"🏘 <b>Area</b>: {selected_item_area}\n"
                f"💴 <b>Price</b>: {float(selected_item_price / 100)}$ \n"
                f"📄 <b>Description</b>: {selected_item_description1}")
        photo = selected_item.photo1
        logger.debug("Selected item found and state updated.")

    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text="💲Buy", callback_data="buy_confirmation"),
        types.InlineKeyboardButton(text="🔙Back", callback_data="back_buy_confirmation")
    )

    await state.set_state(ItemBuy.waiting_for_confirmation)
    return photo, builder.as_markup(), text


def register_buy_handlers(router) -> None:

    @router.message(F.text == "💲 Buy")
    async def buy_handler(message: types.Message, state: FSMContext):
        # Выполняем запрос к таблице Item:

        result = await build_buy_keyboard(state)
        if result is None:
            if not keyboard:
                await message.answer("Unfortunately there are no products available at the moment 😔1")
                await state.clear()
                return
        keyboard, text = result

        await message.answer(text=text, reply_markup=keyboard)

    @router.callback_query(F.data == "back_buy_area", ItemBuy.waiting_for_category)
    async def return_to_buy_handler(callback: types.CallbackQuery, state: FSMContext):
        result = await build_buy_keyboard(state)

        if result is None:
            await callback.message.delete()
            await callback.message.answer("Unfortunately there are no products available at the moment 😔 2")
            await state.clear()
            return

        areas_keyboard, text = result

        await callback.message.edit_text(text=text, reply_markup=areas_keyboard)

    @router.callback_query(F.data.startswith('buy_area_'), ItemBuy.waiting_for_area)
    async def buy_area_selected(callback: types.CallbackQuery, state: FSMContext):
        # Извлекаем выбранное area из callback data, например, "buy_area_Moscow" -> "Moscow"
        area = str(callback.data.split("_")[-1])
        logger.info(f"Selected area: {area}")

        result = await build_category_keyboard(area, state)

        if result is None:
            await callback.message.delete()
            await callback.message.anwer(text="Unfortunately there are no products available at the moment 3")
            await state.clear()
            return

        category_keyboard, text = result

        await callback.message.edit_text(
            text=text,
            reply_markup=category_keyboard,
            parse_mode="HTML"
        )

    @router.callback_query(F.data == "back_buy_category", ItemBuy.waiting_for_item)
    async def return_to_category_handler(callback: types.CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        selected_item_area = state_data.get("selected_item_area")

        result = await build_category_keyboard(selected_item_area, state)

        if result is None:
            await callback.message.delete()
            await callback.message.answer("Unfortunately there are no products available at the moment 4")
            await state.clear()

        item_keyboard, item_text = result

        await callback.message.edit_text(text=item_text, reply_markup=item_keyboard, parse_mode='HTML')

    @router.callback_query(F.data.startswith('buy_category_'), ItemBuy.waiting_for_category)
    async def buy_category_selected(callback: types.CallbackQuery, state: FSMContext):

        category_id = int(callback.data.split("_")[-1])
        result = await build_item_keyboard(category_id, state)

        if result is None:
            await callback.message.delete()
            await callback.message.answer("Unfortunately there are no products available at the moment 5")
            return
        items_keyboard, item_text = result
        await callback.message.edit_text(item_text, reply_markup=items_keyboard, parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data == "back_buy_item", ItemBuy.waiting_for_weight)
    async def return_to_item_handler(callback: types.CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        selected_category_id = state_data.get("selected_category_id")
        result = await build_item_keyboard(selected_category_id, state)
        items_keyboard, text = result
        await callback.message.edit_text(text, reply_markup=items_keyboard, parse_mode='HTML')
        await callback.answer()

    @router.callback_query(F.data.startswith('buy_item_'), ItemBuy.waiting_for_item)
    async def buy_item_selected(callback: types.CallbackQuery, state: FSMContext):
        selected_item_name = callback.data.split('_')[-1]
        await state.update_data(selected_item_name=selected_item_name)
        kb, text = await build_weights_keyboard(selected_item_name, state)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data == "back_buy_confirmation", ItemBuy.waiting_for_confirmation)
    async def return_to_weight_handler(callback: types.CallbackQuery, state: FSMContext):

        state_data = await state.get_data()
        selected_item_name = state_data.get("selected_item_name")

        weights_kb, weights_text = await build_weights_keyboard(selected_item_name,state)

        await callback.message.delete()
        await callback.message.answer(weights_text, reply_markup=weights_kb, parse_mode='HTML')

    @router.callback_query(F.data.startswith('buy_weight_'), ItemBuy.waiting_for_weight)
    async def buy_weight_selected(callback: types.CallbackQuery, state: FSMContext):
        selected_item_weight = callback.data.split('_')[-1]

        selected_item_photo, selected_item_kb, selected_item_text = await build_confirmation_keyboard(selected_item_weight, state)
        if selected_item_photo is None:
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="🔙Back", callback_data="back_buy_confirmation"))
            await callback.message.edit_text(text="Item not found. Please go back and select a different one.", reply_markup=builder.as_markup())
        else:
            await callback.message.delete()
            await callback.message.answer_photo(photo=selected_item_photo, caption=selected_item_text, reply_markup=selected_item_kb,
                                                parse_mode='HTML')

    @router.callback_query(F.data == "back_bonus_usage", ItemBuy.waiting_for_bonus_decision)
    async def return_to_confirmation(callback: types.CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        selected_item_weight = state_data.get("selected_item_weight")
        selected_item_photo, selected_item_kb, selected_item_text = await build_confirmation_keyboard(selected_item_weight, state)

        await callback.message.delete()
        if selected_item_photo is None:
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="🔙Back", callback_data="back_buy_confirmation"))
            await callback.message.delete()
            await callback.message.anwer(text="Item not found. Please go back and select a different one.", reply_markup=builder.as_markup())
        else:
            await callback.message.answer_photo(photo=selected_item_photo, caption=selected_item_text,
                                                reply_markup=selected_item_kb,
                                                parse_mode='HTML')

    @router.callback_query(F.data == 'buy_confirmation', ItemBuy.waiting_for_confirmation)
    async def buy_complete(callback: types.CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        selected_item_id = state_data.get("selected_item_id")
        selected_item = await get_item_by_id(selected_item_id)
        curr_user = await get_user_by_callback(callback)

        if not curr_user:
            await callback.message.delete()
            await callback.answer("User not registered")
            await state.clear()
            return

        if not selected_item:
            selected_item = await get_new_item(state)
            if not selected_item:
                await callback.message.delete()
                await callback.message.answer("❌ The item was purchased by another user.")
                await state.clear()
                return

        selected_item_photo1 = selected_item.photo1


        # Проверка: хватает ли средств для покупки (без учета бонусов)
        if await can_use_bonus(callback.from_user.id):
            if curr_user.balance + curr_user.bonus_balance < selected_item.price:
                await callback.message.answer("Insufficient funds to complete the purchase.")
                await callback.answer()
                return

        elif curr_user.balance < selected_item.price:
            await callback.message.answer("Insufficient funds to complete the purchase.")
            await callback.answer()
            return

        if curr_user.bonus_balance > 0 and await can_use_bonus(callback.from_user.id):
            # Если у пользователя есть бонусы, спрашиваем, использовать ли их.
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(text="✅ Yes", callback_data="use_bonus_balance"),
                types.InlineKeyboardButton(text="❌ No", callback_data="dont_use_bonus_balance")
            )
            builder.row(types.InlineKeyboardButton(text="🔙 Back", callback_data="back_bonus_usage"))
            builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_buying"))
            # Изменяем текущее сообщение, предлагая выбор использования бонусов.
            current_caption = callback.message.caption
            new_caption = current_caption + "\n\nDo you want to use your bonus balance?"

            await callback.message.answer_photo(selected_item_photo1, new_caption, reply_markup=builder.as_markup())
            await state.set_state(ItemBuy.waiting_for_bonus_decision)
            await callback.answer()
        else:
            # Если бонусов нет, сразу проводим покупку
            new_balance = curr_user.balance - selected_item.price
            await process_purchase(state, callback, new_balance)

    @router.callback_query(F.data == "use_bonus_balance", ItemBuy.waiting_for_bonus_decision)
    async def bonus_used_purchase(callback: types.CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        selected_item_id = state_data.get("selected_item_id")
        selected_item = await get_item_by_id(selected_item_id)
        curr_user = await get_user_by_callback(callback)

        if not curr_user:
            await callback.message.delete()
            await callback.message.answer("User not registered. Please send /start command")
            await state.clear()

        if not selected_item:
            selected_item = await get_new_item(state)
            if not selected_item:
                await callback.message.delete()
                await callback.message.answer("❌ The item was purchased by another user.")
                await state.clear()
                return

        if selected_item.price >= curr_user.bonus_balance:
            new_balance = curr_user.balance - selected_item.price + curr_user.bonus_balance
            await process_purchase(state, callback, new_balance)

        else:
            new_balance = curr_user.balance
            new_bonus_balance = curr_user.bonus_balance - selected_item.price
            await process_purchase(state, callback, new_balance, new_bonus_balance)

    @router.callback_query(F.data == "dont_use_bonus_balance")
    async def bonus_dont_used_purchase(callback: types.CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        selected_item_id = state_data.get("selected_item_id")
        selected_item = await get_item_by_id(selected_item_id)
        curr_user = await get_user_by_callback(callback)

        if not curr_user:
            await callback.message.delete()
            await callback.message.answer("User not registered")
            await state.clear()

        if not selected_item:
            selected_item = await get_new_item(state)
            if not selected_item:
                await callback.message.delete()
                await callback.message.answer("❌ The item was purchased by another user.")
                await state.clear()
                return

        if curr_user.balance < selected_item.price:
            await callback.message.answer("Insufficient funds to complete the purchase.")
            await callback.answer()
            return

        new_balance = curr_user.balance - selected_item.price
        new_bonus_balance = curr_user.bonus_balance

        await process_purchase(state, callback, new_balance, new_bonus_balance)

    @router.callback_query(F.data == "cancel_buying")
    async def cancel_buying(callback: types.CallbackQuery, state: FSMContext):

        await callback.message.delete()
        await state.clear()