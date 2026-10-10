"""Инициализация динамических услуг и цен в БД (seed).

Соответствует 1-в-1 legacy bot_ptb.py (строки 338, 343-373).
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import RegionPriceOverride, ServiceCategory, ServiceItem
from bot.prices import EXTRA_PRICES, PRICE_CATEGORIES, PRICES

logger = logging.getLogger(__name__)

try:
    from bot.constants import DIKOVINKI_PRICES, OKULY_PRICES
except ImportError:
    # Fallback, если bot.constants ещё не создан другим агентом
    DIKOVINKI_PRICES = {
        "Мондштадт": 1.0,
        "Ли Юэ": 1.5,
        "Инадзума": 1.5,
        "Сумеру": 2.0,
        "Фонтейн": 1.5,
        "Натлан, Снежная": 2.0,
    }
    OKULY_PRICES = [
        ("Анемокулы", 200),
        ("Геокулы", 1000),
        ("Багровые агаты", 500),
        ("Электрокулы", 700),
        ("Адъюванты светоносного камня", 550),
        ("Гидрокулы", 1200),
        ("Оперенья очищающего света", 690),
        ("Кои карпы", 1100),
        ("Пирокулы", 550),
        ("Лунокулы", 1500),
        ("Лунокулы — на данный момент", 1000),
        ("Криокулы", 1500),
    ]


async def seed_dynamic_services(session: AsyncSession) -> None:
    """Заполняет категории услуг, услуги и дефолтные цены зачистки, если таблица пуста.

    Также исправляет устаревший плейсхолдер 'Тп в ???' (legacy стр. 338).
    """
    count_stmt = select(func.count(ServiceCategory.id))
    existing = (await session.execute(count_stmt)).scalar_one()

    if existing == 0:
        logger.info("Заполняем service_categories и service_items начальными данными...")
        for cat_index, category in enumerate(PRICE_CATEGORIES):
            cat = ServiceCategory(name=category, active=1, sort_order=cat_index)
            session.add(cat)
            await session.flush()
            category_id = cat.id

            if category == "Крутки":
                items = [
                    ("1 крутка", 24.0, "fixed", "крутка"),
                    ("10 круток", 240.0, "fixed", "комплект"),
                    ("100 круток", 2400.0, "fixed", "комплект"),
                    ("Своя количество", 24.0, "quantity", "крутка"),
                ]
            elif category == "Диковинки":
                items = [
                    (region, float(price), "quantity", "шт.")
                    for region, price in DIKOVINKI_PRICES.items()
                ]
            elif category == "Окулы":
                items = [
                    (name, float(price), "quantity", "шт.")
                    for name, price in OKULY_PRICES
                ]
            else:
                items = []
                for line in [line.strip() for line in EXTRA_PRICES[category].split("\n") if line.strip()]:
                    if (
                        line.startswith("Уточняйте в лс")
                        or line.startswith("(")
                        or line in {"КРУТКИ", "ЭНДГЕЙМ", "НАТИСК", "Театр🌟"}
                    ):
                        continue
                    match = re.search(r"(\d+(?:\.5)?)\s*(?:₽|руб(?:лей|ля)?|рубл(?:ей|я)?)", line, re.I)
                    if not match:
                        continue
                    name = line
                    if category == "Телепорты":
                        name = re.sub(r"Тп в \?\?\?", "Тп в любые доп. локации", name, flags=re.I)
                        mode, unit = "quantity", "ТП"
                    else:
                        mode, unit = "fixed", "шт."
                    items.append((name, float(match.group(1)), mode, unit))

            for item_index, (name, price, mode, unit) in enumerate(items):
                item = ServiceItem(
                    category_id=category_id,
                    name=name,
                    price=price,
                    quantity_mode=mode,
                    unit=unit,
                    active=1,
                    sort_order=item_index,
                )
                session.add(item)

        for region, values in PRICES.items():
            existing_override = await session.get(RegionPriceOverride, region)
            if not existing_override:
                override = RegionPriceOverride(
                    region=region,
                    price_0_100=float(values["0-100"]),
                    price_50_100=float(values["50-100"]),
                    price_80_100=float(values["80-100"]),
                )
                session.add(override)

    # Фикс старого плейсхолдера телепортов из legacy стр. 338
    fix_stmt = (
        update(ServiceItem)
        .where(ServiceItem.name.like("%Тп в ???%"))
        .values(name="Тп в любые доп. локации (1шт)")
    )
    await session.execute(fix_stmt)
    await session.commit()
