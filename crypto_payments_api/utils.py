import logging
from datetime import datetime
from typing import  Optional

from fastapi import HTTPException
from sqlalchemy import select

from config import USDT_CONTRACT_ADDRESS
from models import Wallet, Deposit

from tronpy.keys import PrivateKey
from db.session import get_session
import asyncio
# Утилита для генерации уникальных ключей кошелька (для демонстрационных целей)


async def generate_wallet() -> Optional[Wallet]:
    async with get_session() as session:
        try:
            private_key = PrivateKey.random()
            public_key = private_key.public_key.to_base58check_address()
            new_wallet = Wallet(public_key=public_key,
                                private_key=private_key.hex())
            session.add(new_wallet)
            await session.commit()
            await session.refresh(new_wallet)
        except Exception as wallet_adding_exception:
            await session.rollback()
            logging.info("Ошибка при сохранении кошелька:", wallet_adding_exception)
            return

    return new_wallet


# Функция поиска свободного кошелька или создания нового
async def get_or_create_wallet() -> Wallet:
    async with get_session() as session:
        free_wallet_query = await session.execute(select(Wallet).where(Wallet.in_use==False).limit(1))
        free_wallet = free_wallet_query.scalars().first()
        if not free_wallet:
            free_wallet = await generate_wallet()
            print(f"Сгенерирован новый кошелек: {free_wallet.public_key}")
        else:
            print(f"Найден свободный кошелек: {free_wallet.public_key}")
            free_wallet.in_use = True
        if free_wallet:
            await session.commit()
            return free_wallet
        else:
            raise HTTPException(status_code=400, detail="Ошибка при получении свободного кошелька")


async def get_token_balance(client, wallet_address):
    try:
        cntr = await client.get_contract(USDT_CONTRACT_ADDRESS)
        if cntr is None:
            print("Contract not found!")
        precision = await cntr.functions.decimals()
        if precision is None:
            print("Decimals not returned!")
        token_balance = await cntr.functions.balanceOf(wallet_address)
        if token_balance is None:
            print("Balance not returned!")
        final_token_balance = token_balance / 10 ** precision
        return final_token_balance

    except Exception as balance_check:
        print(f"Ошибка при проверке баланса для {wallet_address}:", balance_check)
        return

