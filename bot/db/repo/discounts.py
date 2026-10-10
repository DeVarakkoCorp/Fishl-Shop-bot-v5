"""Репозиторий и логика скидок (bot.db.repo.discounts).

Соответствует legacy bot_ptb.py (строки 550-650, 1160-1188, 1500-1520):
- get_active_discounts (с авто-деактивацией истёкших)
- get_discount_by_id
- create_discount
- deactivate_discount
- deactivate_all_discounts
- delete_discount
- calculate_discount, get_applicable_discounts, вспомогательные функции форматирования
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Discount


def _get_val(obj: Discount | dict[str, Any], attr: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def discount_kind_label(row: Discount | dict[str, Any]) -> str:
    kind = _get_val(row, "kind", "")
    threshold = _get_val(row, "threshold", 0)
    service = _get_val(row, "service", "")
    if kind == "threshold":
        return f"От {int(float(threshold or 0))} ₽"
    return f"Услуга: {service}"


def discount_value_label(row: Discount | dict[str, Any]) -> str:
    vtype = _get_val(row, "value_type", "%")
    percent = float(_get_val(row, "percent", 0.0))
    suffix = " ₽" if vtype == "RUB" else "%"
    val_str = str(int(percent)) if percent.is_integer() else f"{percent:.2f}".rstrip("0").rstrip(".")
    return f"{val_str}{suffix}"


def discount_period_label(row: Discount | dict[str, Any]) -> str:
    expires_at = _get_val(row, "expires_at", None)
    return "без срока" if not expires_at else f"до {expires_at}"


def discount_description(rows: list[Discount | dict[str, Any]]) -> str:
    return "\n".join(
        f"#{_get_val(r, 'id', '')} — {discount_kind_label(r)} — *{discount_value_label(r)}* — {discount_period_label(r)}"
        for r in rows
    )


def calculate_discount(
    base_price: float | int,
    discounts: list[Discount | dict[str, Any]],
    mode: str = "sequential",
) -> tuple[float, float]:
    """Calculate fixed-ruble and percentage discounts.

    Sequential applies each rule in order. Percentage values are the share of
    the original price that remains after the discount; fixed values subtract
    the specified amount.
    """
    base = float(base_price)
    if not discounts:
        return base, 0.0

    threshold = [d for d in discounts if _get_val(d, "kind") == "threshold"]
    service = [d for d in discounts if _get_val(d, "kind") == "service"]
    ordered = threshold + service

    def value_type(d: Discount | dict[str, Any]) -> str:
        return _get_val(d, "value_type", "%") or "%"

    def percent_val(d: Discount | dict[str, Any]) -> float:
        return float(_get_val(d, "percent", 0.0))

    if mode == "summed":
        percent = sum(min(max(percent_val(d), 0.0), 100.0) for d in ordered if value_type(d) == "%")
        fixed = sum(max(percent_val(d), 0.0) for d in ordered if value_type(d) == "RUB")
        discount_amount = min(base, base * min(percent, 100.0) / 100.0 + fixed)
        final = base - discount_amount
    else:
        final = base
        for d in ordered:
            val = max(percent_val(d), 0.0)
            if value_type(d) == "RUB":
                final -= val
            else:
                # Процентная скидка хранится как доля цены, которую нужно оставить.
                # Например, 91.67% от 24 ₽ = 22 ₽.
                final *= min(val, 100.0) / 100.0
            final = max(final, 0.0)
        discount_amount = base - final

    final = round(max(final, 0.0), 2)
    return final, round(base - final, 2)


def get_applicable_discounts(
    discounts: list[Discount | dict[str, Any]],
    total_price: float | int,
    service: str = "",
) -> list[Discount | dict[str, Any]]:
    """Находит скидки, применимые к заказу с заданной стоимостью и услугой."""
    total = float(total_price)
    service_clean = str(service or "").strip().lower()
    result = []
    for d in discounts:
        kind = _get_val(d, "kind")
        d_service = str(_get_val(d, "service", "") or "").strip().lower()
        threshold = float(_get_val(d, "threshold", 0.0) or 0.0)
        if kind == "threshold" and total >= threshold:
            result.append(d)
        elif kind == "service" and service_clean and service_clean == d_service:
            result.append(d)
    return result


def get_service_discounted_price(
    base_price: float | int,
    service: str,
    active_discounts: list[Discount | dict[str, Any]],
) -> float:
    """Рассчитывает цену услуги с учётом скидок на данную услугу."""
    base = float(base_price)
    service_name = str(service or "").strip().lower()
    if not service_name:
        return round(base, 2)

    applicable = [
        d
        for d in active_discounts
        if _get_val(d, "kind") == "service"
        and str(_get_val(d, "service", "") or "").strip().lower() == service_name
    ]
    if not applicable:
        return round(base, 2)
    final, _ = calculate_discount(base, applicable, mode="sequential")
    return round(final, 2)


async def get_active_discounts(session: AsyncSession) -> list[Discount]:
    """Возвращает все активные скидки. Истёкшие по времени деактивируются с сохранением в БД."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Деактивируем истёкшие по дате скидки
    expire_stmt = (
        update(Discount)
        .where(
            Discount.active == 1,
            Discount.expires_at.is_not(None),
            Discount.expires_at <= now,
        )
        .values(active=0)
    )
    expire_res = await session.execute(expire_stmt)
    if expire_res.rowcount and expire_res.rowcount > 0:
        await session.commit()

    stmt = select(Discount).where(Discount.active == 1).order_by(Discount.id.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_discount_by_id(session: AsyncSession, discount_id: int) -> Discount | None:
    """Возвращает скидку по ID (без commit)."""
    return await session.get(Discount, discount_id)


async def create_discount(
    session: AsyncSession,
    *,
    kind: str,
    percent: float | int,
    value_type: str = "%",
    threshold: float | int = 0.0,
    service: str = "",
    expires_at: str | None = None,
    delete_old: bool = False,
    created_at: str | None = None,
) -> Discount:
    """Создаёт новую скидку. Если delete_old=True, отключает старые активные скидки."""
    if delete_old:
        await session.execute(update(Discount).where(Discount.active == 1).values(active=0))

    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    discount = Discount(
        kind=kind,
        threshold=float(threshold),
        service=service,
        percent=float(percent),
        value_type=value_type,
        active=1,
        created_at=created_at,
        expires_at=expires_at,
    )
    session.add(discount)
    await session.commit()
    await session.refresh(discount)
    return discount


async def deactivate_discount(session: AsyncSession, discount_id: int) -> Discount | None:
    """Деактивирует скидку по её ID."""
    discount = await session.get(Discount, discount_id)
    if not discount:
        return None
    discount.active = 0
    await session.commit()
    await session.refresh(discount)
    return discount


async def deactivate_all_discounts(session: AsyncSession) -> int:
    """Деактивирует все активные скидки."""
    stmt = update(Discount).where(Discount.active == 1).values(active=0)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def delete_discount(session: AsyncSession, discount_id: int) -> bool:
    """Удаляет скидку из БД."""
    discount = await session.get(Discount, discount_id)
    if not discount:
        return False
    await session.delete(discount)
    await session.commit()
    return True
