"""Типизированные CallbackData модели для aiogram 3.31 (bot.callbacks).

Использование CallbackData вместо сырых строк и split(":") обеспечивает:
- Строгую типизацию полей (int, str, float)
- Валидацию данных на этапе разбора апдейта
- Автокомплит в IDE и отсутствие опечаток в префиксах
- Чистый декларативный синтаксис роутинга: HandlerName.filter(...)
"""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


# =========================================================================
# Клиентские CallbackData
# =========================================================================

class OrderRegionCallback(CallbackData, prefix="region"):
    """Выбор региона для зачистки."""
    region: str


class OrderTierCallback(CallbackData, prefix="tier"):
    """Выбор уровня/процента зачистки (0-100, 50-100, 80-100)."""
    region: str
    tier_index: int


class RegionTpQuantityCallback(CallbackData, prefix="region_tp_qty"):
    """Выбор количества телепортов (ТП) для пропорционального расчёта."""
    order_id: str
    quantity: int


class PriceRegionCallback(CallbackData, prefix="price_region"):
    """Просмотр карточки цен конкретного региона."""
    region: str


class PriceCategoryDbCallback(CallbackData, prefix="price_category_db"):
    """Просмотр прайса динамической категории из БД."""
    category_id: int


class PriceCategoryLegacyCallback(CallbackData, prefix="price_category"):
    """Просмотр прайса статического раздела из EXTRA_PRICES."""
    index: int


class Rank57PriceCategoryCallback(CallbackData, prefix="rank57_price_category"):
    """Детальный прайс категории 57+ рангов."""
    index: int


class ServiceCategoryDbCallback(CallbackData, prefix="service_category_db"):
    """Выбор динамической категории услуг при заказе."""
    category_id: int


class ServiceCategoryLegacyCallback(CallbackData, prefix="service_category"):
    """Legacy-выбор категории услуг по индексу."""
    index: int


class ServiceItemDbCallback(CallbackData, prefix="service_item_db"):
    """Выбор конкретного варианта услуги из БД."""
    item_id: int


class ServiceItemCustomCallback(CallbackData, prefix="service_item_custom"):
    """Запрос кастомного количества для услуги с quantity_mode='quantity'."""
    item_id: int


class CustomQuantityLegacyCallback(CallbackData, prefix="custom_quantity"):
    """Legacy-запрос количества (spins, dikovinki, okuly)."""
    kind: str
    value: str


class ServiceItemLegacyCallback(CallbackData, prefix="service_item"):
    """Legacy-выбор варианта услуги по индексам категории и пункта."""
    category_index: int
    item_index: int


class Service57CategoryCallback(CallbackData, prefix="service57_category"):
    """Список вариантов услуг раздела 57+ рангов."""
    index: int


class Rank57ItemSelectCallback(CallbackData, prefix="rank57_item"):
    """Выбор пункта услуги 57+ рангов."""
    category_index: int
    item_index: int


# =========================================================================
# Менеджерские CallbackData
# =========================================================================

class OrderStatusCallback(CallbackData, prefix="order_status"):
    """Смена статуса заказа менеджером."""
    order_id: str
    status: str


class ManagerOrderTakeCallback(CallbackData, prefix="mgr_order_take"):
    """Взять заказ в работу."""
    order_id: str


class ManagerOrderDoneCallback(CallbackData, prefix="mgr_order_done"):
    """Отметить заказ выполненным."""
    order_id: str


class ManagerOrderCancelCallback(CallbackData, prefix="mgr_order_cancel"):
    """Отказаться от заказа / отменить заказ."""
    order_id: str


class ManagerDiscountTypeCallback(CallbackData, prefix="mgr_discount_type"):
    """Выбор типа скидки: threshold / service."""
    kind: str


class ManagerDiscountValueTypeCallback(CallbackData, prefix="mgr_discount_value_type"):
    """Выбор единицы скидки: RUB / %."""
    vtype: str


class ManagerDiscountChoiceCallback(CallbackData, prefix="mgr_discount_choice"):
    """Выбор способа применения скидки (автоматически, последовательно, сложение и т.д.)."""
    order_id: str
    choice: str


class ManagerDiscountToggleCallback(CallbackData, prefix="mgr_discount_toggle"):
    """Переключение активности скидки."""
    discount_id: int


class ManagerDiscountDeleteCallback(CallbackData, prefix="mgr_discount_del"):
    """Удаление скидки."""
    discount_id: int


class ManagerServiceEditCallback(CallbackData, prefix="mgr_service_edit_item"):
    """Редактирование цены услуги."""
    item_id: int


__all__ = [
    "OrderRegionCallback",
    "OrderTierCallback",
    "RegionTpQuantityCallback",
    "PriceRegionCallback",
    "PriceCategoryDbCallback",
    "PriceCategoryLegacyCallback",
    "Rank57PriceCategoryCallback",
    "ServiceCategoryDbCallback",
    "ServiceCategoryLegacyCallback",
    "ServiceItemDbCallback",
    "ServiceItemCustomCallback",
    "CustomQuantityLegacyCallback",
    "ServiceItemLegacyCallback",
    "Service57CategoryCallback",
    "Rank57ItemSelectCallback",
    "OrderStatusCallback",
    "ManagerOrderTakeCallback",
    "ManagerOrderDoneCallback",
    "ManagerOrderCancelCallback",
    "ManagerDiscountTypeCallback",
    "ManagerDiscountValueTypeCallback",
    "ManagerDiscountChoiceCallback",
    "ManagerDiscountToggleCallback",
    "ManagerDiscountDeleteCallback",
    "ManagerServiceEditCallback",
]
