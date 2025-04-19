from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select
from database.models import ItemCategory, Item
from database.session import async_session
from filters import AdminOperatorFilter


def register_delete_category_handlers(router):

    @router.message(Command("delete_category"), AdminOperatorFilter())
    async def delete_category_command_handler(message: types.Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: /delete_category <category_id>")
            return
        try:
            category_id = int(parts[1])
        except ValueError:
            await message.answer("Invalid item ID. Please provide a valid id.")
            return

        async with async_session() as session:
            result = await session.execute(select(ItemCategory).where(ItemCategory.id == category_id))
            category: ItemCategory = result.scalar_one_or_none()

        if not category:
            await message.answer(f"Category with ID {category_id} not found.")
            return

        async with async_session() as session:
            item_category_result = await session.execute(select(Item).where(Item.category_id == category.id))
            item_category = item_category_result.scalars().all()
            if len(item_category) > 0:
                await message.answer("You cannot delete a category if there are already exist items with that category")
                return

        # Формируем inline-клавиатуру с кнопками "Confirm" и "Cancel"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_delete_category_{category_id}")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_delete_category")]
        ])

        await message.answer(
            f"Are you sure you want to delete Category <b>{category.category_name}</b> (ID: {category_id})?",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    @router.callback_query(F.data.startswith("confirm_delete_category_"), AdminOperatorFilter())
    async def confirm_delete_item_handler(callback: CallbackQuery):
        # Извлекаем item_id из callback data
        try:
            category_id = int(callback.data.split("_")[-1])
        except ValueError:
            await callback.answer("Invalid item ID.", show_alert=True)
            return

        async with async_session() as session:
            result = await session.execute(select(ItemCategory).where(ItemCategory.id == category_id))
            category: ItemCategory = result.scalar_one_or_none()
            if not category:
                await callback.answer("Category not found.", show_alert=True)
                return

            item_category_result = await session.execute(select(Item).where(Item.category_id == category.id))
            item_category = item_category_result.scalars().all()
            if len(item_category) > 0:
                await callback.message.answer(
                    "You cannot delete a category if there are already exist items with that category")
                return
            try:
                await session.delete(category)
                await session.commit()
            except Exception as e:
                logging.info(f"ERROR: {e}")
                return

        # Редактируем сообщение, чтобы уведомить пользователя об успешном удалении
        await callback.message.edit_text("Category deleted successfully.")
        await callback.answer()

    @router.callback_query(F.data == "cancel_delete_category", AdminOperatorFilter())
    async def cancel_delete_item_handler(callback: CallbackQuery):
        await callback.message.edit_text("Category deletion canceled.")
        await callback.answer()
