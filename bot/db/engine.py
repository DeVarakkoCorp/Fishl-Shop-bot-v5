"""Async engine для SQLite (WAL) / PostgreSQL и фабрика сессий (bot.db.engine).

Предоставляет:
- Автоматическую настройку URL: из DATABASE_URL или Railway Volume / локальной директории
- Оптимизированные PRAGMA для SQLite (WAL, NORMAL sync, busy_timeout, foreign keys, 64MB cache)
- Поддержку connection pool pre-ping и pool recycle
- Асинхронный контекстный менеджер get_session() для удобной работы в сервисах и задачах
- Полную обратную совместимость со всеми тестами и вызовами
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]

# Railway Volume: RAILWAY_VOLUME_MOUNT_PATH, иначе ./data
DATA_DIR = Path(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", str(BASE_DIR / "data")))
DB_PATH = DATA_DIR / "orders.db"

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def resolve_database_url(db_path: Path | str | None = None) -> str:
    """Определяет итоговый URL подключения к базе данных."""
    # Если явно передан путь к файлу (например, в pytest фикстуре)
    if db_path is not None:
        p = Path(db_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{p.as_posix()}"

    # Если задан DATABASE_URL в окружении
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        # Корректировка префикса для asyncpg, если указан postgres://
        if env_url.startswith("postgres://"):
            env_url = env_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif env_url.startswith("postgresql://") and not env_url.startswith("postgresql+asyncpg://"):
            env_url = env_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return env_url

    # По умолчанию — SQLite файл на persistent volume
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"


def make_engine(db_path: Path | str | None = None) -> AsyncEngine:
    """Создаёт сконфигурированный AsyncEngine."""
    db_url = resolve_database_url(db_path)
    is_sqlite = db_url.startswith("sqlite")

    engine_kwargs: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }

    if not is_sqlite:
        engine_kwargs.update({
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        })

    engine = create_async_engine(db_url, **engine_kwargs)

    if is_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=10000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA cache_size=-64000")  # 64MB cache
            cur.close()

    return engine


def init_engine(db_path: Path | str | None = None) -> async_sessionmaker[AsyncSession]:
    """Создаёт глобальные engine и sessionmaker (вызывается один раз при старте)."""
    global _engine, _sessionmaker
    _engine = make_engine(db_path)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _sessionmaker


def get_engine() -> AsyncEngine:
    """Возвращает инициализированный AsyncEngine."""
    assert _engine is not None, "init_engine() не был вызван перед обращением к get_engine()"
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Возвращает инициализированную фабрику сессий."""
    assert _sessionmaker is not None, "init_engine() не был вызван перед обращением к get_sessionmaker()"
    return _sessionmaker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Контекстный менеджер для безопасной работы с сессией БД."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Корректно закрывает подключения к БД при завершении работы."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "DB_PATH",
    "resolve_database_url",
    "make_engine",
    "init_engine",
    "get_engine",
    "get_sessionmaker",
    "get_session",
    "dispose_engine",
]
