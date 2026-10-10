"""Репозиторий цен зачистки по регионам (bot.db.repo.prices).

Соответствует legacy bot_ptb.py (строки 394-399, 1085-1090, 1560-1563):
- get_region_prices(session, region) с fallback на bot.prices.PRICES
- update_region_price(session, region, tier_key, value)
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import RegionPriceOverride
from bot.prices import PRICES

TIER_FIELD_MAP = {
    "0-100": "price_0_100",
    "50-100": "price_50_100",
    "80-100": "price_80_100",
}


async def get_region_prices(session: AsyncSession, region: str) -> dict[str, float]:
    """Возвращает цены уровней зачистки для региона (из БД, либо дефолт из PRICES)."""
    override = await session.get(RegionPriceOverride, region)
    if override:
        return {
            "0-100": float(override.price_0_100),
            "50-100": float(override.price_50_100),
            "80-100": float(override.price_80_100),
        }
    if region in PRICES:
        return {k: float(v) for k, v in PRICES[region].items()}
    return {"0-100": 0.0, "50-100": 0.0, "80-100": 0.0}


async def update_region_price(
    session: AsyncSession,
    region: str,
    tier_key: str,
    value: float | int,
) -> RegionPriceOverride:
    """Обновляет цену уровня зачистки для региона в region_price_overrides."""
    if tier_key not in TIER_FIELD_MAP:
        raise ValueError(f"Неизвестный уровень зачистки: {tier_key}. Допустимы: {list(TIER_FIELD_MAP.keys())}")

    field_name = TIER_FIELD_MAP[tier_key]
    override = await session.get(RegionPriceOverride, region)
    if not override:
        # Если переопределение ещё не создано, берём дефолты из PRICES
        defaults = PRICES.get(region, {"0-100": 0.0, "50-100": 0.0, "80-100": 0.0})
        override = RegionPriceOverride(
            region=region,
            price_0_100=float(defaults.get("0-100", 0.0)),
            price_50_100=float(defaults.get("50-100", 0.0)),
            price_80_100=float(defaults.get("80-100", 0.0)),
        )
        session.add(override)

    setattr(override, field_name, float(value))
    await session.commit()
    await session.refresh(override)
    return override


async def get_all_region_prices(session: AsyncSession) -> dict[str, dict[str, float]]:
    """Возвращает актуальные цены для всех регионов с учётом переопределений из БД."""
    stmt = select(RegionPriceOverride)
    result = await session.execute(stmt)
    overrides = {o.region: o for o in result.scalars().all()}

    all_prices: dict[str, dict[str, float]] = {}
    for region in PRICES:
        if region in overrides:
            o = overrides[region]
            all_prices[region] = {
                "0-100": float(o.price_0_100),
                "50-100": float(o.price_50_100),
                "80-100": float(o.price_80_100),
            }
        else:
            all_prices[region] = {k: float(v) for k, v in PRICES[region].items()}
    return all_prices
