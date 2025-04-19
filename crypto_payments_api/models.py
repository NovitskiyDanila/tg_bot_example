from datetime import datetime, timedelta

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Sequence, text

Base = declarative_base()


# Модель таблицы wallets
class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    public_key = Column(String, unique=True, index=True, nullable=False)
    private_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    in_use = Column(Boolean, default=True)


# Модель таблицы deposits
class Deposit(Base):
    __tablename__ = "deposits"
    id = Column(
        Integer,
        Sequence("deposit_id_seq", start=187310, increment=1),
        primary_key=True,
        autoincrement=True,
        server_default=text("nextval('deposit_id_seq')")
    )
    user_tg_id = Column(Integer, nullable=False)
    wallet_public_key = Column(String, nullable=False)  # связываем с Wallet.public_key
    wallet_initial_balance = Column(Integer)
    amount = Column(Float, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(minutes=20))
    status = Column(String, default="pending")  # например: pending, confirmed, failed


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(
        Integer,
        Sequence("withdrawal_id_seq", start=187310, increment=1),
        primary_key=True,
        autoincrement=True,
        server_default=text("nextval('withdrawal_id_seq')")
    )
    wallet_public_key = Column(String, nullable=False)  # связываем с Wallet.public_key
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending")  # например: pending, confirmed, failed
    tx_hash = Column(String)