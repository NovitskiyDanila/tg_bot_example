from aiogram import types, F
from aiogram.types import Message
from sqlalchemy import select
from database.session import async_session  # Функция для получения AsyncSession
from database.models import ItemCategory, Item

def register_catalog_handlers(router):
    @router.message(F.text=="🛒 Catalog")
    async def catalog_handler(message: Message):
        message_text = ""
        async with async_session() as session:
            categories_result = await session.execute(
                select(ItemCategory).order_by(ItemCategory.category_name)
            )
            categories = categories_result.scalars().all()

            if not categories:
                await message.answer("No available items")
                return

            for category in categories:
                items_result = await session.execute(
                    select(Item.item_name, Item.weight, Item.price)
                    .where(Item.category_id == category.id, Item.is_bought == False, Item.is_deleted == False)
                    .group_by(Item.item_name, Item.weight, Item.price)
                    .order_by(Item.item_name)
                )

                unique_items = items_result.all()

                if not unique_items:
                    continue

                message_text += f"<b>{category.category_name}</b>\n\n"

                for row in unique_items:
                    item_name, item_weight, item_price = row
                    message_text += f"Item: <b>{item_name}</b> | Weight: <b>{item_weight}</b> | Price: <b>{float(item_price/100)}$</b>\n"

                message_text += "\n\n"

            if message_text.strip() == "":
                message_text = "No items available at the moment"
                await message.answer(message_text, parse_mode='HTML')
                return


            await message.answer(message_text, parse_mode='HTML')

    @router.message(F.content_type == types.ContentType.VIDEO)
    async def video_handler(message: Message):
        unique_id = message.video.file_unique_id
        await message.answer(f"Video unique ID: <code>{unique_id}</code>", parse_mode="HTML")