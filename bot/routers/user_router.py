from aiogram import Router
from middlewares.mirror_active import MirrorActiveMiddleware
from handlers.user import (register_personal_account_handlers, register_deposit_handlers,
                           register_start_handlers, register_create_mirror_handlers,
                           register_my_bot_handlers, register_buy_handlers,
                           register_my_deposits_handlers, register_my_purchases_handlers,
                           register_help_handlers, register_about_bot_handlers, register_catalog_handlers)


def create_user_router() -> Router:
    user_router = Router()
    user_router.message.middleware(MirrorActiveMiddleware())

    register_start_handlers(user_router)
    register_personal_account_handlers(user_router)
    register_help_handlers(user_router)
    register_about_bot_handlers(user_router)
    register_deposit_handlers(user_router)
    register_create_mirror_handlers(user_router)
    register_my_bot_handlers(user_router)
    register_buy_handlers(user_router)
    register_my_deposits_handlers(user_router)
    register_my_purchases_handlers(user_router)
    register_catalog_handlers(user_router)
    return user_router
