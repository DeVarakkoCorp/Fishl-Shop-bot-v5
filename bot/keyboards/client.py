"""Клавиатуры пользовательского интерфейса (клиентские меню, выбор услуг, оформление).

Построены с использованием официального InlineKeyboardBuilder из aiogram 3.31.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants import (
    RANK57_CATEGORIES,
    RANK57_PRICES,
    REGION_TP_QUANTITY_OPTIONS,
    TIER_KEYS,
)
from bot.prices import PRICE_CATEGORIES, PRICES
from bot.services.pricing import (
    _get,
    format_price,
    price_with_discount_text_sync,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def region_tp_quantity_keyboard(order_id: int | str) -> InlineKeyboardMarkup:
    """Выбор количества телепортов (ТП) для пропорционального расчёта цены."""
    builder = InlineKeyboardBuilder()
    for q in REGION_TP_QUANTITY_OPTIONS:
        builder.button(text=f"{q} ТП", callback_data=f"region_tp_qty:{order_id}:{q}")
    builder.adjust(3)
    return builder.as_markup()


def region_keyboard(callback_prefix: str = "region") -> InlineKeyboardMarkup:
    """Список регионов для зачистки с кнопкой Назад."""
    builder = InlineKeyboardBuilder()
    for region in PRICES:
        builder.button(text=region, callback_data=f"{callback_prefix}:{region}")
    builder.adjust(2)
    builder.row()
    builder.button(text="⬅️ Назад", callback_data="back")
    return builder.as_markup()


def cleanup_region_keyboard() -> InlineKeyboardMarkup:
    """Алиас для region_keyboard (выбор региона для зачистки)."""
    return region_keyboard()


def build_tier_keyboard(
    region: str,
    prices: dict[str, float | int],
    discounts: Sequence[Any] = (),
) -> InlineKeyboardMarkup:
    """Синхронное построение клавиатуры выбора объёма зачистки региона."""
    p_0 = prices.get("0-100", PRICES.get(region, {}).get("0-100", 0))
    p_50 = prices.get("50-100", PRICES.get(region, {}).get("50-100", 0))
    p_80 = prices.get("80-100", PRICES.get(region, {}).get("80-100", 0))

    t0_text = f"0–100% — {price_with_discount_text_sync(p_0, 'Зачистка по регионам', discounts)}"
    t1_text = f"50–100% — {price_with_discount_text_sync(p_50, 'Зачистка по регионам', discounts)}"
    t2_text = f"80–100% — {price_with_discount_text_sync(p_80, 'Зачистка по регионам', discounts)}"

    builder = InlineKeyboardBuilder()
    builder.button(text=t0_text, callback_data=f"tier:{region}:0")
    builder.button(text=t1_text, callback_data=f"tier:{region}:1")
    builder.button(text=t2_text, callback_data=f"tier:{region}:2")
    builder.adjust(1)
    builder.button(text="⬅️ Назад", callback_data="cleanup")
    return builder.as_markup()


async def tier_keyboard(
    session_or_prices: AsyncSession | dict[str, float | int],
    region: str,
    discounts: Sequence[Any] = (),
) -> InlineKeyboardMarkup:
    """Клавиатура выбора процентов зачистки (0-100, 50-100, 80-100) с учётом скидок."""
    if hasattr(session_or_prices, "execute"):
        session: AsyncSession = session_or_prices
        from bot.db.repo.discounts import get_active_discounts
        from bot.db.repo.prices import get_region_prices

        prices = await get_region_prices(session, region)
        active_discounts = await get_active_discounts(session)
        return build_tier_keyboard(region, prices, active_discounts)

    return build_tier_keyboard(region, session_or_prices, discounts)


def build_service_category_keyboard(categories: Sequence[Any]) -> InlineKeyboardMarkup:
    """Построение клавиатуры категорий услуг."""
    builder = InlineKeyboardBuilder()
    for c in categories:
        builder.button(text=_get(c, "name"), callback_data=f"service_category_db:{_get(c, 'id')}")
    builder.adjust(1)
    builder.button(text="🧹 Зачистка по регионам", callback_data="cleanup_regions")
    builder.button(text="Для 57+ рангов", callback_data="service_57")
    builder.button(text="⬅️ Назад", callback_data="back")
    return builder.as_markup()


async def service_category_keyboard(session: AsyncSession) -> InlineKeyboardMarkup:
    """Загружает список активных категорий услуг из БД и строит клавиатуру."""
    from bot.db.repo.services import get_service_categories

    categories = await get_service_categories(session, active_only=True)
    return build_service_category_keyboard(categories)


def build_service_item_keyboard(category: Any, items: Sequence[Any]) -> InlineKeyboardMarkup:
    """Построение клавиатуры вариантов конкретной услуги."""
    builder = InlineKeyboardBuilder()
    if not category:
        builder.button(text="⬅️ К услугам", callback_data="cleanup")
        return builder.as_markup()

    cat_name = _get(category, "name", "")
    for item in items:
        q_mode = _get(item, "quantity_mode", "fixed")
        if cat_name == "Крутки" and q_mode == "quantity":
            continue
        unit = _get(item, "unit", "шт.")
        suffix = f" ₽/{unit}" if q_mode == "quantity" else " ₽"
        price_str = format_price(_get(item, "price", 0))
        name = _get(item, "name")
        item_id = _get(item, "id")
        builder.button(
            text=f"{name} — {price_str}{suffix}",
            callback_data=f"service_item_db:{item_id}",
        )

    builder.adjust(1)
    if cat_name == "Крутки":
        custom = next((i for i in items if _get(i, "quantity_mode") == "quantity"), None)
        if custom:
            custom_id = _get(custom, "id")
            builder.button(
                text="✏️ Ввести своё количество",
                callback_data=f"service_item_custom:{custom_id}",
            )

    builder.button(text="⬅️ К услугам", callback_data="cleanup")
    return builder.as_markup()


async def service_item_keyboard(session: AsyncSession, category_id: int) -> InlineKeyboardMarkup:
    """Загружает категорию и варианты из БД и строит клавиатуру выбора варианта."""
    from bot.db.repo.services import get_service_category, get_service_items

    category = await get_service_category(session, category_id)
    items = await get_service_items(session, category_id, active_only=True)
    return build_service_item_keyboard(category, items)


def build_price_region_keyboard(categories: Sequence[Any]) -> InlineKeyboardMarkup:
    """Построение клавиатуры раздела Прайсы."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🧹 Зачистка по регионам", callback_data="price_cleanup")
    for category in categories:
        builder.button(
            text=_get(category, "name"),
            callback_data=f"price_category_db:{_get(category, 'id')}",
        )
    builder.adjust(1)
    builder.button(text="Для 57+ рангов", callback_data="price_57")
    builder.button(text="⬅️ Назад", callback_data="back")
    return builder.as_markup()


async def price_region_keyboard(session: AsyncSession) -> InlineKeyboardMarkup:
    """Загружает категории услуг из БД и формирует меню прайсов."""
    from bot.db.repo.services import get_service_categories

    categories = await get_service_categories(session, active_only=True)
    return build_price_region_keyboard(categories)


def price_category_keyboard() -> InlineKeyboardMarkup:
    """Статическое меню категорий прайса (из legacy)."""
    builder = InlineKeyboardBuilder()
    for i, category in enumerate(PRICE_CATEGORIES):
        builder.button(text=category, callback_data=f"price_category:{i}")
    builder.adjust(1)
    builder.button(text="⬅️ К прайсам", callback_data="prices")
    return builder.as_markup()


def rank57_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Выбор раздела для 57+ рангов (Крутки, Эндгейм, Натиск, Театр)."""
    back_cb = "cleanup" if prefix == "service57_category" else "prices"
    builder = InlineKeyboardBuilder()
    for i, name in enumerate(RANK57_CATEGORIES):
        builder.button(text=name, callback_data=f"{prefix}:{i}")
    builder.adjust(1)
    builder.button(text="⬅️ Назад", callback_data=back_cb)
    return builder.as_markup()


def rank57_item_keyboard(category_index: int) -> InlineKeyboardMarkup:
    """Выбор варианта внутри раздела 57+ рангов."""
    category = RANK57_CATEGORIES[category_index]
    lines = [line.strip() for line in RANK57_PRICES[category].split("\n") if line.strip()]
    builder = InlineKeyboardBuilder()
    for i, line in enumerate(lines):
        if line == category or line.startswith("("):
            continue
        if re.search(r"\d+(?:\.5)?\s*(?:₽|руб(?:лей|ля)?|рубл(?:ей|я)?)", line, re.I):
            builder.button(
                text=line[:60],
                callback_data=f"rank57_item:{category_index}:{i}",
            )
    builder.adjust(1)
    if category == "Крутки":
        builder.button(
            text="✏️ Ввести своё количество",
            callback_data="custom_quantity:spins:57",
        )
    builder.button(text="⬅️ К услугам", callback_data="cleanup")
    return builder.as_markup()


def client_orders_keyboard() -> InlineKeyboardMarkup:
    """Меню в списке заказов клиента."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="my_orders")
    builder.button(text="🛒 Заказать услугу", callback_data="cleanup")
    builder.button(text="🏠 Главное меню", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def contact_keyboard() -> InlineKeyboardMarkup:
    """Контакты менеджера и разработчика."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 @fishlme — менеджер", url="https://t.me/fishlme")
    builder.button(text="💬 @devarapq — разработчик", url="https://t.me/devarapq")
    builder.button(text="⬅️ Назад", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def order_confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение или отмена оформления заказа перед отправкой менеджеру."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить заказ", callback_data="confirm_order")
    builder.button(text="❌ Отменить", callback_data="cancel_order")
    builder.adjust(1)
    return builder.as_markup()


def order_placed_keyboard(manager_username: str) -> InlineKeyboardMarkup:
    """Клавиатура после успешного оформления заказа (связь с менеджером и возврат в меню)."""
    username_mgr = manager_username.strip().lstrip("@")
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Связаться с менеджером", url=f"https://t.me/{username_mgr}")
    builder.button(text="🏠 Главное меню", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def price_region_view_keyboard() -> InlineKeyboardMarkup:
    """Навигация со страницы просмотра цен зачистки конкретного региона."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К зачистке", callback_data="price_cleanup")
    builder.button(text="🏠 Главное меню", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def price_category_view_keyboard() -> InlineKeyboardMarkup:
    """Навигация со страницы просмотра прайса услуги."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К прайсам", callback_data="prices")
    builder.button(text="🏠 Главное меню", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def price_57_view_keyboard() -> InlineKeyboardMarkup:
    """Навигация со страницы просмотра прайса 57+ рангов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К 57+", callback_data="price_57")
    builder.button(text="🏠 Главное меню", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


__all__ = [
    "region_tp_quantity_keyboard",
    "region_keyboard",
    "cleanup_region_keyboard",
    "build_tier_keyboard",
    "tier_keyboard",
    "build_service_category_keyboard",
    "service_category_keyboard",
    "build_service_item_keyboard",
    "service_item_keyboard",
    "build_price_region_keyboard",
    "price_region_keyboard",
    "price_category_keyboard",
    "rank57_keyboard",
    "rank57_item_keyboard",
    "client_orders_keyboard",
    "contact_keyboard",
    "order_confirm_keyboard",
    "order_placed_keyboard",
    "price_region_view_keyboard",
    "price_category_view_keyboard",
    "price_57_view_keyboard",
]
