"""Репозиторий динамических категорий и услуг (bot.db.repo.services).

Соответствует legacy bot_ptb.py (строки 343-400, 1530-1560):
- get_service_categories
- get_service_category
- get_service_items
- get_service_item (с category_name)
- CRUD добавления категорий и вариантов
- обновление цены
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import ServiceCategory, ServiceItem


async def get_service_categories(
    session: AsyncSession,
    active_only: bool = True,
) -> list[ServiceCategory]:
    """Возвращает список категорий услуг, отсортированных по sort_order, id."""
    stmt = select(ServiceCategory)
    if active_only:
        stmt = stmt.where(ServiceCategory.active == 1)
    stmt = stmt.order_by(ServiceCategory.sort_order, ServiceCategory.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_service_category(
    session: AsyncSession,
    category_id: int,
) -> ServiceCategory | None:
    """Возвращает категорию услуг по ID."""
    return await session.get(ServiceCategory, category_id)


async def get_service_items(
    session: AsyncSession,
    category_id: int,
    active_only: bool = True,
) -> list[ServiceItem]:
    """Возвращает варианты услуг для заданной категории, отсортированные по sort_order, id."""
    stmt = select(ServiceItem).where(ServiceItem.category_id == category_id)
    if active_only:
        stmt = stmt.where(ServiceItem.active == 1)
    stmt = stmt.order_by(ServiceItem.sort_order, ServiceItem.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_service_item(
    session: AsyncSession,
    item_id: int,
) -> ServiceItem | None:
    """Возвращает услугу по ID с прикреплённым category_name (как в legacy: JOIN service_categories)."""
    stmt = (
        select(ServiceItem, ServiceCategory.name)
        .join(ServiceCategory, ServiceCategory.id == ServiceItem.category_id)
        .where(ServiceItem.id == item_id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if not row:
        return None
    item, cat_name = row
    # Прикрепляем динамический атрибут category_name для удобства
    setattr(item, "category_name", cat_name)
    return item


async def create_service_category(
    session: AsyncSession,
    name: str,
    active: int = 1,
    sort_order: int | None = None,
) -> ServiceCategory:
    """Создаёт новую категорию услуг (соответствует legacy строкам 1541-1542)."""
    if sort_order is None:
        order_stmt = select(func.coalesce(func.max(ServiceCategory.sort_order), 0) + 1)
        sort_order = (await session.execute(order_stmt)).scalar_one()

    category = ServiceCategory(name=name, active=active, sort_order=sort_order)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def create_service_item(
    session: AsyncSession,
    category_id: int,
    name: str,
    price: float | int,
    quantity_mode: str = "fixed",
    unit: str = "шт.",
    active: int = 1,
    sort_order: int | None = None,
) -> ServiceItem:
    """Создаёт новый вариант услуги (соответствует legacy строкам 1543, 1554-1555)."""
    if sort_order is None:
        order_stmt = select(func.coalesce(func.max(ServiceItem.sort_order), 0) + 1).where(
            ServiceItem.category_id == category_id
        )
        sort_order = (await session.execute(order_stmt)).scalar_one()

    item = ServiceItem(
        category_id=category_id,
        name=name,
        price=float(price),
        quantity_mode=quantity_mode,
        unit=unit,
        active=active,
        sort_order=sort_order,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_service_item_price(
    session: AsyncSession,
    item_id: int,
    price: float | int,
) -> ServiceItem | None:
    """Обновляет цену варианта услуги (соответствует legacy строке 1538)."""
    item = await session.get(ServiceItem, item_id)
    if not item:
        return None
    item.price = float(price)
    await session.commit()
    await session.refresh(item)
    return item
