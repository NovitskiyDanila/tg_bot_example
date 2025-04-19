import asyncio
import logging

import aiohttp
from aiogram import types, F, Bot
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update

from config import API_URL, headers, ssl_context
from database.session import async_session
from database.models import Deposit, User


logger = logging.getLogger(__name__)

monitor_tasks = {}

# FSM для депозита
class DepositState(StatesGroup):
    waiting_for_amount = State()


def build_cancel_keyboard(deposit_id):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_deposit_{deposit_id}")
    )
    return builder.as_markup()


async def monitor_deposit_status_background(deposit_id: int, user_id: int, amount: int):
    """
    Фоновая задача, которая периодически проверяет статус депозита, созданного до запуска.
    Логика такая же, как и в основной функции, но без отправки сообщений пользователю,
    а только обновление статуса депозита в БД.
    """
    api_url = f"{API_URL}/api/deposit/status?deposit_id={deposit_id}"
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(10)
            async with session.get(api_url, headers=headers, ssl=ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get("status")
                    logging.info(f"Deposit {deposit_id} status: {status}")
                    if status != "pending":
                        if status == "confirmed":
                            async with async_session() as db_session:
                                try:
                                    deposit_query = await db_session.execute(
                                        select(Deposit).where(Deposit.api_deposit_id == deposit_id)
                                    )
                                    curr_deposit: Deposit = deposit_query.scalar_one_or_none()
                                    if curr_deposit:
                                        curr_deposit.status = "confirmed"

                                    user_query = await db_session.execute(
                                        select(User).where(User.id == user_id)
                                    )
                                    curr_user: User = user_query.scalar_one_or_none()

                                    if curr_user:
                                        if curr_user.referrer_id:
                                            first_level_referrer_query = await db_session.execute(
                                                select(User).where(User.id == curr_user.referrer_id)
                                            )
                                            first_level_referrer: User = first_level_referrer_query.scalar_one_or_none()
                                            if first_level_referrer:
                                                first_level_referrer.bonus_balance += int(amount / 10)

                                                if first_level_referrer.referrer_id:
                                                    second_level_referrer_query = await db_session.execute(
                                                        select(User).where(User.id == first_level_referrer.referrer_id)
                                                    )
                                                    second_level_referrer: User = second_level_referrer_query.scalar_one_or_none()
                                                    if second_level_referrer:
                                                        second_level_referrer.bonus_balance += int(amount * 3 / 100)

                                        curr_user.balance += amount
                                    await db_session.commit()
                                except Exception as deposit_confirm_exception:
                                    await db_session.rollback()
                                    logging.info(f"DEPOSIT ERROR for deposit {deposit_id}: {deposit_confirm_exception}")
                                break

                        elif status == "expired":
                            async with async_session() as db_session:
                                try:
                                    deposit_query = await db_session.execute(
                                        select(Deposit).where(Deposit.api_deposit_id == deposit_id)
                                    )
                                    curr_deposit: Deposit = deposit_query.scalar_one_or_none()
                                    if curr_deposit:
                                        curr_deposit.status = "expired"
                                    await db_session.commit()
                                except Exception as e:
                                    await db_session.rollback()
                                    logging.info(f"Expired status writing ERROR for deposit {deposit_id}: {e}")
                                break

                        elif status == "canceled":
                            async with async_session() as db_session:
                                try:
                                    deposit_query = await db_session.execute(
                                        select(Deposit).where(Deposit.api_deposit_id == deposit_id)
                                    )
                                    curr_deposit: Deposit = deposit_query.scalar_one_or_none()
                                    if curr_deposit:
                                        curr_deposit.status = "canceled"
                                    await db_session.commit()
                                except Exception as e:
                                    await db_session.rollback()
                                    logging.info(f"Canceled status writing ERROR for deposit {deposit_id}: {e}")
                                break
                else:
                    logging.error(f"Error retrieving deposit status for deposit {deposit_id}: HTTP {response.status}")
                    break
    # Убираем задачу из глобального кэша, если используется
        monitor_tasks.pop(deposit_id, None)

async def monitor_deposit_status(deposit_id: int, user_id: int, bot: Bot, amount: int, deposit_message: Message, state: FSMContext):
    """Фоновая задача, которая периодически проверяет статус депозита."""
    # Здесь ваш код для опроса API, например:
    api_url = f"{API_URL}/api/deposit/status?deposit_id={deposit_id}"
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(10)
            async with session.get(api_url, headers=headers, ssl=ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get("status")
                    logging.info(f"Deposit status: {status}")
                    if status != "pending":
                        if status == "confirmed":
                            async with async_session() as db_session:
                                try:
                                    deposit_query = await db_session.execute(select(Deposit).where(Deposit.api_deposit_id==deposit_id))
                                    curr_deposit: Deposit = deposit_query.scalar_one_or_none()
                                    curr_deposit.status = "confirmed"

                                    user_query = await db_session.execute(select(User).where(User.tg_id == user_id))
                                    curr_user: User = user_query.scalar_one_or_none()

                                    if curr_user:
                                        if curr_user.referrer_id:
                                            first_level_referrer_query = await db_session.execute(select(User).where(User.id == curr_user.referrer_id))
                                            first_level_referrer: User = first_level_referrer_query.scalar_one_or_none()
                                            first_level_referrer.bonus_balance = first_level_referrer.bonus_balance + amount * 10

                                            if first_level_referrer.referrer_id:
                                                second_level_referrer_query = await db_session.execute(select(User).where(User.id == first_level_referrer.referrer_id))
                                                second_level_referrer: User = second_level_referrer_query.scalar_one_or_none()
                                                second_level_referrer.bonus_balance = second_level_referrer.bonus_balance + amount * 3

                                        curr_user.balance = curr_user.balance + amount * 100
                                        await db_session.commit()

                                except Exception as deposit_confirm_exception:
                                    await db_session.rollback()
                                    logging.info(f"DEPOSIT ERROR: {deposit_confirm_exception}")
                                    confirmation_error_message = (
                                        "✅ *Deposit Confirmed!*\n\n"
                                        "However, an error occurred while adding funds to your balance.\n\n"
                                        f"Please contact support and provide your Deposit ID: <b>{deposit_id}</b>.\n\n"
                                        "You can find the operator's contact by clicking the <b>Help</b> button in the main menu."
                                    )
                                    try:
                                        await deposit_message.delete()
                                    except Exception as e:
                                        continue
                                    await bot.send_message(user_id, text=confirmation_error_message, parse_mode='HTML')
                                    await state.clear()
                                    break

                            confirmation_message = (f"✅ Deposit Confirmed!\n\n"
                                                    f"Your deposit of <b>{amount}$</b> has been successfully credited to your balance.")
                            await deposit_message.delete()
                            await bot.send_message(user_id, text=confirmation_message, parse_mode='HTML')
                            await state.clear()
                            break

                        if status == "expired":
                            expired_message = (
                                "⚠️ <b>Deposit Expired!</b>\n\n"
                                "Your deposit has expired and has been cancelled.\n\n"
                                "<b>Please DO NOT SEND ANY FUNDS to this wallet address.</b>\n\n"
                                "<b>If you have already transferred funds</b>, please contact support and provide your DEPOSIT ID for further investigation.\n\n"
                                "You can find the operator's contact details by clicking the <b>Help</b> button in the main menu.\n\n"
                                f"<b>DEPOSIT ID: {deposit_id}</b>"
                            )
                            async with async_session() as db_session:
                                try:
                                    deposit_query = await db_session.execute(select(Deposit).where(Deposit.api_deposit_id == deposit_id))
                                    curr_deposit: Deposit = deposit_query.scalar_one_or_none()
                                    curr_deposit.status = "expired"
                                    await db_session.commit()
                                    try:
                                        await deposit_message.delete()
                                        await bot.send_message(user_id, text=expired_message, parse_mode='HTML')
                                    except Exception as e:
                                        pass
                                    await state.clear()
                                    break
                                except Exception as e:
                                    await db_session.rollback()
                                    logging.info(f"Expired status writing ERROR: {e}")
                                    await bot.send_message(user_id, text=expired_message, parse_mode='HTML')
                                    await state.clear()
                                    break
                        if status == "canceled":
                            canceled_message = "⚠️ Deposit cancelled successfully."
                            async with async_session() as db_session:
                                try:
                                    deposit_query = await db_session.execute(select(Deposit).where(Deposit.api_deposit_id == deposit_id))
                                    curr_deposit: Deposit = deposit_query.scalar_one_or_none()
                                    curr_deposit.status = "canceled"
                                    await db_session.commit()
                                    await state.clear()
                                    break
                                except Exception as e:
                                    await db_session.rollback()
                                    logging.info(f"Expired status writing ERROR: {e}")
                                    await bot.send_message(user_id, text=canceled_message, parse_mode='HTML')
                                    await state.clear()
                                    break
                else:
                    await bot.send_message(user_id, "Error retrieving deposit status.")
                    await state.clear()
                    break
    monitor_tasks.pop(deposit_id, None)


async def monitor_existing_pending_deposits():
    async with async_session() as session:
        result = await session.execute(select(Deposit).where(Deposit.status == "pending"))
        pending_deposits = result.scalars().all()
    for deposit in pending_deposits:
        task = asyncio.create_task(
            monitor_deposit_status_background(
                deposit_id=deposit.api_deposit_id,
                user_id=deposit.user_id,
                amount=deposit.amount
            )
        )
        monitor_tasks[deposit.api_deposit_id] = task



def register_deposit_handlers(router) -> None:
    @router.callback_query(F.data == "deposit")
    async def deposit_setup(callback: types.CallbackQuery, state: FSMContext):

        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_entering_amount"))
        await callback.message.answer("Enter the deposit amount (an integer > 0):", reply_markup=builder.as_markup())
        await state.set_state(DepositState.waiting_for_amount)
        await callback.answer()  # закрываем алерт

    @router.message(DepositState.waiting_for_amount)
    async def deposit_amount_handler(message: types.Message, state: FSMContext):
        if message.text:
            try:
                deposit_amount = int(message.text.strip())
            except ValueError:
                await message.answer("⚠️ Please enter a valid integer for the amount.")
                return
        else:
            await message.answer("⚠️ Please enter a valid integer for the amount.")
            return

        if deposit_amount <= 0:
            await message.answer("⚠️ The amount must be greater than 0.")
            return


        msg = await message.answer("⏳Creating a transaction...⏳")

        url = f"{API_URL}/api/deposit"
        deposit_data = {"amount": deposit_amount, "user_tg_id": message.from_user.id}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=deposit_data, headers=headers, ssl=ssl_context) as response:
                if response.status == 200:
                    response_data: dict = await response.json()
                    deposit_id = response_data.get("deposit_id")
                    wallet_public_key = response_data.get("wallet_public_key")
                    amount = response_data.get("amount")
                    expires_at = response_data.get("expires_at")
                    async with async_session() as db_session:
                        try:
                            curr_user_request = await db_session.execute(select(User).where(User.tg_id==message.from_user.id))
                            curr_user = curr_user_request.scalar_one_or_none()
                            new_deposit = Deposit(user_id=curr_user.id,
                                                  api_deposit_id=deposit_id,
                                                  amount=deposit_amount*100,
                                                  status="pending")
                            db_session.add(new_deposit)
                            await db_session.commit()
                        except Exception as e:
                            logger.info(f"Error during creating deposit transaction: {e}")
                            await db_session.rollback()
                            await message.delete()
                            deposit_error_message = "⚠️ <b>An error occurred during deposit creation.</b>Please try again later."
                            await message.answer(text=deposit_error_message, parse_mode='HTML')
                            return

                    deposit_message = (
                        f"🆔 <b>Deposit ID:</b> <code>{deposit_id}</code>\n"
                        f"🔹 <b>*** DEPOSIT DETAILS ***</b> 🔹\n\n"
                        f"💰 <b>>Amount:</b> <code>{amount}</code> $USDT\n"
                        f"🏦 <b>Wallet Address:</b> <code>{wallet_public_key}</code>\n"
                        f"🌐 <b>Network:</b> TRC20\n\n"
                        f"⚠️ <b>Deposit expires at:</b> {expires_at}UTC\n"
                        f"🚨 <b>Ensure you send the exact amount to the specified wallet address</b>\n\n"
                        f"✅ Once the transaction is confirmed, your balance will be updated.\n\n"
                        f"❌ If you changed your mind and have not made the transfer, press the <b>Cancel</b> button."
                    )

                    info_message = await msg.edit_text(text=deposit_message, reply_markup=build_cancel_keyboard(deposit_id), parse_mode="HTML")

                    task = asyncio.create_task(monitor_deposit_status(deposit_id, message.from_user.id, message.bot, deposit_amount, info_message, state))
                    monitor_tasks[deposit_id] = task
                elif response.status == 409:
                    response_data: dict = await response.json()
                    deposit_id = response_data.get("deposit_id")
                    wallet_public_key = response_data.get("wallet_public_key")
                    amount = response_data.get("amount")
                    expires_at = response_data.get("expires_at")

                    deposit_message = (
                        "⚠️ <b>EXISTING DEPOSIT FOUND</b>\n\n"
                        "You already have an active deposit with the following details:\n"
                        f"🆔 <b>Deposit ID:</b> <code>{deposit_id}</code>\n"
                        f"💰 <b>>Amount:</b> <code>{amount}</code> $USDT\n"
                        f"🏦 <b>Wallet Address:</b> <code>{wallet_public_key}</code>\n"
                        f"🌐 <b>Network:</b> TRC20\n\n"
                        f"⚠️ <b>Deposit expires at:</b> {expires_at}UTC\n"
                        f"🚨 <b>Ensure you send the exact amount to the specified wallet address</b>\n\n"
                        f"✅ Once the transaction is confirmed, your balance will be updated.\n\n"
                        f"❌ If you changed your mind and have not made the transfer, press the <b>Cancel</b> button."
                    )

                    info_message = await msg.edit_text(text=deposit_message,
                                                       reply_markup=build_cancel_keyboard(deposit_id),
                                                       parse_mode="HTML")
                    task = monitor_tasks.get(deposit_id)
                    if task is not None:
                        task.cancel()
                    task = asyncio.create_task(monitor_deposit_status(deposit_id, message.from_user.id, message.bot, deposit_amount, info_message, state))
                    monitor_tasks[deposit_id] = task

                else:
                    logger.info("Deposit request ERROR: WRONG STATUS ")
                    error_message = "⚠️Something went wrong. Please try again later."
                    await msg.edit_text(text=error_message, parse_mode=None)
                    await state.clear()
                    return

    @router.callback_query(F.data.startswith("cancel_deposit_"))
    async def cancel_deposit(callback: types.CallbackQuery, state: FSMContext):
        try:
            deposit_id = int(callback.data.split("_")[-1])
        except Exception as e:
            await callback.message.answer("⚠️ An unexpected error occurred while cancelling the deposit.")
            logging.info(f"Callback ERROR: {e}")
            return

        cancel_url = f"{API_URL}/api/deposit/cancel"
        payload = {"deposit_id": deposit_id}
        async with aiohttp.ClientSession() as session:
            async with session.post(cancel_url, json=payload, headers=headers, ssl=ssl_context) as response:
                if response.status == 200:
                    await state.clear()
                    canceled_message = "⚠️ Deposit cancelled successfully."
                    try:
                        await callback.message.delete()
                        await callback.message.answer( text=canceled_message, parse_mode='HTML')
                    except Exception as e:
                        pass
                else:
                    await callback.message.answer("⚠️ An unexpected error occurred while cancelling the deposit.")

    @router.callback_query(F.data == "cancel_entering_amount")
    async def cancel_deposit_amount(callback: types.callback_query, state: FSMContext):
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("⚠️ Deposit cancelled successfully.")
