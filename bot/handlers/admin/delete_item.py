from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select
from database.models import Item
from database.session import async_session
from filters import AdminOperatorFilter


def register_item_delete_handlers(router):
    @router.message(Command("delete_item"), AdminOperatorFilter())
    async def delete_item_command_handler(message: types.Message):
        # Ожидаем, что команда выглядит так: /delete_item {item_id}
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: /delete_item {item_id}")
            return
        try:
            item_id = int(parts[1])
        except ValueError:
            await message.answer("Invalid item ID. Please provide a valid integer.")
            return

        async with async_session() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()

        if not item:
            await message.answer(f"Item with ID {item_id} not found.")
            return

        if item.is_bought:
            await message.answer("You cannot delete an item that has been purchased.")
            return

        # Формируем inline-клавиатуру с кнопками "Confirm" и "Cancel"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_delete_item_{item_id}")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_delete_item")]
        ])

        await message.answer(
            f"Are you sure you want to delete item <b>{item.item_name}</b> (ID: {item_id})?",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    @router.callback_query(F.data.startswith("confirm_delete_item_"), AdminOperatorFilter())
    async def confirm_delete_item_handler(callback: CallbackQuery):
        # Извлекаем item_id из callback data
        try:
            item_id = int(callback.data.split("_")[-1])
        except ValueError:
            await callback.answer("Invalid item ID.", show_alert=True)
            return

        async with async_session() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item: Item = result.scalar_one_or_none()
            if not item:
                await callback.answer("Item not found.", show_alert=True)
                return
            if item.is_bought:
                await callback.answer("You cannot delete an item that has been purchased.", show_alert=True)
                return
            try:
                await session.delete(item)
                await session.commit()
            except Exception as e:
                logging.info(f"ERROR: {e}")
                return

        # Редактируем сообщение, чтобы уведомить пользователя об успешном удалении
        await callback.message.edit_text("Item deleted successfully.")
        await callback.answer()

    @router.callback_query(F.data == "cancel_delete_item", AdminOperatorFilter())
    async def cancel_delete_item_handler(callback: CallbackQuery):
        await callback.message.edit_text("Item deletion canceled.")
        await callback.answer()
