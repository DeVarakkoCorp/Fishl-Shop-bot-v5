"""Пакет репозиториев базы данных."""
from bot.db.repo import discounts, orders, prices, services

__all__ = [
    "discounts",
    "orders",
    "prices",
    "services",
]
