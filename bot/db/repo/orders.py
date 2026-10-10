"""Репозиторий заказов (bot.db.repo.orders).

Все функции принимают `session: AsyncSession`.
Чтение выполняется без commit, записи делают `await session.commit()`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Order


def order_to_dict(order: Order, is_archive: bool = False, source_db: str = "orders.db") -> dict[str, Any]:
    """Преобразует модель Order в dict (совместимо со старыми хендлерами из legacy)."""
    return {
        "id": order.id,
        "created_at": order.created_at,
        "client_telegram_id": order.client_telegram_id,
        "client_name": order.client_name,
        "uid": order.uid,
        "server": order.server,
        "region": order.region,
        "tier": order.tier,
        "price": order.price,
        "status": order.status,
        "manager_name": order.manager_name or "",
        "service": order.service or "",
        "details": order.details or "",
        "original_price": order.original_price,
        "discount_amount": order.discount_amount or 0.0,
        "discount_mode": order.discount_mode or "",
        "_is_archive": is_archive,
        "_source_db": source_db,
    }


async def create_order(
    session: AsyncSession,
    *,
    client_telegram_id: int,
    client_name: str,
    price: int | float,
    region: str = "Не требуется",
    tier: str = "Услуга",
    service: str = "Зачистка по регионам",
    details: str = "",
    uid: str = "",
    server: str = "",
    original_price: float | None = None,
    discount_amount: float = 0.0,
    discount_mode: str = "",
    status: str = "new",
    manager_name: str = "",
    created_at: str | None = None,
) -> Order:
    """Создаёт новый заказ и сохраняет в БД."""
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    order = Order(
        created_at=created_at,
        client_telegram_id=client_telegram_id,
        client_name=client_name,
        uid=uid,
        server=server,
        region=region,
        tier=tier,
        price=int(round(price)),
        status=status,
        manager_name=manager_name,
        service=service,
        details=details,
        original_price=float(original_price) if original_price is not None else None,
        discount_amount=float(discount_amount) if discount_amount is not None else 0.0,
        discount_mode=discount_mode,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_order_by_id(session: AsyncSession, order_id: int) -> Order | None:
    """Получает заказ по ID (без commit)."""
    return await session.get(Order, order_id)


async def update_order_status(
    session: AsyncSession,
    order_id: int,
    status: str,
    manager_name: str | None = None,
) -> Order | None:
    """Обновляет статус заказа и имя менеджера."""
    order = await session.get(Order, order_id)
    if not order:
        return None
    order.status = status
    if manager_name is not None:
        order.manager_name = manager_name
    await session.commit()
    await session.refresh(order)
    return order


async def update_order_discount(
    session: AsyncSession,
    order_id: int,
    price: float | int,
    original_price: float,
    discount_amount: float,
    discount_mode: str,
) -> Order | None:
    """Обновляет итоговую цену и параметры скидки для заказа."""
    order = await session.get(Order, order_id)
    if not order:
        return None
    order.price = int(round(price))
    order.original_price = float(original_price)
    order.discount_amount = float(discount_amount)
    order.discount_mode = discount_mode
    await session.commit()
    await session.refresh(order)
    return order


async def get_active_orders(
    session: AsyncSession,
    statuses: tuple[str, ...] = ("new", "taken", "working"),
    limit: int = 20,
) -> list[Order]:
    """Возвращает активные заказы менеджера (по умолчанию статусы new/taken/working, сортировка по id DESC)."""
    stmt = (
        select(Order)
        .where(Order.status.in_(statuses))
        .order_by(Order.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_client_orders(
    session: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[Order]:
    """Возвращает последние заказы клиента, отсортированные от новых к старым (created_at DESC)."""
    stmt = (
        select(Order)
        .where(Order.client_telegram_id == user_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_manager_orders(
    session: AsyncSession,
    limit: int = 50,
) -> list[Order]:
    """Возвращает все заказы для менеджера (сортировка от новых к старым created_at DESC)."""
    stmt = (
        select(Order)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
