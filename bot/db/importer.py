"""Импорт архивных баз данных orders*.db и перенос seed-баз в persistent storage.

Соответствует legacy bot_ptb.py (строки 38-50, 755-815):
- ensure_persistent_databases (копирование seed-БД из BASE_DIR в DATA_DIR)
- import_archived_orders (одноразовый идемпотентный импорт архивов в основную БД с дедупом по fingerprint)
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import shutil
import sqlite3

from bot.db.engine import BASE_DIR, DATA_DIR, DB_PATH

logger = logging.getLogger(__name__)


def ensure_persistent_databases(
    base_dir: Path | str | None = None,
    data_dir: Path | str | None = None,
) -> None:
    """Создаёт каталог данных и один раз переносит DB из репозитория в persistent storage."""
    b_dir = Path(base_dir) if base_dir else BASE_DIR
    d_dir = Path(data_dir) if data_dir else DATA_DIR
    d_dir.mkdir(parents=True, exist_ok=True)

    if b_dir.resolve() == d_dir.resolve():
        return

    for seed in sorted(b_dir.glob("orders*.db")):
        destination = d_dir / seed.name
        if destination.exists():
            continue
        try:
            shutil.copy2(seed, destination)
            logger.info("Скопирована исходная БД в persistent storage: %s", destination)
        except OSError:
            logger.exception("Не удалось скопировать %s в %s", seed, destination)


def _sync_import_archived_orders(
    data_dir: Path | str | None = None,
    main_db_path: Path | str | None = None,
) -> int:
    """Синхронная функция импорта архивных orders*.db в основную базу."""
    m_path = Path(main_db_path) if main_db_path else DB_PATH
    d_dir = Path(data_dir) if data_dir else (m_path.parent if main_db_path else DATA_DIR)

    if not m_path.exists():
        logger.warning("Основная БД %s не существует, импорт архивов пропущен.", m_path)
        return 0

    m_path_resolved = m_path.resolve()
    # Ищем все orders*.db кроме основного файла и файлов *.imported
    archive_paths = [
        p
        for p in sorted(d_dir.glob("orders*.db"))
        if p.resolve() != m_path_resolved and not p.name.endswith(".imported")
    ]
    if not archive_paths:
        return 0

    main_conn = sqlite3.connect(m_path)
    main_conn.row_factory = sqlite3.Row

    # Проверяем наличие таблицы orders в основной БД
    cur = main_conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'")
    if not cur.fetchone():
        main_conn.close()
        logger.warning("Таблица orders отсутствует в %s, импорт отложен.", m_path)
        return 0

    # Собираем существующие фингерпринты из основной БД
    cur = main_conn.execute("SELECT * FROM orders")
    existing_fingerprints = set()
    for row in cur.fetchall():
        d = dict(row)
        fp = (
            d.get("client_telegram_id"),
            str(d.get("created_at") or ""),
            str(d.get("client_name") or ""),
            int(d.get("price") or 0),
            str(d.get("service") or ""),
            str(d.get("details") or ""),
            str(d.get("region") or ""),
            str(d.get("tier") or ""),
            str(d.get("uid") or ""),
            str(d.get("server") or ""),
        )
        existing_fingerprints.add(fp)

    total_imported = 0

    for arch_path in archive_paths:
        try:
            arch_conn = sqlite3.connect(arch_path)
            arch_conn.row_factory = sqlite3.Row
            table_check = arch_conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
            if not table_check:
                arch_conn.close()
                _rename_to_imported(arch_path)
                continue

            rows = arch_conn.execute("SELECT * FROM orders").fetchall()
            arch_conn.close()

            for row in rows:
                d = dict(row)
                price_val = int(round(float(d.get("price") or 0)))
                service_val = str(d.get("service") or "")
                details_val = str(d.get("details") or "")
                region_val = str(d.get("region") or "")
                tier_val = str(d.get("tier") or "")
                uid_val = str(d.get("uid") or "")
                server_val = str(d.get("server") or "")
                client_id = int(d.get("client_telegram_id") or 0)
                client_name = str(d.get("client_name") or "")
                created_at = str(d.get("created_at") or "")

                fp = (
                    client_id,
                    created_at,
                    client_name,
                    price_val,
                    service_val,
                    details_val,
                    region_val,
                    tier_val,
                    uid_val,
                    server_val,
                )

                if fp in existing_fingerprints:
                    continue

                original_price = float(d["original_price"]) if d.get("original_price") is not None else None
                discount_amount = float(d.get("discount_amount") or 0.0)
                discount_mode = str(d.get("discount_mode") or "")
                status_val = str(d.get("status") or "new")
                manager_val = str(d.get("manager_name") or "")

                main_conn.execute(
                    """
                    INSERT INTO orders (
                        created_at, client_telegram_id, client_name, uid, server,
                        region, tier, price, status, manager_name, service, details,
                        original_price, discount_amount, discount_mode
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        created_at,
                        client_id,
                        client_name,
                        uid_val,
                        server_val,
                        region_val,
                        tier_val,
                        price_val,
                        status_val,
                        manager_val,
                        service_val,
                        details_val,
                        original_price,
                        discount_amount,
                        discount_mode,
                    ),
                )
                existing_fingerprints.add(fp)
                total_imported += 1

            main_conn.commit()
            _rename_to_imported(arch_path)
        except Exception:
            logger.exception("Ошибка при импорте архивной БД %s", arch_path)

    main_conn.close()
    return total_imported


def _rename_to_imported(path: Path) -> None:
    imported_path = path.with_name(path.name + ".imported")
    try:
        if imported_path.exists():
            imported_path.unlink()
        path.rename(imported_path)
        logger.info("Архив %s переименован в %s", path, imported_path)
    except OSError:
        logger.exception("Не удалось переименовать архив %s в %s", path, imported_path)


async def import_archived_orders(
    data_dir: Path | str | None = None,
    main_db_path: Path | str | None = None,
) -> int:
    """Асинхронная обёртка над импортом архивов в основном потоке через asyncio.to_thread."""
    return await asyncio.to_thread(_sync_import_archived_orders, data_dir, main_db_path)
