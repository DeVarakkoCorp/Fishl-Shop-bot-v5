"""FSM-состояния aiogram 3.31 (bot.states).

Определяет группы состояний (StatesGroup) для:
- Оформления заказов клиентом (OrderFlow)
- Управления услугами и ценами менеджером (ManagerService)
- Создания и настройки скидок менеджером (ManagerDiscount)
"""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    """Клиентский сценарий оформления заказа."""

    # Гранулярные состояния aiogram 3
    quantity = State()
    login = State()
    password = State()
    telegram_username = State()
    confirm = State()

    # Общее состояние для совместимости с тестами и шаговым контроллером
    waiting_input = State()


class ManagerService(StatesGroup):
    """Сценарии добавления и редактирования услуг и цен."""

    name = State()
    price = State()
    item_name = State()
    item_price = State()
    region_price = State()


class ManagerDiscount(StatesGroup):
    """Сценарий создания скидки менеджером."""

    threshold = State()
    service = State()
    value = State()
    expires_at = State()

class ManagerBanner(StatesGroup):
    """Сценарий установки баннера раздела менеджером."""
    waiting_photo = State()


__all__ = [
    "OrderFlow",
    "ManagerService",
    "ManagerDiscount",
    "ManagerBanner",
]
