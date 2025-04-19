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

# FSM для этапа подтверждения изменения роли
class RoleChange(StatesGroup):
    waiting_for_confirmation = State()

def register_add_role_handlers(router) -> None:
    """
    Регистрирует хэндлеры для команды /add_role.
    Формат команды: /add_role <tg_id_or_username> <role>
    Если пользователь найден и новая роль отличается от текущей,
    выводится сообщение с клавиатурой Confirm/Cancel для подтверждения.
    В противном случае выводится сообщение об ошибке или о том, что роль уже установлена.
    """
    @router.message(Command("add_role"), AdminFilter())
    async def add_role_handler(message: types.Message, state: FSMContext):
        if not message.text:
            await message.answer(
                "Usage: /add_role <tg_id_or_username> <role>\n"
                "Role must be 'admin', 'operator' или 'user'."
            )
            return

        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                "Usage: /add_role <tg_id_or_username> <role>\n"
                "Role must be 'admin', 'operator' или 'user'."
            )
            return

        identifier = parts[1].strip()
        if identifier.startswith('@'):
            identifier = identifier[1:]
        new_role = parts[2].lower()
        if new_role not in ("admin", "operator", "user"):
            await message.answer("Invalid role. Role must be 'admin', 'operator' или 'user'.")
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

        # Если новая роль совпадает с текущей, сразу сообщаем об этом
        if target_user.role.lower() == new_role:
            await message.answer(
                f"У пользователя @{target_user.username} (tg id: {target_user.tg_id}) уже установлена роль '{new_role}'."
            )
            return

        # Формируем сообщение подтверждения с inline клавиатурой
        confirmation_text = (
            f"Вы хотите изменить роль пользователя @{target_user.username} "
            f"(tg id: {target_user.tg_id}) с {target_user.role} на {new_role}?"
        )
        confirmation_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_role"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_role")
            ]
        ])
        await state.update_data(identifier=identifier, new_role=new_role)
        await message.answer(confirmation_text, reply_markup=confirmation_kb)
        await state.set_state(RoleChange.waiting_for_confirmation)

    @router.callback_query(lambda cb: cb.data in ("confirm_role", "cancel_role"), RoleChange.waiting_for_confirmation, AdminFilter())
    async def role_confirmation_callback(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        identifier = data.get("identifier")
        new_role = data.get("new_role")

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

            if callback.data == "cancel_role":
                await callback.message.edit_text("Role change operation cancelled.")
                await state.clear()
                await callback.answer()
                return

            # При подтверждении обновляем роль
            try:
                target_user.role = new_role
                await session.commit()
            except Exception as e:
                logging.info(f"ERROR: {e}")
                await session.rollback()
                await callback.message.answer("An error occurred while changing role, please try again. 🙂")
                return

        await callback.message.edit_text(
            f"Role of user @{target_user.username} (tg id: {target_user.tg_id}) updated to {new_role}."
        )
        await state.clear()
        await callback.answer()
