import logging
import math

from typing import Union

import aiohttp
from aiogram import F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, desc

from config import API_URL, headers, ssl_context
from database.models import Deposit, User
from database.session import async_session
from filters import AdminOperatorFilter
from handlers.user.personal_account import get_personal_account_info


async def build_my_deposits_message(message: Union[types.Message, CallbackQuery], curr_page: int, username: str):
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

        curr_user_deposits_result = await session.execute(
            select(Deposit).where(Deposit.user_id == curr_user.id).order_by(desc(Deposit.id)))
        curr_user_deposits = curr_user_deposits_result.scalars().all()

    if curr_user_deposits:
        total_deposits = len(curr_user_deposits)
        per_page = 4
        total_pages = math.ceil(total_deposits / per_page)

        message_text = f"<b>💰 Deposits by user @{curr_user.username} </b>"

        start_index = (curr_page - 1) * per_page
        end_index = start_index + per_page
        deposits_on_page = curr_user_deposits[start_index:end_index]

        # Формируем текст сообщения для депозитов


        # Добавляем кнопки для каждого депозита (2 кнопки в ряду)

        builder = InlineKeyboardBuilder()

        # Добавляем первую строку с пагинацией, если страниц больше одной.
        if total_pages > 1:
            if curr_page == 1:
                builder.row(
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop"),
                    InlineKeyboardButton(text="➡️", callback_data=f"user_deposits_page_{curr_page + 1}")
                )
            elif curr_page == total_pages:
                builder.row(
                    InlineKeyboardButton(text="⬅️", callback_data=f"user_deposits_page_{curr_page - 1}"),
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop")
                )
            else:
                builder.row(
                    InlineKeyboardButton(text="⬅️", callback_data=f"user_deposits_page_{curr_page - 1}"),
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop"),
                    InlineKeyboardButton(text="➡️", callback_data=f"user_deposits_page_{curr_page + 1}")
                )

        # Добавляем кнопки депозитов, по одной кнопке в ряду.
        for dep in deposits_on_page:
            btn_text = f"💰 Deposit ID: {dep.id} ({dep.status})"
            builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"user_deposit_detail_{dep.api_deposit_id}"))

        # Добавляем кнопку "Back"
        builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_viewing_deposit"))
        if isinstance(message, types.Message):
            await message.answer(text=message_text, reply_markup=builder.as_markup(), parse_mode='HTML')
        elif isinstance(message, CallbackQuery):
            await message.answer()
            await message.message.edit_text(text=message_text, reply_markup=builder.as_markup(), parse_mode='HTML')
    else:
        deposits_message = "<b>Unfortunately, user dont have any deposits 😔</b>"
        await message.answer(text=deposits_message, parse_mode='HTML')


def register_check_users_deposits_handlers(router) -> None:

    @router.message(Command("check_deposits"), AdminOperatorFilter())
    async def user_deposits_handler(message: types.Message, state: FSMContext):
        if not message.text:
            await message.answer("Usage: /check_deposits <username>")
            return
        parts = message.text.split(maxsplit=1)
        if not parts:
            await message.answer("Usage: /check_deposits <username>")
            return
        username = parts[1].strip()
        if username.startswith('@'):
            username = username[1:]
        await state.update_data(username=username)
        await state.update_data(curr_page=1)
        await build_my_deposits_message(message, curr_page=1, username=username)

    @router.callback_query(F.data.startswith("user_deposit_detail_"), AdminOperatorFilter())
    async def deposit_details_handler(callback: CallbackQuery, state: FSMContext):
        deposit_id = int(callback.data.split("_")[-1])
        state_data = await state.get_data()
        curr_page = state_data.get("curr_page")
        request_url = f"{API_URL}/api/deposit/detail"
        params = {"deposit_id": deposit_id}
        async with aiohttp.ClientSession() as session:
            try:
                # Здесь используем GET-запрос с передачей query-параметров
                async with session.get(request_url, params=params, headers=headers, ssl=ssl_context) as response:
                    if response.status != 200:
                        logging.error(f"HTTP error {response.status} while fetching deposit details")
                        await callback.message.answer("Error fetching deposit details")
                        return
                    deposit_data = await response.json()
            except Exception as e:
                logging.error(f"Exception while fetching deposit details: {e}")
                await callback.message.answer("Error fetching deposit details")
                return
            deposit_id = deposit_data.get("deposit_id")
            wallet_public_key = deposit_data.get("wallet_public_key")
            initial_balance = deposit_data.get("wallet_initial_balance")
            deposit_amount = deposit_data.get("deposit_amount")
            expires_time = deposit_data.get("expires_time")
            status = deposit_data.get("status")
            curr_message_text = ("*** DEPOSIT DETAILS ***\n\n"
                                 f"<b>Deposit ID:</b> <code>{deposit_id}</code>\n"
                                 f"<b>Deposit wallet: <code>{wallet_public_key}</code></b>\n"
                                 f"<b>Balance of wallet before deposit</b>: {initial_balance}\n"
                                 f"<b>Deposit Amount:</b> {deposit_amount}$\n"
                                 f"<b>Deposit expiration time:</b> {expires_time}\n"
                                 f"<b>Deposit status:</b> {status} ")
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data=f"user_deposits_page_{curr_page}"))
            builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_viewing_deposit"))
            await callback.answer()
            await callback.message.edit_text(text=curr_message_text, reply_markup=builder.as_markup(), parse_mode='HTML')

    @router.callback_query(F.data.startswith("user_deposits_page_"), AdminOperatorFilter())
    async def back_to_deposits_page(callback: CallbackQuery, state: FSMContext):
        page_number = int(callback.data.split("_")[-1])
        await state.update_data(curr_page=page_number)
        state_data = await state.get_data()
        username = state_data.get("username")
        try:
            await build_my_deposits_message(callback, page_number, username)
        except Exception as e:
            logging.info(f"BACK HANDLE ERROR: {e}")
            await callback.message.delete()
            await callback.message.answer("⚠️Something went wrong. Please try again later.")

    @router.callback_query(F.data == "cancel_viewing_deposit", AdminOperatorFilter())
    async def cancel_viewing_deposit(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.answer()
        await callback.message.delete()
        return
