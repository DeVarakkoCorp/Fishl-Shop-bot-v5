"""Функции формирования и форматирования текстов сообщений Fishl Shop."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Sequence

from bot.constants import (
    RANK57_CATEGORIES,
    RANK57_PRICES,
    TIER_NAMES,
)
from bot.services.pricing import (
    _get,
    calculate_service_discounted_price,
    discount_kind_label,
    discount_value_label,
    format_price,
    price_with_discount_text_sync,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def format_service_category_text(
    category_name: str,
    items: Sequence[Any],
    discounts: Sequence[Any] = (),
) -> str:
    """Формирует текстовый список вариантов услуги с ценами и скидками."""
    if not category_name:
        return ""
    lines = [category_name]
    for item in items:
        name = _get(item, "name")
        q_mode = _get(item, "quantity_mode", "fixed")
        unit = _get(item, "unit", "шт.")
        price = _get(item, "price", 0)

        # Для круток вариант со свободным количеством не выводим в общий список
        if category_name == "Крутки" and q_mode == "quantity":
            continue

        shown = price_with_discount_text_sync(price, category_name, discounts)
        if q_mode == "quantity":
            lines.append(f"{name} — {shown}/{unit}")
        else:
            lines.append(f"{name} — {shown}")
    return "\n".join(lines)


async def service_category_text(session: AsyncSession, category_id: int) -> str:
    """Загружает услугу, её пункты и активные скидки из БД и формирует текст описания."""
    from bot.db.repo.discounts import get_active_discounts
    from bot.db.repo.services import get_service_category, get_service_items

    category = await get_service_category(session, category_id)
    if not category:
        return ""
    items = await get_service_items(session, category_id)
    discounts = await get_active_discounts(session)
    category_name = _get(category, "name")
    return format_service_category_text(category_name, items, discounts)


def format_rank57_prices_sync(category: str, discounts: Sequence[Any] = ()) -> str:
    """Заменяет цены в тексте прайса 57+ рангов на цены с учётом действующих скидок."""
    text = RANK57_PRICES.get(category, "")
    if not text:
        return ""

    def replace_price(match: re.Match[str]) -> str:
        value = float(match.group(1))
        final = calculate_service_discounted_price(value, category, discounts)
        if final < value:
            return f"{format_price(final)} ₽ (было {format_price(value)} ₽)"
        return match.group(0)

    return re.sub(
        r"(\d+(?:\.5)?)\s*(?:₽|руб(?:лей|ля)?|рубл(?:ей|я)?)",
        replace_price,
        text,
        flags=re.I,
    )


async def format_rank57_prices(
    session_or_category: AsyncSession | str,
    category_or_discounts: str | Sequence[Any] = (),
) -> str:
    """Асинхронное или синхронное форматирование цен раздела 57+ рангов со скидками."""
    if hasattr(session_or_category, "execute"):
        session: AsyncSession = session_or_category
        category = str(category_or_discounts)
        from bot.db.repo.discounts import get_active_discounts

        discounts = await get_active_discounts(session)
        return format_rank57_prices_sync(category, discounts)

    category = str(session_or_category)
    discounts = (
        category_or_discounts
        if isinstance(category_or_discounts, (list, tuple))
        else ()
    )
    return format_rank57_prices_sync(category, discounts)


def rank57_item_data(category_index: int, item_index: int) -> tuple[str, str, int] | None:
    """Извлекает название услуги, строку варианта и цену из раздела 57+ по индексам."""
    if category_index < 0 or category_index >= len(RANK57_CATEGORIES):
        return None
    category = RANK57_CATEGORIES[category_index]
    lines = [line.strip() for line in RANK57_PRICES[category].split("\n") if line.strip()]
    if item_index < 0 or item_index >= len(lines):
        return None
    line = lines[item_index]
    if line == category or line.startswith("("):
        return None
    match = re.search(r"(\d+(?:\.5)?)\s*(?:₽|руб(?:лей|ля)?|рубл(?:ей|я)?)", line, re.I)
    if not match:
        return None
    price = int(float(match.group(1)))
    return category, line, price


def format_discount_choice(order_id: int | str, rows: Sequence[Any]) -> str:
    """Текст запроса к менеджеру о способе применения нескольких скидок к заказу."""
    lines = [f"🏷 *Для заказа №{order_id} доступны скидки:*", ""]
    for row in rows:
        lines.append(f"• {discount_kind_label(row)} — *{discount_value_label(row)}*")
    lines += [
        "",
        "Выбери, как применить скидки:",
        "• *Сложить проценты* — например 10% + 5% = 15%.",
        "• *Последовательно* — сначала скидка на весь заказ, затем на конкретную услугу.",
    ]
    return "\n".join(lines)


def format_order_summary(
    client_name: str,
    telegram_username: str,
    region: str | None,
    service: str | None,
    service_item: str | None,
    tier_index: int | None,
    base_price: float | int,
    final_price: float | int,
    discount_amount: float | int = 0,
    details: str | None = None,
) -> str:
    """Формирует карточку проверки заказа перед отправкой клиентом."""
    if tier_index is not None and 0 <= tier_index < len(TIER_NAMES):
        service_line = f"🧹 Зачистка: *{TIER_NAMES[tier_index]}*"
    else:
        service_line = f"🛒 Услуга: *{service or ''}*\n📦 Вариант: *{service_item or ''}*"

    details_line = (
        f"\n📝 Детали: {details}"
        if details and str(details).strip().upper() != "НЕТ"
        else ""
    )

    if discount_amount > 0:
        price_line = (
            f"💰 Цена: *{format_price(final_price)} ₽* (было {format_price(base_price)} ₽)\n"
            f"💸 Скидка: *{format_price(discount_amount)} ₽*"
        )
    else:
        price_line = f"💰 Цена: *{format_price(base_price)} ₽*"

    return (
        "🧾 *Проверь заказ*\n\n"
        f"👤 Клиент: {client_name}\n"
        f"💬 Telegram: *{telegram_username}*\n"
        f"📍 Регион: *{region or 'Не требуется'}*\n"
        f"{service_line}\n"
        f"{price_line}"
        f"{details_line}\n\n"
        "🔐 Данные для входа будут переданы менеджерам только после подтверждения заказа.\n\n"
        "⚠️ После выполнения заказа рекомендуется изменить пароль.\n\n"
        "Всё верно?"
    )
