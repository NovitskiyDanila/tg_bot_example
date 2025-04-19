from aiogram import types
from aiogram.filters import Command

from filters import AdminOperatorFilter


def register_commands_handlers(router):

    @router.message(Command("commands"), AdminOperatorFilter())
    async def help_handler(message: types.Message):
        commands_text = (
            "<b>Admin Commands:</b>\n\n"
            
            "<b>/add_category</b> - Adds a new category to the database. \n\n"
            
            "<b>/delete_category 'category_id'</b> - Deletes category with the specified ID.\n"
            "The category ID can be found when adding the category.\n"
            "A category can only be deleted if it has no associated items.\n\n"
            
            "<b>/add_item</b> - Initiates a step-by-step process to add a new item.\n\n"
            
            "<b>/delete_item 'item_id'</b> - Deletes the item with the specified ID.\n"
            "The item ID can be found when adding the item.\n"
            "Only items that have not been purchased can be deleted.\n\n"
            
            "<b>/add_role 'username_or_tg_id' 'role'</b> - Changes the role of the specified user. \n"
            "Available roles: user, admin, operator. \n"
            "(This command is available only for admins.)\n\n"
            
            "<b>/add_balance 'username_or_tg_id'</b> 'amount'\nChanges the user's balance by the specified amount.\n"
            "(This command is available only for admins.)\n\n"

            "<b>/check_deposits 'username'</b> - Views the deposits for the specified user.\n\n"
            
            "<b>/check_purchases 'username'</b> - Views purchases for the specified user.\n\n"
            
            "<b>/commands</b> - Displays all available commands."

        )
        await message.answer(text=commands_text, parse_mode='HTML')
