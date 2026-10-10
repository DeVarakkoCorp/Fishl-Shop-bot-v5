"""Инициализация базы данных и запуск миграций (bot.db.setup).

Выполняет:
1. ensure_persistent_databases() (копирование seed-БД в persistent storage)
2. init_engine() (создание async engine + WAL)
3. alembic upgrade head программно (идемпотентная baseline-миграция)
4. seed_dynamic_services() (заполнение категорий, услуг, цен и фикс плейсхолдера)
5. import_archived_orders() (импорт архивов orders*.db с дедупликацией по fingerprint)
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.engine import BASE_DIR, DB_PATH, init_engine
from bot.db.importer import ensure_persistent_databases, import_archived_orders
from bot.db.seed import seed_dynamic_services

logger = logging.getLogger(__name__)


def run_alembic_upgrade(db_path: Path | str | None = None) -> None:
    """Синхронно запускает alembic upgrade head."""
    ini_path = BASE_DIR / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))

    if db_path is not None:
        p = Path(db_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{p.as_posix()}")

    logger.info("Запуск миграций Alembic...")
    command.upgrade(cfg, "head")
    logger.info("Миграции Alembic успешно применены.")


async def setup_database(
    db_path: Path | str | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Полная процедура начальной настройки БД при старте приложения."""
    target_path = Path(db_path) if db_path else DB_PATH
    logger.info("Настройка базы данных: %s", target_path)

    # 1. Обеспечиваем persistent storage и копируем seed-БД
    ensure_persistent_databases(data_dir=target_path.parent)

    # 2. Инициализируем async engine и фабрику сессий
    session_maker = init_engine(target_path)

    # 3. Применяем миграции Alembic программно в отдельном потоке
    await asyncio.to_thread(run_alembic_upgrade, target_path)

    # 4. Заполняем динамические услуги и цены
    async with session_maker() as session:
        await seed_dynamic_services(session)

    # 5. Импортируем архивные базы данных
    await import_archived_orders(data_dir=target_path.parent, main_db_path=target_path)

    logger.info("База данных готова к работе.")
    return session_maker
