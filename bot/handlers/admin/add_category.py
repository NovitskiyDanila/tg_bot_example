import logging
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.session import async_session
from database.models import ItemCategory
from filters import AdminOperatorFilter

logger = logging.getLogger(__name__)


class CategoryCreation(StatesGroup):
    waiting_for_category_name = State()
    waiting_for_confirmation = State()


def register_add_category_handlers(router):
    @router.message(Command("add_category"))
    async def add_category_command_handler(message: types.Message, state: FSMContext):
        """
        Обработчик команды /add_category.
        Переводит пользователя в состояние ожидания ввода названия новой категории.
        """
        await message.answer("Please send me the name of the new category:")
        await state.set_state(CategoryCreation.waiting_for_category_name)

    @router.message(CategoryCreation.waiting_for_category_name, AdminOperatorFilter())
    async def add_category_handler(message: types.Message, state: FSMContext):
        """
        Обработчик сообщения с названием новой категории.
        Проверяет, существует ли категория, и запрашивает подтверждение добавления.
        """
        if not message.text:
            await message.answer("Category name cannot be empty. Please try again.")
            return

        category_name = message.text.strip()
        if not category_name:
            await message.answer("Category name cannot be empty. Please try again.")
            return

        # Проверяем, существует ли категория с таким именем (без учёта регистра)
        async with async_session() as session:
            result = await session.execute(
                select(ItemCategory).where(ItemCategory.category_name == category_name,
                                           ItemCategory.is_deleted == False)

            )
            existing_category = result.scalar_one_or_none()
        if existing_category:
            await message.answer("A category with this name already exists.")
            await state.clear()
            return

        # Сохраняем название категории для дальнейшего использования
        await state.update_data(category_name=category_name)

        # Формируем инлайн-клавиатуру с кнопками Confirm и Cancel
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm", callback_data="confirm")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
        ])

        await message.answer(f"You are about to add a category: {category_name}", reply_markup=keyboard)
        await state.set_state(CategoryCreation.waiting_for_confirmation)

    @router.callback_query(CategoryCreation.waiting_for_confirmation, AdminOperatorFilter())
    async def confirm_category_callback(callback_query: types.CallbackQuery, state: FSMContext):
        """
        Обработчик callback_query для инлайн-клавиатуры.
        При нажатии Confirm – записывает категорию в БД, при Cancel – отменяет операцию.
        """
        data = callback_query.data
        state_data = await state.get_data()
        category_name = state_data.get("category_name")

        if data == "cancel":
            await callback_query.message.edit_text("Category addition canceled.")
            await state.clear()
            await callback_query.answer()
            return

        if data == "confirm":
            # Проверяем ещё раз наличие категории (на случай, если она успела добавиться)
            async with async_session() as session:
                result = await session.execute(
                    select(ItemCategory).where(ItemCategory.category_name.ilike(category_name))
                )
                existing_category = result.scalar_one_or_none()
                if existing_category:
                    await callback_query.message.edit_text("A category with this name already exists.")
                    await state.clear()
                    await callback_query.answer()
                    return
                try:
                # Создаем новую категорию
                    new_category = ItemCategory(category_name=category_name)
                    session.add(new_category)
                    await session.commit()
                    await session.refresh(new_category)
                except Exception as e:
                    logging.info(f"ERROR: {e}")
                    await session.rollback()
                    await callback_query.message.answer("An error occurred while adding the category, please try again. 🙂 ")
                    return

            await callback_query.message.edit_text(f"Category <b>{category_name}</b> <b>(ID: <code>{new_category.id}</code>)</b> has been added.")
            await state.clear()
            await callback_query.answer()
