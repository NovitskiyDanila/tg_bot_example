from aiogram import Router

from filters.admin_operator_filter import AdminOperatorFilter
from handlers.admin import (register_add_category_handlers, register_add_item_handlers,
                            register_add_role_handlers, register_add_balance_handlers,
                            register_check_users_deposits_handlers, register_user_purchases_handlers,
                            register_item_delete_handlers, register_delete_category_handlers,
                            register_commands_handlers)


def create_admin_router() -> Router:
    admin_router = Router()
    admin_router.message.filter(AdminOperatorFilter())

    register_add_category_handlers(admin_router)
    register_add_item_handlers(admin_router)
    register_add_role_handlers(admin_router)
    register_add_balance_handlers(admin_router)
    register_check_users_deposits_handlers(admin_router)
    register_user_purchases_handlers(admin_router)
    register_item_delete_handlers(admin_router)
    register_delete_category_handlers(admin_router)
    register_commands_handlers(admin_router)

    return admin_router
