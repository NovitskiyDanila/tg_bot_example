import logging
import math
from typing import Union

from aiogram import F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload

from database.models import Purchase, User, Item
from database.session import async_session
from filters import AdminOperatorFilter
from handlers.user.personal_account import get_personal_account_info


async def build_my_purchases_message(message: Union[CallbackQuery, types.Message], curr_page: int, state, username) -> tuple:
    """
    Формирует сообщение и inline-клавиатуру для отображения депозитов пользователя с пагинацией.

    Пагинация:
      - Если всего страниц 1, то строка с пагинацией не добавляется.
      - Если страница первая: кнопка с текущей страницей/общим числом страниц и кнопка "➡️" для перехода к следующей странице.
      - Если страница не первая и не последняя: кнопки "⬅️", текущая страница/общие страницы, "➡️".
      - Если страница последняя: кнопка "⬅️" и кнопка с текущей страницей/общим числом страниц.

    Депозиты будут выводиться построчно (например, 6 депозитов на страницу, по 2 в ряду).

    Возвращает кортеж: (message_text, keyboard)
    """

    async with async_session() as session:

        curr_user_result = await session.execute(select(User).where(User.username.ilike(username)))
        curr_user: User = curr_user_result.scalar_one_or_none()

        curr_user_purchases_result = await session.execute(select(Purchase).where(Purchase.user_id == curr_user.id).order_by(desc(Purchase.id)))
        curr_user_purchases = curr_user_purchases_result.scalars().all()

    if curr_user_purchases:
        total_purchases = len(curr_user_purchases)
        per_page = 4
        total_pages = math.ceil(total_purchases / per_page)

        message_text = f"<b>💰 Purchases by user @{username}</b>"

        start_index = (curr_page - 1) * per_page
        end_index = start_index + per_page
        purchases_on_page = curr_user_purchases[start_index:end_index]

        # Формируем текст сообщения для депозитов


        # Добавляем кнопки для каждого депозита (2 кнопки в ряду)

        builder = InlineKeyboardBuilder()

        # Добавляем первую строку с пагинацией, если страниц больше одной.
        if total_pages > 1:
            if curr_page == 1:
                builder.row(
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop"),
                    InlineKeyboardButton(text="➡️", callback_data=f"user_purchases_page_{curr_page + 1}")
                )
            elif curr_page == total_pages:
                builder.row(
                    InlineKeyboardButton(text="⬅️", callback_data=f"user_purchases_page_{curr_page - 1}"),
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop")
                )
            else:
                builder.row(
                    InlineKeyboardButton(text="⬅️", callback_data=f"user_purchases_page_{curr_page - 1}"),
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop"),
                    InlineKeyboardButton(text="➡️", callback_data=f"user_purchases_page_{curr_page + 1}")
                )

        # Добавляем кнопки депозитов, по одной кнопке в ряду.
        for purchase in purchases_on_page:
            async with async_session() as session:
                purchased_item_result = await session.execute(select(Item).where(Item.id == purchase.item_id))
                purchased_item = purchased_item_result.scalar_one_or_none()
            btn_text = f"🛍 {purchased_item.item_name} {purchased_item.weight} "
            builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"user_purchase_detail_{purchase.id}"))

        # Добавляем кнопку "Back"
        builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_user_purchase_selected"))
        state_data = await state.get_data()
        photo2_message = state_data.get("photo2_message")
        if photo2_message:
            try:
                if isinstance(message, CallbackQuery):
                    chat_id = message.message.chat.id
                else:
                    chat_id = message.chat.id
                await message.bot.delete_message(chat_id, photo2_message)
            except Exception as e:
                logging.info(f"ERROR: {e}")
                pass

        photo3_message = state_data.get("photo3_message")
        if photo3_message:
            try:
                if isinstance(message, CallbackQuery):
                    chat_id = message.message.chat.id
                else:
                    chat_id = message.chat.id
                await message.bot.delete_message(chat_id, photo3_message)
            except Exception as e:
                logging.info(f"ERROR: {e}")
                pass
        photo4_message = state_data.get("photo4_message")
        if photo4_message:
            try:
                if isinstance(message, CallbackQuery):
                    chat_id = message.message.chat.id
                else:
                    chat_id = message.chat.id
                await message.bot.delete_message(chat_id, photo4_message)
            except Exception as e:
                logging.info(f"ERROR: {e}")
                pass
        if isinstance(message, CallbackQuery):
            await message.message.delete()
            await message.message.answer(text=message_text, reply_markup=builder.as_markup(), parse_mode='HTML')
        else:
            await message.answer(text=message_text, reply_markup=builder.as_markup(), parse_mode='HTML')
    else:
        deposits_message = f"<b>Unfortunately, user {username} dont have any purchases 😔</b>"
        await message.answer(text=deposits_message, parse_mode='HTML')


def register_user_purchases_handlers(router) -> None:

    @router.message(Command("check_purchases"), AdminOperatorFilter())
    async def user_purchases_handler(message: types.Message, state: FSMContext):
        if not message.text:
            await message.answer("Usage: /check_purchases <username> ")
        parts = message.text.split(maxsplit=1)
        if not parts:
            await message.answer("Usage: /check_purchases <username>")
            return
        username = parts[1].strip()
        if username.startswith('@'):
            username = username[1:]
        await state.update_data(username=username)
        await state.update_data(curr_page=1)
        await build_my_purchases_message(message, curr_page=1, state=state, username=username)

    @router.callback_query(F.data.startswith("user_purchase_detail_"), AdminOperatorFilter())
    async def purchase_details_handler(callback: CallbackQuery, state: FSMContext):
        purchase_id = int(callback.data.split("_")[-1])
        state_data = await state.get_data()
        curr_page = state_data.get("curr_page")
        async with async_session() as session:
            result = await session.execute((
                select(Purchase, Item)
                .join(Item, Purchase.item_id == Item.id)
                .where(Purchase.id == purchase_id)
            ))
            rows = result.all()
            if rows:
                for purchase, item in rows:
                    curr_message_text = ("*** PURCHASE DETAILS ***\n\n"
                                         f"<b>Purchase ID:</b> <code>{purchase.id}</code>\n"
                                         f"<b>Item name:</b> {item.item_name}\n"
                                         f"<b>Item area:</b> {item.area}\n"
                                         f"<b>Item weight:</b> {item.weight}\n"
                                         f"<b>Item location description:</b> {item.description2}\n"
                                         f"<b>Item price:</b> {float(item.price/100)}$\n"
                                         f"<b>Purchase date:</b> {item.purchase_date}\n")

                    builder = InlineKeyboardBuilder()
                    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data=f"user_purchases_page_{curr_page}"))
                    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_user_purchase_selected"))

                    try:
                        await callback.message.delete()
                    except Exception as e:
                        pass
                    await callback.message.answer_photo(item.photo1, caption=curr_message_text,
                                                        reply_markup=builder.as_markup(), parse_mode='HTML')

                    if item.photo2:
                        msg = await callback.message.answer_photo(item.photo2)
                        await state.update_data(photo2_message=msg.message_id)
                    if item.photo3:
                        msg = await callback.message.answer_photo(item.photo3)
                        await state.update_data(photo3_message=msg.message_id)
                    if item.photo4:
                        msg = await callback.message.answer_photo(item.photo4)
                        await state.update_data(photo4_message=msg.message_id)
            else:
                curr_message_text = "⚠️ Purchase not found!"
                await callback.message.answer(text=curr_message_text)

    @router.callback_query(F.data.startswith("user_purchases_page_"), AdminOperatorFilter())
    async def back_to_purchases_page(callback: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        curr_page = int(callback.data.split("_")[-1])
        await state.update_data(curr_page=curr_page)
        username = state_data.get("username")
        try:
            await build_my_purchases_message(callback, curr_page, state, username)
        except Exception as e:
            await state.clear()
            logging.info(f"BACK HANDLE ERROR: {e}")
            await callback.message.delete()
            await callback.message.answer("⚠️Something went wrong. Please try again later.")

    @router.callback_query(F.data == "cancel_user_purchase_selected", AdminOperatorFilter())
    async def cancel_purchase_watching(callback: CallbackQuery, state: FSMContext):
        state_data = await state.get_data()
        photo2_message = state_data.get("photo2_message")
        if photo2_message:
            try:
                await callback.bot.delete_message(callback.message.chat.id, photo2_message)
            except Exception as e:
                pass

        photo3_message = state_data.get("photo3_message")
        if photo3_message:
            try:
                await callback.bot.delete_message(callback.message.chat.id, photo3_message)
            except Exception as e:
                pass
        photo4_message = state_data.get("photo4_message")
        if photo4_message:
            try:
                await callback.bot.delete_message(callback.message.chat.id, photo4_message)
            except Exception as exx:
                pass

        await callback.message.delete()
        await state.clear()

