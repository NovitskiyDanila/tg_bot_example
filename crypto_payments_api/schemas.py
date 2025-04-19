import datetime

from pydantic import BaseModel


class DepositRequest(BaseModel):
    amount: int
    user_tg_id: int

class DepositResponse(BaseModel):
    deposit_id: int
    wallet_public_key: str
    amount: int
    expires_at: str


class DepositStatusResponse(BaseModel):
    status: str


class DepositCancelResponse(BaseModel):
    detail: str


class DepositCancelRequest(BaseModel):
    deposit_id: int


class DepositDetailResponse(BaseModel):
    deposit_id: int
    wallet_public_key: str
    wallet_initial_balance: int
    deposit_amount: int
    expires_time: datetime
    status: str

    class Config:
        arbitrary_types_allowed = True
