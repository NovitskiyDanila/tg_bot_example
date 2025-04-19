import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query, Security, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession


from clients.tron_client import tron_client
from models import Deposit, Wallet
from schemas import (DepositRequest, DepositResponse,
                     DepositStatusResponse, DepositCancelRequest,
                     DepositCancelResponse, DepositDetailResponse)
from db.session import get_db
from tasks import monitor_deposit
from config import API_KEY
from utils import get_or_create_wallet, get_token_balance

# Настройки API Key
api_key = API_KEY  # Ваш секретный API-ключ
API_KEY_NAME = "access_token"  # Имя заголовка, в котором передается ключ
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key"
    )


# Все эндпоинты в данном роутере будут требовать валидный API Key
router = APIRouter(dependencies=[Depends(get_api_key)])


@router.post("/deposit", response_model=DepositResponse)
async def create_deposit(
        deposit_req: DepositRequest,
        background_tasks: BackgroundTasks,
        session: AsyncSession = Depends(get_db)
):
    if deposit_req.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid deposit amount")

    existing_deposit_result = await session.execute(
        select(Deposit).where(
            Deposit.user_tg_id == deposit_req.user_tg_id,
            Deposit.status == "pending"
        )
    )
    existing_deposit = existing_deposit_result.scalar_one_or_none()
    if existing_deposit:
        # Если депозит уже существует, возвращаем его информацию
        return JSONResponse(
            status_code=409,
            content=DepositResponse(
                deposit_id=existing_deposit.id,
                wallet_public_key=existing_deposit.wallet_public_key,
                amount=existing_deposit.amount,
                expires_at=existing_deposit.expires_at.strftime("%d.%m.%Y %H:%M")
            ).dict()
        )

    wallet = await get_or_create_wallet()
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    initial_balance = await get_token_balance(tron_client, wallet.public_key)
    deposit = Deposit(
        wallet_public_key=wallet.public_key,
        amount=deposit_req.amount,
        wallet_initial_balance=initial_balance,
        user_tg_id=deposit_req.user_tg_id
    )
    session.add(deposit)
    try:
        await session.commit()
        await session.refresh(deposit)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to create a deposit")

    # Запускаем фоновую задачу для мониторинга депозита
    background_tasks.add_task(monitor_deposit, deposit.id, session)

    return DepositResponse(
        deposit_id=deposit.id,
        wallet_public_key=wallet.public_key,
        amount=deposit_req.amount,
        expires_at=deposit.expires_at.strftime("%d.%m.%Y %H:%M")
    )


@router.get("/deposit/status", response_model=DepositStatusResponse)
async def get_deposit_status(
        deposit_id: int = Query(...),
        session: AsyncSession = Depends(get_db)
):
    logging.info(f"Deposit id: {deposit_id}")
    deposit = await session.get(Deposit, deposit_id)
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return DepositStatusResponse(status=deposit.status)


@router.post("/deposit/cancel", response_model=DepositCancelResponse)
async def cancel_deposit(
        cancel_req: DepositCancelRequest,
        session: AsyncSession = Depends(get_db)
):
    deposit = await session.get(Deposit, cancel_req.deposit_id)
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deposit not found")

    if deposit.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Deposit cannot be canceled because it is not pending")

    deposit.status = "canceled"

    wallet_query = await session.execute(
        select(Wallet).where(Wallet.public_key == deposit.wallet_public_key)
    )
    wallet = wallet_query.scalar_one_or_none()
    if wallet:
        wallet.in_use = False

    await session.commit()
    return DepositCancelResponse(detail="Deposit canceled successfully")


@router.get("/deposit/detail", response_model=DepositDetailResponse)
async def get_deposit_details(
        deposit_id: int = Query(...),
        session: AsyncSession = Depends(get_db)
):
    logging.info(f"Deposit id detail request: {deposit_id}")
    deposit = await session.get(Deposit, deposit_id)
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return DepositDetailResponse(deposit_id=deposit.id,
                                 wallet_public_key=deposit.wallet_public_key,
                                 wallet_initial_balance=deposit.wallet_initial_balance,
                                 deposit_amount=deposit.amount,
                                 expires_time=deposit.expires_at,
                                 status=deposit.status)