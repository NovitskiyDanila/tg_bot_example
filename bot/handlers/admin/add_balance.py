import logging
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.session import async_session
from database.models import User
from filters.admin_filter import AdminFilter

logger = logging.getLogger(__name__)


# FSM для этапа изменения баланса
class BalanceChange(StatesGroup):
    waiting_for_confirmation = State()

def register_add_balance_handlers(router) -> None:
    """
    Регистрирует хэндлеры для команды /add_balance.
    Формат команды: /add_balance <tg_id_or_username> <amount>
    Если пользователь найден и amount является целым числом, выводится сообщение с клавиатурой Confirm/Cancel,
    где текст зависит от знака amount:
      - Если amount > 0: "Вы хотите добавить на баланс пользователя ..."
      - Если amount < 0: "Вы хотите списать с баланса пользователя ..."
    """
    @router.message(Command("add_balance"), AdminFilter())
    async def add_balance_handler(message: types.Message, state: FSMContext):
        if not message.text:
            await message.answer(
                "Usage: /add_balance <tg_id_or_username> <amount>\n"
                "Amount must be an integer (positive to add, negative to subtract)."
            )
            return

        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                "Usage: /add_balance <tg_id_or_username> <amount>\n"
                "Amount must be an integer (positive to add, negative to subtract)."
            )
            return

        identifier = parts[1].strip()
        if identifier.startswith('@'):
            identifier = identifier[1:]
        try:
            amount = int(parts[2])
        except ValueError:
            await message.answer("Invalid amount. Amount must be an integer.")
            return

        async with async_session() as session:
            if identifier.isdigit():
                query = select(User).where(User.tg_id == int(identifier))
            else:
                query = select(User).where(User.username.ilike(identifier))
            result = await session.execute(query)
            target_user = result.scalar_one_or_none()

        if not target_user:
            await message.answer("User with this identifier not found.")
            return

        # Формируем текст подтверждения в зависимости от знака amount
        if amount > 0:
            action_text = f"добавить на баланс пользователю"
            amount_text = f"{amount}$"
        else:
            action_text = f"списать с баланса пользователя"
            amount_text = f"{abs(amount)}$"

        confirmation_text = (
            f"Вы хотите {action_text}  @{target_user.username} "
            f"(tg id: {target_user.tg_id}) {amount_text}?"
        )

        confirmation_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_balance"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_balance")
            ]
        ])

        await state.update_data(identifier=identifier, amount=amount)
        await message.answer(confirmation_text, reply_markup=confirmation_kb)
        await state.set_state(BalanceChange.waiting_for_confirmation)

    @router.callback_query(lambda cb: cb.data in ("confirm_balance", "cancel_balance"), BalanceChange.waiting_for_confirmation, AdminFilter())
    async def balance_confirmation_callback(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        identifier = data.get("identifier")
        amount = data.get("amount")

        async with async_session() as session:
            if identifier.isdigit():
                query = select(User).where(User.tg_id == int(identifier))
            else:
                query = select(User).where(User.username.ilike(identifier))
            result = await session.execute(query)
            target_user = result.scalar_one_or_none()
            if not target_user:
                await callback.message.edit_text("User not found in DB.")
                await state.clear()
                await callback.answer()
                return

            if callback.data == "cancel_balance":
                await callback.message.edit_text("Balance change operation cancelled.")
                await state.clear()
                await callback.answer()
                return

            # При подтверждении обновляем баланс пользователя
            # Предположим, что у пользователя есть поле balance (целое число или float)
            try:
                target_user.balance = target_user.balance + amount * 100
                await session.commit()
            except Exception as e:
                logging.info(f"ERROR: {e}")
                await session.rollback()
                await callback.message.answer("An error occurred while changing balance, please try again. 🙂")

        await callback.message.edit_text(
            f"Balance of user @{target_user.username} (tg id: {target_user.tg_id}) updated by {amount}$."
        )
        await state.clear()
        await callback.answer()
