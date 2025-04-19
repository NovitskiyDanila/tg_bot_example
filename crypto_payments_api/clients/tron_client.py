from httpx import AsyncClient
from tronpy import AsyncTron
from tronpy.providers import AsyncHTTPProvider

from config import TRONGRID_API_KEY

async_client = AsyncClient(headers={"TRON-PRO-API-KEY": TRONGRID_API_KEY})
provider = AsyncHTTPProvider("https://api.trongrid.io", client=async_client)
tron_client = AsyncTron(provider)

