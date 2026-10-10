"""ORM-модели данных Fishl Shop (SQLAlchemy 2.0).

Включает:
- Строгую типизацию Mapped[...] и mapped_column(...)
- BigInteger для Telegram user ID (поддержка 64-битных ID)
- Индексы для ускорения поиска (client_telegram_id, status, created_at, category_id)
- ORM-связи relationship (ServiceCategory <-> ServiceItem с каскадным удалением)
- Человекочитаемые __repr__ для информативного логгирования
- Полную обратную совместимость со схемой legacy
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый декларативный класс для всех моделей."""
    __allow_unmapped__ = True


class Order(Base):
    """Заказ клиента."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    server: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    tier: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default="new", index=True)
    manager_name: Mapped[str | None] = mapped_column(String(255), default="", server_default="")
    service: Mapped[str | None] = mapped_column(String(255), default="", server_default="")
    details: Mapped[str | None] = mapped_column(Text, default="", server_default="")
    original_price: Mapped[float | None] = mapped_column(Float, default=None)
    discount_amount: Mapped[float | None] = mapped_column(Float, default=0.0, server_default="0")
    discount_mode: Mapped[str | None] = mapped_column(String(64), default="", server_default="")

    def __repr__(self) -> str:
        return (
            f"<Order(id={self.id}, client='{self.client_name}', "
            f"price={self.price}, status='{self.status}')>"
        )


class Discount(Base):
    """Скидка (накопительная/пороговая или на категорию услуг)."""
    __tablename__ = "discounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float, default=0.0, server_default="0")
    service: Mapped[str | None] = mapped_column(String(255), default="", server_default="")
    percent: Mapped[float] = mapped_column(Float, nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, default="%", server_default="%")
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1", index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[str | None] = mapped_column(String(64), default=None)

    def __repr__(self) -> str:
        return (
            f"<Discount(id={self.id}, kind='{self.kind}', "
            f"percent={self.percent}{self.value_type}, active={bool(self.active)})>"
        )


class ServiceCategory(Base):
    """Категория услуг."""
    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    items: Mapped[list[ServiceItem]] = relationship(
        "ServiceItem",
        back_populates="category",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ServiceItem.sort_order, ServiceItem.id",
    )

    def __repr__(self) -> str:
        return f"<ServiceCategory(id={self.id}, name='{self.name}', active={bool(self.active)})>"


class ServiceItem(Base):
    """Конкретная услуга или вариант внутри категории."""
    __tablename__ = "service_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("service_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    quantity_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed", server_default="fixed")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="шт.", server_default="шт.")
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    category: Mapped[ServiceCategory | None] = relationship("ServiceCategory", back_populates="items")

    _category_name: str | None = None

    @property
    def category_name(self) -> str:
        """Возвращает название категории для совместимости с репозиториями."""
        if self._category_name is not None:
            return self._category_name
        return self.category.name if self.category else ""

    @category_name.setter
    def category_name(self, value: str) -> None:
        self._category_name = value

    def __repr__(self) -> str:
        return (
            f"<ServiceItem(id={self.id}, name='{self.name}', "
            f"price={self.price}, mode='{self.quantity_mode}')>"
        )


class RegionPriceOverride(Base):
    """Кастомные цены зачистки для региона (0-100%, 50-100%, 80-100%)."""
    __tablename__ = "region_price_overrides"

    region: Mapped[str] = mapped_column(String(128), primary_key=True)
    price_0_100: Mapped[float] = mapped_column(Float, nullable=False)
    price_50_100: Mapped[float] = mapped_column(Float, nullable=False)
    price_80_100: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<RegionPriceOverride(region='{self.region}')>"


class FsmState(Base):
    """Хранилище FSM aiogram (состояния и данные, переживающие рестарт)."""
    __tablename__ = "fsm_state"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    state: Mapped[str | None] = mapped_column(String(255), default=None)
    data: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")

    def __repr__(self) -> str:
        return f"<FsmState(key='{self.key}', state='{self.state}')>"


class Banner(Base):
    """Баннер экрана бота (Telegram photo file_id)."""
    __tablename__ = "banners"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self) -> str:
        return f"<Banner(key='{self.key}', file_id='{self.file_id[:12]}...')>"


__all__ = [
    "Base",
    "Order",
    "Discount",
    "ServiceCategory",
    "ServiceItem",
    "RegionPriceOverride",
    "FsmState",
    "Banner",
]
