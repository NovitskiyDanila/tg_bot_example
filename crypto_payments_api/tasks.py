import asyncio
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

from clients import tron_client
from db.session import get_db
from models import Deposit, Wallet
from utils import get_token_balance


async def monitor_deposit(deposit_id: int, session):
    """
    Функция периодически проверяет баланс кошелька, указанного в deposit.wallet_public_key,
    пока deposit.status равен "Pending" и текущее время меньше deposit.expires_at.
    Если баланс достигает необходимого уровня, статус меняется на "confirmed".
    Если депозит отменён (status != "Pending") или время истекло, функция завершает опрос.
    """
    while True:
        deposit = await session.get(Deposit, deposit_id)
        await session.refresh(deposit)
        deposit_wallet_result = await session.execute(select(Wallet).where(Wallet.public_key == deposit.wallet_public_key))
        deposit_wallet: Wallet = deposit_wallet_result.scalar_one_or_none()
        if not deposit:
            # Если депозит не найден в БД, прерываем выполнение.
            raise HTTPException(status_code=404, detail="Deposit not found")

        # Если депозит уже не в состоянии "Pending" (например, "canceled"), выходим.
        if deposit.status != "pending":
            print(f"Депозит {deposit_id} изменён на статус {deposit.status}. Остановка мониторинга.")
            deposit_wallet.in_use = False
            await session.commit()
            return

        if deposit.status == "canceled":
            deposit_wallet.in_use = False
            await session.commit()
            return

        # Если время истекло, обновляем статус и завершаем мониторинг.
        if datetime.utcnow() >= deposit.expires_at:
            deposit.status = "expired"
            deposit_wallet.in_use = False
            await session.commit()
            print(f"Время для депозита {deposit_id} истекло.")
            return


        # Получаем текущий баланс кошелька
        current_balance = await get_token_balance(tron_client, deposit.wallet_public_key)
        print(f"Депозит {deposit_id}: текущий баланс для {deposit.wallet_public_key} = {current_balance}")

        # Если баланс увеличился на сумму депозита (или достиг требуемого уровня)
        # Здесь можно добавить вычитание начального баланса, если нужно:
        if current_balance == deposit.wallet_initial_balance + deposit.amount:
            deposit.status = "confirmed"
            deposit_wallet.in_use = False
            await session.commit()
            print(f"Депозит {deposit_id} подтверждён: баланс достиг {current_balance}.")
            return

        # Ждём 15 секунд перед следующим опросом
        await asyncio.sleep(15)


async def run_monitor_deposit(deposit_id: int):
    async for session in get_db():
        await monitor_deposit(deposit_id, session)


async def startup_monitor_pending_deposits():
    pending_deposits = []
    # Получаем список всех депозитов со статусом "pending"
    async for session in get_db():
        result = await session.execute(select(Deposit).where(Deposit.status == "pending"))
        pending_deposits = result.scalars().all()
        break  # Получаем сессию только один раз

    # Для каждого найденного депозита создаём отдельный background task
    for deposit in pending_deposits:
        asyncio.create_task(run_monitor_deposit(deposit.id))