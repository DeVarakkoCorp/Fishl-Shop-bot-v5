"""Конфигурация приложения Fishl Shop бота.

Поддерживает переменные окружения, типизированный класс Settings и обратную совместимость
со всеми существующими импортами в проекте.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Типизированные настройки бота."""

    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    shop_name: str = field(default_factory=lambda: os.getenv("SHOP_NAME", "Fishl Shop"))

    # Основной контакт и список менеджеров
    manager_username: str = field(
        default_factory=lambda: os.getenv("MANAGER_USERNAME", "devarapq").strip().lstrip("@")
    )
    manager_usernames: frozenset[str] = field(
        default_factory=lambda: frozenset(
            u.strip().lstrip("@").lower()
            for u in os.getenv("MANAGER_USERNAMES", "devarapq,fishlme").split(",")
            if u.strip()
        )
    )

    # Административные чаты
    admin_chat_id: int = field(
        default_factory=lambda: int(os.getenv("ADMIN_CHAT_ID", "0")) if os.getenv("ADMIN_CHAT_ID", "0").lstrip("-").isdigit() else 0
    )
    admin_chat_ids: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(v.strip())
            for v in os.getenv("ADMIN_CHAT_IDS", "").split(",")
            if v.strip().lstrip("-").isdigit()
        )
    )

    # База данных: DATABASE_URL (PostgreSQL / SQLite) или путь к локальной sqlite-базе
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "")
    )
    railway_volume_mount_path: str = field(
        default_factory=lambda: os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
    )

    # Резервное копирование на GitHub
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_repo: str = field(default_factory=lambda: os.getenv("GITHUB_REPO", ""))
    github_backup_branch: str = field(
        default_factory=lambda: os.getenv("GITHUB_BACKUP_BRANCH", "backups")
    )
    github_backup_path: str = field(
        default_factory=lambda: os.getenv("GITHUB_BACKUP_PATH", "backups/orders")
    )
    github_backup_interval_minutes: int = field(
        default_factory=lambda: int(os.getenv("GITHUB_BACKUP_INTERVAL_MINUTES", "360"))
    )

    def resolved_admin_chat_ids(self) -> list[int]:
        """Возвращает объединённый упорядоченный список чатов администраторов."""
        chat_ids = list(self.admin_chat_ids)
        if self.admin_chat_id and self.admin_chat_id not in chat_ids:
            chat_ids.insert(0, self.admin_chat_id)
        return chat_ids


# Инициализация глобального объекта настроек
settings = Settings()

# Экспорт для обратной совместимости со старыми модулями
BOT_TOKEN = settings.bot_token
SHOP_NAME = settings.shop_name
MANAGER_USERNAME = settings.manager_username
MANAGER_USERNAMES = set(settings.manager_usernames)
ADMIN_CHAT_ID = settings.admin_chat_id
ADMIN_CHAT_IDS = settings.resolved_admin_chat_ids()

DATABASE_URL = settings.database_url
RAILWAY_VOLUME_MOUNT_PATH = settings.railway_volume_mount_path

GITHUB_TOKEN = settings.github_token
GITHUB_REPO = settings.github_repo
GITHUB_BACKUP_BRANCH = settings.github_backup_branch
GITHUB_BACKUP_PATH = settings.github_backup_path
GITHUB_BACKUP_INTERVAL_MINUTES = settings.github_backup_interval_minutes

__all__ = [
    "Settings",
    "settings",
    "BOT_TOKEN",
    "SHOP_NAME",
    "MANAGER_USERNAME",
    "MANAGER_USERNAMES",
    "ADMIN_CHAT_ID",
    "ADMIN_CHAT_IDS",
    "DATABASE_URL",
    "RAILWAY_VOLUME_MOUNT_PATH",
    "GITHUB_TOKEN",
    "GITHUB_REPO",
    "GITHUB_BACKUP_BRANCH",
    "GITHUB_BACKUP_PATH",
    "GITHUB_BACKUP_INTERVAL_MINUTES",
]
