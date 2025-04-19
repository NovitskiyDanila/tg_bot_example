from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, Numeric, Sequence, text
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


# -------------------------------
# Пользователи и зеркальные боты
# -------------------------------

class User(Base):
    """
    Модель пользователя.
    Поле mirror_created:
      - False – зеркало не создано (ограниченный доступ)
      - True – зеркало создано и активно (полный доступ)
    Поле referrer_id (опционально) хранит ID пользователя, который его пригласил.
    Дополнительные финансовые поля:
      - balance: основной баланс пользователя.
      - bonus_balance: бонусный баланс (например, 10% от пополнений рефералов).
      - amount_of_deposits: общая сумма пополнений.
    Новое поле role определяет роль пользователя и может принимать значения:
      "user", "admin", "operator".
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=False)
    entry_date = Column(DateTime, default=datetime.utcnow)
    mirror_created = Column(Boolean, default=False)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    balance = Column(Integer, default=0)
    bonus_balance = Column(Integer, default=0)

    # Роль пользователя: "user" (по умолчанию), "admin" или "operator"
    role = Column(String, default="user")
    is_banned = Column(Boolean, default=False)

    # Связь с зеркальным ботом (один пользователь может иметь не более одного зеркала)
    mirror_bot = relationship("MirrorBot", back_populates="owner", uselist=False)


class MirrorBot(Base):
    """
    Модель зеркального бота.
    Хранит токен, username и флаг active, определяющий, действителен ли бот.
    """
    __tablename__ = "mirror_bots"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, nullable=False)
    username = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="mirror_bot")


# -------------------------------
# Категории и товары
# -------------------------------

class ItemCategory(Base):
    """
    Таблица категорий товаров.
    Поля:
      - id: первичный ключ.
      - category_name: название категории.
    """
    __tablename__ = "item_categories"
    id = Column(Integer, Sequence("item_category_id_seq", start=12040, increment=1), primary_key=True)
    category_name = Column(String, nullable=False)
    is_deleted = Column(Boolean, default=False)

    # Связь с товарами
    items = relationship("Item", back_populates="category")


class Item(Base):
    """
    Таблица товаров.
    Поля:
      - id: первичный ключ.
      - category_id: внешний ключ на категорию.
      - item_name: название товара.
      - weight: вес товара (можно изменить тип, если необходимо).
      - area: район нахождения.
      - photo1: фотография товара (до покупки).
      - description1: описание товара, видимое до покупки.
      - photo2, photo3, photo4: фотографии товара после покупки.
      - description2: описание, выводимое после покупки.
      - price: цена товара.
      - addition_date: дата добавления товара.
      - is_bought: флаг покупки товара.
      - purchase_date: дата покупки (если товар куплен).
      - added_by: id пользователя, который добавил товар.
    """
    __tablename__ = "items"
    id = Column(
        Integer,
        Sequence("item_id_seq", start=187310, increment=1),
        primary_key=True,
        autoincrement=True,
        server_default=text("nextval('item_id_seq')")
    )
    category_id = Column(Integer, ForeignKey("item_categories.id"), nullable=False)
    item_name = Column(String, nullable=False)
    weight = Column(String)  # или Numeric, если требуется
    area = Column(String)
    photo1 = Column(String)
    description1 = Column(String)
    photo2 = Column(String)
    photo3 = Column(String)
    photo4 = Column(String)
    description2 = Column(String)
    price = Column(Integer, nullable=False)
    addition_date = Column(DateTime, default=datetime.utcnow)
    is_bought = Column(Boolean, default=False)
    purchase_date = Column(DateTime, nullable=True)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_deleted = Column(Boolean, default=False)

    # Связи
    category = relationship("ItemCategory", back_populates="items")
    added_user = relationship("User", foreign_keys=[added_by])
    purchase = relationship("Purchase", back_populates="item", uselist=False)


# -------------------------------
# Покупки
# -------------------------------

class Purchase(Base):
    """
    Таблица покупок.
    Поля:
      - id: первичный ключ.
      - user_id: внешний ключ на пользователя.
      - item_id: внешний ключ на товар.
      - amount: сумма покупки.
      - purchase_date: дата покупки.
    """
    __tablename__ = "purchases"
    id = Column(
        Integer,
        Sequence("purchase_id_seq", start=187310, increment=1),
        primary_key=True,
        autoincrement=True,
        server_default=text("nextval('purchase_id_seq')")
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    purchase_date = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    item = relationship("Item", back_populates="purchase")


# -------------------------------
# Кошельки и пополнения
# -------------------------------


class Deposit(Base):
    """
    Таблица пополнений.
    Поля:
      - id: первичный ключ.
      - user_id: внешний ключ на пользователя.
      - wallet_id: внешний ключ на кошелек.
      - amount: сумма пополнения.
      - status: статус пополнения ("in progress", "canceled", "confirmed").
      - deposit_date: дата пополнения.
    """
    __tablename__ = "deposits"
    id = Column(
        Integer,
        Sequence("deposit_id_seq", start=187310, increment=1),
        primary_key=True,
        autoincrement=True,
        server_default=text("nextval('deposit_id_seq')")
    )
    api_deposit_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, nullable=False, index=True)

    user = relationship("User", foreign_keys=[user_id])

