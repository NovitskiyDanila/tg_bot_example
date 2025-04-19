import logging
import math

from aiogram import F, types
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, desc

from database.models import Deposit, User
from database.session import async_session
from handlers.user.personal_account import get_personal_account_info


async def build_my_deposits_message(callback: CallbackQuery, curr_page: int):
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

        curr_user_result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        curr_user: User = curr_user_result.scalar_one_or_none()

        curr_user_deposits_result = await session.execute(
            select(Deposit).where(Deposit.user_id == curr_user.id).order_by(desc(Deposit.id)))
        curr_user_deposits = curr_user_deposits_result.scalars().all()

    if curr_user_deposits:
        total_deposits = len(curr_user_deposits)
        per_page = 4
        total_pages = math.ceil(total_deposits / per_page)

        message_text = "<b>💰 Your Deposits</b>"

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
                    InlineKeyboardButton(text="➡️", callback_data=f"my_deposits_page_{curr_page + 1}")
                )
            elif curr_page == total_pages:
                builder.row(
                    InlineKeyboardButton(text="⬅️", callback_data=f"my_deposits_page_{curr_page - 1}"),
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop")
                )
            else:
                builder.row(
                    InlineKeyboardButton(text="⬅️", callback_data=f"my_deposits_page_{curr_page - 1}"),
                    InlineKeyboardButton(text=f"📄 {curr_page}/{total_pages}", callback_data="noop"),
                    InlineKeyboardButton(text="➡️", callback_data=f"my_deposits_page_{curr_page + 1}")
                )

        # Добавляем кнопки депозитов, по одной кнопке в ряду.
        for dep in deposits_on_page:
            btn_text = f"💰 Deposit ID: {dep.id} ({dep.status})"
            builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"deposit_detail_{dep.id}"))

        # Добавляем кнопку "Back"
        builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu"))

        await callback.message.edit_text(text= message_text, reply_markup=builder.as_markup(), parse_mode='HTML')
    else:
        deposits_message = "<b>Unfortunately, you dont have any deposits 😔</b>"
        await callback.message.answer(text=deposits_message, parse_mode='HTML')


def register_my_deposits_handlers(router) -> None:

    @router.callback_query(F.data == "my_deposits")
    async def my_deposits_handler(callback: CallbackQuery , state: FSMContext):
        await state.update_data(curr_page=1)
        await build_my_deposits_message(callback, curr_page=1)

    @router.callback_query(F.data.startswith("deposit_detail_"))
    async def deposit_details_handler(callback: CallbackQuery, state: FSMContext):
        deposit_id = int(callback.data.split("_")[-1])
        state_data = await state.get_data()
        curr_page = state_data.get("curr_page")
        async with async_session() as session:
            curr_deposit_result = await session.execute(select(Deposit).where(Deposit.id == deposit_id))
            curr_deposit: Deposit = curr_deposit_result.scalar_one_or_none()
            if curr_deposit:
                curr_message_text = ("*** DEPOSIT DETAILS ***\n\n"
                                     f"<b>Deposit ID:</b> <code>{curr_deposit.api_deposit_id}</code>\n"
                                     f"<b>Deposit Amount:</b> {float(curr_deposit.amount/100)}$\n"
                                     f"<b>Deposit Status:</b> {curr_deposit.status}\n")
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data=f"my_deposits_page_{curr_page}"))
                builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_my_deposits"))
                await callback.message.edit_text(text=curr_message_text, reply_markup=builder.as_markup(), parse_mode='HTML')
            else:
                curr_message_text = "⚠️ Deposit not found!"
                await callback.message.answer(text=curr_message_text)

    @router.callback_query(F.data.startswith("my_deposits_page_"))
    async def back_to_deposits_page(callback: CallbackQuery, state: FSMContext):
        page_number = int(callback.data.split("_")[-1])
        await state.update_data(curr_page=page_number)
        try:
            await build_my_deposits_message(callback, page_number)
        except Exception as e:
            logging.info(f"BACK HANDLE ERROR: {e}")
            await callback.message.delete()
            await callback.message.answer("⚠️Something went wrong. Please try again later.")

    @router.callback_query(F.data == "main_menu")
    async def return_personal_account(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == user_id))
            user = result.scalar_one_or_none()
        if not user:
            await callback.message.edit_text("User not found. Please, send /start")
            await callback.answer()
            return
        text, kb = await get_personal_account_info(user, callback.bot)
        await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
