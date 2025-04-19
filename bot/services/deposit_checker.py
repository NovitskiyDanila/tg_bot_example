import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update
from database.session import async_session
from database.models import Deposit, User

from services.tron_client import get_token_balance  # функция для получения баланса
from config import TRONGRID_API_KEY  # если требуется, можно использовать здесь, но в get_token_balance она уже передается через tron_client

# Константы
DEPOSIT_TIMEOUT = timedelta(minutes=15)
CHECK_INTERVAL = 30  # интервал проверки в секундах
USDT_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcd"

logger = logging.getLogger(__name__)

async def background_deposit_checker():
    """
    Фоновая задача, которая периодически проверяет депозиты со статусом "in progress".
    Если текущий баланс кошелька равен initial_balance + deposit.amount, то:
      - Обновляется баланс пользователя (в центах) и сумма депозитов.
      - Начисляются бонусы: 10% для реферера и 5% для реферала реферала.
      - Статус депозита меняется на "confirmed".
      - Кошелек освобождается (in_use = False).
    Если прошло более 15 минут, а перевод не обнаружен, депозит отменяется и кошелек освобождается.
    """
    logger.info("Запуск фоновой проверки депозитов...")
    while True:
        try:
            async with async_session() as session:
                now = datetime.utcnow()
                query = select(Deposit).where(Deposit.status == "in progress")
                result = await session.execute(query)
                deposits = result.scalars().all()

                for deposit in deposits:
                    deposit_age = now - deposit.deposit_date

                    # Получаем кошелек, связанный с депозитом
                    query_wallet = select(Wallet).where(Wallet.id == deposit.wallet_id)
                    result_wallet = await session.execute(query_wallet)
                    wallet = result_wallet.scalar_one_or_none()
                    if not wallet:
                        continue

                    current_balance = await get_token_balance(wallet.public_key, token=USDT_CONTRACT)
                    if current_balance is None:
                        continue

                    expected_balance = int(deposit.initial_balance) + deposit.amount

                    if current_balance == expected_balance:
                        # Подтверждаем депозит
                        await session.execute(
                            update(Deposit)
                            .where(Deposit.id == deposit.id)
                            .values(status="confirmed")
                        )
                        query_user = select(User).where(User.id == deposit.user_id)
                        result_user = await session.execute(query_user)
                        user = result_user.scalar_one_or_none()
                        if user:
                            user.balance = (user.balance or 0) + deposit.amount
                            user.amount_of_deposits = (user.amount_of_deposits or 0) + deposit.amount
                            # Начисляем бонусы
                            if user.referrer_id:
                                query_ref = select(User).where(User.id == user.referrer_id)
                                result_ref = await session.execute(query_ref)
                                ref_user = result_ref.scalar_one_or_none()
                                if ref_user:
                                    bonus = int(deposit.amount * 0.10)
                                    ref_user.bonus_balance = (ref_user.bonus_balance or 0) + bonus
                                    if ref_user.referrer_id:
                                        query_ref2 = select(User).where(User.id == ref_user.referrer_id)
                                        result_ref2 = await session.execute(query_ref2)
                                        ref_user2 = result_ref2.scalar_one_or_none()
                                        if ref_user2:
                                            bonus2 = int(deposit.amount * 0.05)
                                            ref_user2.bonus_balance = (ref_user2.bonus_balance or 0) + bonus2

                        # Освобождаем кошелек
                        await session.execute(
                            update(Wallet)
                            .where(Wallet.id == wallet.id)
                            .values(in_use=False)
                        )
                        logger.info(f"Deposit {deposit.id} confirmed for user {deposit.user_id}.")
                    elif deposit_age > DEPOSIT_TIMEOUT:
                        # Если прошло более 15 минут и депозит не подтвержден, отменяем его
                        await session.execute(
                            update(Deposit)
                            .where(Deposit.id == deposit.id)
                            .values(status="canceled")
                        )
                        # Освобождаем кошелек
                        await session.execute(
                            update(Wallet)
                            .where(Wallet.id == wallet.id)
                            .values(in_use=False)
                        )
                        logger.info(f"Deposit {deposit.id} canceled due to timeout.")
                await session.commit()
        except Exception as e:
            logger.error(f"Error in deposit checker: {e}")
        await asyncio.sleep(CHECK_INTERVAL)
