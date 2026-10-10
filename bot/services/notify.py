"""Сервис уведомлений администраторов и форматирования заказов."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bot.config import ADMIN_CHAT_IDS
from bot.constants import STATUS_LABELS
from bot.services.pricing import format_price

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

# Временное хранилище конфиденциальных данных заказов до выбора скидки менеджером
pending_credentials: dict[int, str] = {}

def _order_val(order: Any, key: str, default: Any = None) -> Any:
    """Универсальное чтение атрибута заказа (словарь, sqlite3.Row или ORM Order)."""
    if isinstance(order, dict):
        return order.get(key, default)
    if hasattr(order, key):
        val = getattr(order, key)
        return val if val is not None else default
    if hasattr(order, "__getitem__"):
        try:
            return order[key]
        except (KeyError, TypeError, IndexError):
            pass
    return default


def format_admin_order(row: Any) -> str:
    """Форматирует карточку заказа для панели менеджера и чатов администраторов."""
    status_raw = str(_order_val(row, "status", "new"))
    status = STATUS_LABELS.get(status_raw, status_raw)
    manager_name = _order_val(row, "manager_name") or ""
    manager = f"\n👨‍💼 Менеджер: {manager_name}" if manager_name else ""

    service = _order_val(row, "service") or "Зачистка по регионам"
    details = _order_val(row, "details") or ""
    details_str = f"\n📝 Детали: {details}" if details else ""

    price = _order_val(row, "price", 0)
    orig_price = _order_val(row, "original_price")
    discount_amount = _order_val(row, "discount_amount")

    discount_str = (
        f"\n💸 Скидка: *{format_price(discount_amount)} ₽*" if discount_amount else ""
    )
    orig_price_str = ""
    if orig_price is not None:
        try:
            if float(orig_price) != float(price):
                orig_price_str = f"\n💰 Цена без скидки: *{format_price(orig_price)} ₽*"
        except (ValueError, TypeError):
            pass

    return (
        f"🧾 *Заказ №{_order_val(row, 'id')}*\n\n"
        f"{status}\n"
        f"🕐 Создан: `{_order_val(row, 'created_at')}`\n"
        f"👤 Клиент: {_order_val(row, 'client_name')}\n"
        f"🆔 Telegram ID: `{_order_val(row, 'client_telegram_id')}`\n"
        f"📍 Регион: *{_order_val(row, 'region')}*\n"
        f"🛒 Услуга: *{service}*\n"
        f"📦 Вариант: *{_order_val(row, 'tier')}*\n"
        f"💰 Цена: *{format_price(price)} ₽*"
        + discount_str
        + orig_price_str
        + details_str
        + manager
    )


def format_client_order(row: Any) -> str:
    """Форматирует карточку заказа для списка 'Мои заказы' клиента."""
    status_raw = str(_order_val(row, "status", "new"))
    status = STATUS_LABELS.get(status_raw, status_raw)
    service = _order_val(row, "service") or "Зачистка по регионам"
    tier = _order_val(row, "tier") or "Не указан"
    region = _order_val(row, "region") or "Не указан"
    details = _order_val(row, "details") or ""
    details_str = f"\n📝 {details}" if details else ""

    order_id = _order_val(row, "id")
    is_archive = bool(_order_val(row, "_is_archive", False))
    order_label = f"архив-{order_id}" if is_archive else str(order_id)

    discount_amount = _order_val(row, "discount_amount")
    discount_str = (
        f"\n💸 Скидка: *{format_price(discount_amount)} ₽*" if discount_amount else ""
    )

    return (
        f"🧾 *Заказ №{order_label}*\n"
        f"{status}\n"
        f"🕐 {_order_val(row, 'created_at')}\n"
        f"🛒 {service}\n"
        f"📦 {tier}\n"
        f"📍 {region}\n"
        f"💰 *{format_price(_order_val(row, 'price', 0))} ₽*"
        f"{discount_str}"
        f"{details_str}"
    )


def format_order_credentials(
    order_id: int | str,
    client_name: str,
    login: str,
    password: str,
    telegram_username: str,
) -> str:
    """Форматирует конфиденциальные данные для входа в аккаунт."""
    return (
        f"🔐 *Данные для входа — заказ №{order_id}*\n\n"
        f"👤 Клиент: {client_name}\n"
        f"🔑 Логин: `{login}`\n"
        f"🔒 Пароль: `{password}`\n"
        f"💬 Telegram-юзернейм: `{telegram_username}`\n\n"
        "⚠️ Эти данные не сохраняются в orders.db. Они находятся только в памяти бота до оформления заказа и затем очищаются. "
        "После выполнения заказа рекомендуется удалить сообщение с данными для входа и изменить пароль."
    )


def is_admin_chat(chat_id: int) -> bool:
    """Проверяет, входит ли данный chat_id в список админских чатов."""
    return bool(ADMIN_CHAT_IDS and chat_id in ADMIN_CHAT_IDS)


async def send_to_admin_chats(bot: Bot, text: str, **kwargs: Any) -> tuple[int, list[int]]:
    """Отправляет уведомление во все настроенные админ-чаты (ADMIN_CHAT_IDS).

    Каждый чат обрабатывается изолированно, ошибка в одном не блокирует остальные.
    Возвращает (sent_count, list_of_failed_chat_ids).
    """
    sent = 0
    failed: list[int] = []
    for chat_id in ADMIN_CHAT_IDS:
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            sent += 1
        except Exception:
            failed.append(chat_id)
            logger.exception("Не удалось отправить уведомление в админ-чат %s", chat_id)
    return sent, failed
