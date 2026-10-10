"""Фильтры aiogram."""
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot.config import MANAGER_USERNAMES


def normalize_username(username: str | None) -> str:
    return (username or "").strip().lstrip("@").lower()


def is_manager_user(user) -> bool:
    return bool(user and normalize_username(user.username) in MANAGER_USERNAMES)


class IsManager(BaseFilter):
    """Доступ только для менеджеров (по username из MANAGER_USERNAMES)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return is_manager_user(event.from_user)
