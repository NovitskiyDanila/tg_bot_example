import logging
from httpx import AsyncClient, Timeout
from tronpy.async_tron import AsyncTron
from tronpy.providers.async_http import AsyncHTTPProvider
from config import TRONGRID_API_KEY
from tronpy import TRX

logger = logging.getLogger(__name__)


# Функция для создания асинхронного клиента Tron с заданными параметрами
async def get_async_tron_client():
    async_client = AsyncClient(timeout=Timeout(10.0), headers={"TRON-PRO-API-KEY": TRONGRID_API_KEY})
    provider = AsyncHTTPProvider("https://api.trongrid.io", client=async_client)
    return AsyncTron(provider=provider)


# Функция для получения баланса токена (например, USDT TRC20) по кошельку
async def get_token_balance(public_key: str, token: str):
    client = await get_async_tron_client()
    contract_usdt = await client.get_contract(token)  # usdt
    precision = contract_usdt.functions.decimals()
    try:
        amount = contract_usdt.functions.balanceOf(public_key) / 10 ** precision
        print(amount)
        return (amount)
    except Exception as e:
        logger.error(f"Error fetching balance for wallet {public_key}: {e}")
        return None
