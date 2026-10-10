"""Клавиатуры панели менеджера (управление заказами, скидками, услугами и ценами).

Построены с использованием official InlineKeyboardBuilder из aiogram 3.31.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.prices import PRICES
from bot.services.pricing import _get, format_price

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def manager_keyboard() -> InlineKeyboardMarkup:
    """Возвращает главное меню панели менеджера."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Все заказы", callback_data="mgr_all_orders")
    builder.button(text="➕ Добавить скидку", callback_data="mgr_discount_add")
    builder.button(text="📋 Активные скидки", callback_data="mgr_discount_list")
    builder.button(text="🗑 Управление скидками", callback_data="mgr_discount_manage")
    builder.button(text="🛠 Услуги и цены", callback_data="mgr_services")
    builder.button(text="🖼 Баннеры", callback_data="mgr_banners")
    builder.button(text="💾 Сделать бэкап", callback_data="mgr_backup")
    builder.adjust(1)
    return builder.as_markup()


MANAGER_MENU = manager_keyboard()


def admin_keyboard(order_id: int | str, status: str = "new") -> InlineKeyboardMarkup | None:
    """Кнопки смены статуса заказа менеджером."""
    builder = InlineKeyboardBuilder()
    if status in ("new", "taken"):
        builder.button(text="🔵 Взять в работу", callback_data=f"order_status:{order_id}:working")
        builder.button(text="❌ Отказаться", callback_data=f"order_status:{order_id}:cancelled")
        builder.adjust(1)
        return builder.as_markup()
    elif status == "working":
        builder.button(text="✅ Выполнить", callback_data=f"order_status:{order_id}:done")
        builder.button(text="❌ Отказаться", callback_data=f"order_status:{order_id}:cancelled")
        builder.adjust(1)
        return builder.as_markup()
    return None


def manager_all_orders_keyboard() -> InlineKeyboardMarkup:
    """Меню обновления списка всех заказов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="mgr_all_orders")
    builder.button(text="⬅️ Панель менеджера", callback_data="mgr_panel")
    builder.adjust(1)
    return builder.as_markup()


def manager_services_menu_keyboard() -> InlineKeyboardMarkup:
    """Раздел 'Услуги и цены' панели менеджера."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить услугу", callback_data="mgr_service_add")
    builder.button(text="➕ Добавить вариант", callback_data="mgr_service_item_add")
    builder.button(text="✏️ Изменить цену услуги", callback_data="mgr_service_edit")
    builder.button(text="🧹 Изменить цены зачистки", callback_data="mgr_region_edit")
    builder.button(text="📋 Список услуг", callback_data="mgr_service_list")
    builder.button(text="🏠 Панель менеджера", callback_data="mgr_panel")
    builder.adjust(1)
    return builder.as_markup()


def manager_discount_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа создаваемой скидки: от суммы заказа или на услугу."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 От суммы заказа", callback_data="mgr_discount_type:threshold")
    builder.button(text="🛒 На конкретную услугу", callback_data="mgr_discount_type:service")
    builder.button(text="⬅️ Назад", callback_data="mgr_panel")
    builder.adjust(1)
    return builder.as_markup()


def manager_discount_value_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор единицы скидки: рубли или проценты."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 В рублях", callback_data="mgr_discount_value_type:RUB")
    builder.button(text="📉 В процентах", callback_data="mgr_discount_value_type:%")
    builder.button(text="⬅️ Назад", callback_data="mgr_discount_add")
    builder.adjust(1)
    return builder.as_markup()


def manager_discount_period_keyboard() -> InlineKeyboardMarkup:
    """Выбор срока действия скидки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="♾ Без срока", callback_data="mgr_discount_period:none")
    builder.button(text="📅 1 день", callback_data="mgr_discount_period:1")
    builder.button(text="📅 7 дней", callback_data="mgr_discount_period:7")
    builder.button(text="📅 30 дней", callback_data="mgr_discount_period:30")
    builder.button(text="🗓 До указанной даты", callback_data="mgr_discount_period:custom")
    builder.adjust(1)
    return builder.as_markup()


def manager_discount_replace_keyboard() -> InlineKeyboardMarkup:
    """Выбор: оставить старые активные скидки или удалить перед созданием новой."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оставить старые", callback_data="mgr_discount_keep")
    builder.button(text="🗑 Удалить старые", callback_data="mgr_discount_replace")
    builder.adjust(1)
    return builder.as_markup()


def manager_discount_choice_keyboard(order_id: int | str) -> InlineKeyboardMarkup:
    """Выбор менеджером метода применения нескольких скидок к заказу."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Сложить проценты", callback_data=f"discount_sum:{order_id}")
    builder.button(text="🔄 Последовательно", callback_data=f"discount_seq:{order_id}")
    builder.adjust(1)
    return builder.as_markup()


def manager_discount_manage_keyboard(rows: Sequence[Any]) -> InlineKeyboardMarkup:
    """Список активных скидок с кнопками отключения."""
    builder = InlineKeyboardBuilder()
    for r in rows:
        builder.button(
            text=f"❌ Отключить #{_get(r, 'id')}",
            callback_data=f"mgr_discount_disable:{_get(r, 'id')}",
        )
    builder.adjust(1)
    builder.button(text="⬅️ Назад", callback_data="mgr_panel")
    return builder.as_markup()


async def manager_discount_manage_keyboard_db(session: AsyncSession) -> InlineKeyboardMarkup:
    """Загружает скидки из БД и строит клавиатуру управления ими."""
    from bot.db.repo.discounts import get_active_discounts

    rows = await get_active_discounts(session)
    return manager_discount_manage_keyboard(rows)


def manager_service_list_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата из текстового списка всех услуг."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Услуги и цены", callback_data="mgr_services")
    return builder.as_markup()


def manager_service_select_category_keyboard(
    categories: Sequence[Any],
    prefix: str = "mgr_service_item_category",
) -> InlineKeyboardMarkup:
    """Выбор категории для добавления варианта или редактирования цен."""
    builder = InlineKeyboardBuilder()
    for c in categories:
        builder.button(
            text=_get(c, "name"),
            callback_data=f"{prefix}:{_get(c, 'id')}",
        )
    builder.adjust(1)
    builder.button(text="⬅️ Услуги и цены", callback_data="mgr_services")
    return builder.as_markup()


async def manager_service_select_category_keyboard_db(
    session: AsyncSession,
    prefix: str = "mgr_service_item_category",
) -> InlineKeyboardMarkup:
    """Загружает категории услуг из БД и строит клавиатуру выбора."""
    from bot.db.repo.services import get_service_categories

    categories = await get_service_categories(session, active_only=False)
    return manager_service_select_category_keyboard(categories, prefix=prefix)


def manager_service_select_item_keyboard(items: Sequence[Any]) -> InlineKeyboardMarkup:
    """Выбор варианта услуги для изменения цены."""
    builder = InlineKeyboardBuilder()
    for i in items:
        builder.button(
            text=f"{_get(i, 'name')} — {format_price(_get(i, 'price'))} ₽",
            callback_data=f"mgr_service_price:{_get(i, 'id')}",
        )
    builder.adjust(1)
    builder.button(text="⬅️ Услуги и цены", callback_data="mgr_services")
    return builder.as_markup()


async def manager_service_select_item_keyboard_db(
    session: AsyncSession,
    category_id: int,
) -> InlineKeyboardMarkup:
    """Загружает варианты услуги из БД и строит клавиатуру выбора пункта."""
    from bot.db.repo.services import get_service_items

    items = await get_service_items(session, category_id, active_only=False)
    return manager_service_select_item_keyboard(items)


def manager_region_select_keyboard() -> InlineKeyboardMarkup:
    """Выбор региона для изменения цен зачистки."""
    builder = InlineKeyboardBuilder()
    for r in PRICES:
        builder.button(text=r, callback_data=f"mgr_region:{r}")
    builder.adjust(2)
    builder.row()
    builder.button(text="⬅️ Услуги и цены", callback_data="mgr_services")
    return builder.as_markup()


def manager_region_tiers_keyboard(
    region: str,
    prices: dict[str, float | int],
) -> InlineKeyboardMarkup:
    """Выбор яруса зачистки (0-100, 50-100, 80-100) для изменения цены региона."""
    p_0 = prices.get("0-100", PRICES.get(region, {}).get("0-100", 0))
    p_50 = prices.get("50-100", PRICES.get(region, {}).get("50-100", 0))
    p_80 = prices.get("80-100", PRICES.get(region, {}).get("80-100", 0))

    builder = InlineKeyboardBuilder()
    builder.button(text=f"0–100% — {format_price(p_0)} ₽", callback_data=f"mgr_region_price:{region}:0-100")
    builder.button(text=f"50–100% — {format_price(p_50)} ₽", callback_data=f"mgr_region_price:{region}:50-100")
    builder.button(text=f"80–100% — {format_price(p_80)} ₽", callback_data=f"mgr_region_price:{region}:80-100")
    builder.adjust(1)
    builder.button(text="⬅️ Цены зачистки", callback_data="mgr_region_edit")
    return builder.as_markup()


async def manager_region_tiers_keyboard_db(
    session: AsyncSession,
    region: str,
) -> InlineKeyboardMarkup:
    """Загружает актуальные цены зачистки региона из БД и строит клавиатуру."""
    from bot.db.repo.prices import get_region_prices

    prices = await get_region_prices(session, region)
    return manager_region_tiers_keyboard(region, prices)


def manager_back_to_panel_keyboard() -> InlineKeyboardMarkup:
    """Возврат в корень панели менеджера."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="mgr_panel")
    return builder.as_markup()


def manager_banners_menu_keyboard(banners: dict[str, Any]) -> InlineKeyboardMarkup:
    """Список разделов с индикацией наличия баннера."""
    from bot.db.repo.banners import BANNER_SECTIONS

    builder = InlineKeyboardBuilder()
    for key, title in BANNER_SECTIONS.items():
        has_banner = key in banners and bool(getattr(banners[key], "file_id", None))
        status = "✅" if has_banner else "⚪"
        builder.button(text=f"{title} {status}", callback_data=f"mgr_banner_view:{key}")
    builder.adjust(1)
    builder.button(text="⬅️ Панель менеджера", callback_data="mgr_panel")
    return builder.as_markup()


def manager_banner_item_keyboard(key: str, has_banner: bool) -> InlineKeyboardMarkup:
    """Действия с баннером конкретного раздела."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Загрузить баннер", callback_data=f"mgr_banner_upload:{key}")
    if has_banner:
        builder.button(text="🗑 Удалить баннер", callback_data=f"mgr_banner_delete:{key}")
    builder.adjust(1)
    builder.button(text="⬅️ К разделам", callback_data="mgr_banners")
    return builder.as_markup()


def manager_banner_cancel_keyboard(key: str) -> InlineKeyboardMarkup:
    """Кнопка отмены при ожидании загрузки фото баннера."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=f"mgr_banner_view:{key}")
    return builder.as_markup()


__all__ = [
    "manager_keyboard",
    "MANAGER_MENU",
    "admin_keyboard",
    "manager_all_orders_keyboard",
    "manager_services_menu_keyboard",
    "manager_discount_type_keyboard",
    "manager_discount_value_type_keyboard",
    "manager_discount_period_keyboard",
    "manager_discount_replace_keyboard",
    "manager_discount_choice_keyboard",
    "manager_discount_manage_keyboard",
    "manager_discount_manage_keyboard_db",
    "manager_service_list_back_keyboard",
    "manager_service_select_category_keyboard",
    "manager_service_select_category_keyboard_db",
    "manager_service_select_item_keyboard",
    "manager_service_select_item_keyboard_db",
    "manager_region_select_keyboard",
    "manager_region_tiers_keyboard",
    "manager_region_tiers_keyboard_db",
    "manager_back_to_panel_keyboard",
    "manager_banners_menu_keyboard",
    "manager_banner_item_keyboard",
    "manager_banner_cancel_keyboard",
]
