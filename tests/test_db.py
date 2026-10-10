"""Тесты базы данных (tests/test_db.py).

Покрывает:
1. PRAGMA journal_mode == 'wal'
2. CRUD заказов (orders repo)
3. Миграция старой БД (схема legacy без новых колонок -> alembic baseline)
4. Импорт архивов с дедупликацией по fingerprint и идемпотентностью
5. FSM storage roundtrip (SqliteStorage)
6. Репозитории services, prices, discounts и seed_dynamic_services
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest
from sqlalchemy import text
from aiogram.fsm.storage.base import StorageKey

from bot.db.engine import dispose_engine, init_engine, make_engine
from bot.db.fsm_storage import SqliteStorage
from bot.db.importer import import_archived_orders
from bot.db.repo import discounts as discounts_repo
from bot.db.repo import orders as orders_repo
from bot.db.repo import prices as prices_repo
from bot.db.repo import services as services_repo
from bot.db.seed import seed_dynamic_services
from bot.db.setup import run_alembic_upgrade, setup_database


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    """Автоматически закрывает глобальный движок после каждого теста."""
    yield
    await dispose_engine()


async def test_wal_mode(tmp_path: Path):
    """Проверка, что PRAGMA journal_mode == 'wal' и pragma активны."""
    db_file = tmp_path / "test_wal.db"
    engine = make_engine(db_file)
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA journal_mode;"))
        mode = result.scalar()
        assert mode is not None
        assert mode.lower() == "wal"
    await engine.dispose()


async def test_crud_orders(tmp_path: Path):
    """CRUD операции с заказами через orders repository."""
    db_file = tmp_path / "orders_crud.db"
    session_maker = await setup_database(db_file)

    async with session_maker() as session:
        # 1. Создание заказа
        order = await orders_repo.create_order(
            session,
            client_telegram_id=123456,
            client_name="Test User",
            price=1500,
            region="Мондштат",
            tier="0-100",
            service="Зачистка по регионам",
            details="Быстрее, пожалуйста",
            original_price=2000.0,
            discount_amount=500.0,
            discount_mode="automatic",
        )
        assert order.id is not None
        order_id = order.id
        assert order.price == 1500
        assert order.status == "new"

        # 2. Получение по ID
        fetched = await orders_repo.get_order_by_id(session, order_id)
        assert fetched is not None
        assert fetched.client_name == "Test User"
        assert fetched.details == "Быстрее, пожалуйста"
        assert fetched.original_price == 2000.0

        # 3. Обновление статуса и менеджера
        updated = await orders_repo.update_order_status(session, order_id, "taken", manager_name="@manager_ivan")
        assert updated is not None
        assert updated.status == "taken"
        assert updated.manager_name == "@manager_ivan"

        # 4. Обновление скидки
        discount_updated = await orders_repo.update_order_discount(
            session,
            order_id,
            price=1400,
            original_price=2000.0,
            discount_amount=600.0,
            discount_mode="summed",
        )
        assert discount_updated is not None
        assert discount_updated.price == 1400
        assert discount_updated.discount_amount == 600.0

        # Создаём второй заказ (завершённый)
        await orders_repo.create_order(
            session,
            client_telegram_id=123456,
            client_name="Test User",
            price=500,
            status="done",
            created_at="2026-10-06 10:00:00",
        )

        # 5. Активные заказы
        active_orders = await orders_repo.get_active_orders(session)
        assert any(o.id == order_id for o in active_orders)
        assert all(o.status in ("new", "taken", "working") for o in active_orders)

        # 6. Заказы клиента (сортировка created_at DESC)
        client_orders = await orders_repo.get_client_orders(session, 123456)
        assert len(client_orders) == 2

        # 7. Заказы менеджера
        all_orders = await orders_repo.get_all_manager_orders(session)
        assert len(all_orders) >= 2

        # Проверка сериализации в словарь
        d = orders_repo.order_to_dict(fetched)
        assert d["id"] == order_id
        assert d["client_telegram_id"] == 123456


async def test_migration_old_db(tmp_path: Path):
    """Миграция существующей БД со старой схемой (без колонок service/details/original_price и т.д.)."""
    old_db_file = tmp_path / "old_orders.db"

    # Создаём старую схему вручную через sqlite3
    conn = sqlite3.connect(old_db_file)
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            client_telegram_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            uid TEXT NOT NULL,
            server TEXT NOT NULL,
            region TEXT NOT NULL,
            tier TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            manager_name TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE discounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            threshold REAL DEFAULT 0,
            service TEXT DEFAULT '',
            percent REAL NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )
    # Вставляем старую запись
    conn.execute(
        """
        INSERT INTO orders (created_at, client_telegram_id, client_name, uid, server, region, tier, price)
        VALUES ('2025-01-01 12:00:00', 999, 'Old Customer', '12345', 'Europe', 'Ли Юэ', '50-100', 1700)
        """
    )
    conn.commit()
    conn.close()

    # Запускаем программную миграцию Alembic
    run_alembic_upgrade(old_db_file)

    # Проверяем структуру через sqlite3
    chk_conn = sqlite3.connect(old_db_file)
    chk_conn.row_factory = sqlite3.Row
    order_cols = {col["name"] for col in chk_conn.execute("PRAGMA table_info(orders)").fetchall()}
    assert "service" in order_cols
    assert "details" in order_cols
    assert "original_price" in order_cols
    assert "discount_amount" in order_cols
    assert "discount_mode" in order_cols

    discount_cols = {col["name"] for col in chk_conn.execute("PRAGMA table_info(discounts)").fetchall()}
    assert "value_type" in discount_cols
    assert "expires_at" in discount_cols

    # Проверяем наличие fsm_state
    fsm_table = chk_conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fsm_state'").fetchone()
    assert fsm_table is not None

    # Проверяем, что старая запись сохранилась
    row = chk_conn.execute("SELECT * FROM orders WHERE client_telegram_id=999").fetchone()
    assert row is not None
    assert row["client_name"] == "Old Customer"
    assert row["service"] == "" or row["service"] is None
    chk_conn.close()

    # Повторный апгрейд не должен падать (идемпотентность)
    run_alembic_upgrade(old_db_file)


async def test_import_dedup_and_idempotency(tmp_path: Path):
    """Импорт архивных БД orders*.db с дедупликацией по fingerprint и идемпотентностью."""
    main_db = tmp_path / "orders.db"
    run_alembic_upgrade(main_db)

    # Добавляем существующий заказ в main_db
    conn = sqlite3.connect(main_db)
    conn.execute(
        """
        INSERT INTO orders (
            created_at, client_telegram_id, client_name, uid, server,
            region, tier, price, status, manager_name, service, details,
            original_price, discount_amount, discount_mode
        ) VALUES (
            '2025-05-01 10:00:00', 111, 'Alice', 'UID1', 'Europe',
            'Мондштат', '0-100', 1000, 'done', 'mgr', 'Зачистка', 'детали1',
            1000.0, 0.0, ''
        )
        """
    )
    conn.commit()
    conn.close()

    # Создаём архивный файл orders_archive1.db
    arch_db = tmp_path / "orders_archive1.db"
    conn_arch = sqlite3.connect(arch_db)
    conn_arch.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            client_telegram_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            uid TEXT NOT NULL,
            server TEXT NOT NULL,
            region TEXT NOT NULL,
            tier TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT DEFAULT 'new',
            manager_name TEXT DEFAULT '',
            service TEXT DEFAULT '',
            details TEXT DEFAULT ''
        )
        """
    )
    # Заказ 1: дубликат Alice
    conn_arch.execute(
        """
        INSERT INTO orders (created_at, client_telegram_id, client_name, uid, server, region, tier, price, service, details)
        VALUES ('2025-05-01 10:00:00', 111, 'Alice', 'UID1', 'Europe', 'Мондштат', '0-100', 1000, 'Зачистка', 'детали1')
        """
    )
    # Заказ 2: новый заказ Bob
    conn_arch.execute(
        """
        INSERT INTO orders (created_at, client_telegram_id, client_name, uid, server, region, tier, price, service, details)
        VALUES ('2025-05-02 12:00:00', 222, 'Bob', 'UID2', 'Europe', 'Ли Юэ', '50-100', 1700, 'Зачистка', 'детали2')
        """
    )
    conn_arch.commit()
    conn_arch.close()

    # Запускаем импорт
    imported_count = await import_archived_orders(data_dir=tmp_path, main_db_path=main_db)
    assert imported_count == 1  # Только заказ Bob должен быть импортирован

    # Проверяем переименование
    assert not arch_db.exists()
    assert (tmp_path / "orders_archive1.db.imported").exists()

    # Проверяем записи в main_db
    conn = sqlite3.connect(main_db)
    rows = conn.execute("SELECT client_name FROM orders ORDER BY id").fetchall()
    names = [r[0] for r in rows]
    assert names == ["Alice", "Bob"]
    conn.close()

    # Повторный вызов импорта (идемпотентность)
    second_run = await import_archived_orders(data_dir=tmp_path, main_db_path=main_db)
    assert second_run == 0


async def test_fsm_storage_roundtrip(tmp_path: Path):
    """Тест FSM хранилища SqliteStorage: set_state, get_state, set_data, get_data, update_data."""
    db_file = tmp_path / "fsm_test.db"
    session_maker = await setup_database(db_file)

    storage = SqliteStorage(session_maker)
    key = StorageKey(
        bot_id=1001,
        chat_id=2002,
        user_id=3003,
        thread_id=None,
        business_connection_id=None,
        destiny="default",
    )

    # Изначально пусто
    assert await storage.get_state(key) is None
    assert await storage.get_data(key) == {}

    # Установка состояния
    await storage.set_state(key, "OrderState:waiting_email")
    assert await storage.get_state(key) == "OrderState:waiting_email"

    # Установка данных
    await storage.set_data(key, {"email": "user@test.com", "region": "Мондштат"})
    data = await storage.get_data(key)
    assert data == {"email": "user@test.com", "region": "Мондштат"}

    # Обновление данных
    updated = await storage.update_data(key, {"password": "secret", "region": "Ли Юэ"})
    assert updated == {"email": "user@test.com", "region": "Ли Юэ", "password": "secret"}
    assert await storage.get_data(key) == updated

    # Сброс состояния без потери данных
    await storage.set_state(key, None)
    assert await storage.get_state(key) is None
    assert await storage.get_data(key) == updated

    await storage.close()


async def test_services_prices_and_discounts_repos(tmp_path: Path):
    """Тест репозиториев services, prices, discounts и seed."""
    db_file = tmp_path / "all_repos.db"
    session_maker = await setup_database(db_file)

    async with session_maker() as session:
        # 1. Services
        categories = await services_repo.get_service_categories(session)
        assert len(categories) > 0
        first_cat = categories[0]
        cat_items = await services_repo.get_service_items(session, first_cat.id)
        assert len(cat_items) > 0

        # Проверка get_service_item с category_name
        first_item = cat_items[0]
        item_with_cat = await services_repo.get_service_item(session, first_item.id)
        assert item_with_cat is not None
        assert hasattr(item_with_cat, "category_name")
        assert item_with_cat.category_name == first_cat.name

        # Обновление цены услуги
        await services_repo.update_service_item_price(session, first_item.id, 99.0)
        reloaded_item = await services_repo.get_service_item(session, first_item.id)
        assert reloaded_item is not None
        assert reloaded_item.price == 99.0

        # Добавление категории и варианта
        new_cat = await services_repo.create_service_category(session, "Тестовая категория")
        new_item = await services_repo.create_service_item(session, new_cat.id, "Тестовый вариант", 500)
        assert new_item.name == "Тестовый вариант"

        # 2. Prices
        mond_prices = await prices_repo.get_region_prices(session, "Мондштат")
        assert "0-100" in mond_prices
        # Обновление цены региона
        await prices_repo.update_region_price(session, "Мондштат", "0-100", 1111)
        updated_mond = await prices_repo.get_region_prices(session, "Мондштат")
        assert updated_mond["0-100"] == 1111.0

        # 3. Discounts
        discount = await discounts_repo.create_discount(
            session,
            kind="threshold",
            threshold=1000,
            percent=10,
            value_type="%",
        )
        assert discount.id is not None
        active_discounts = await discounts_repo.get_active_discounts(session)
        assert any(d.id == discount.id for d in active_discounts)

        # Деактивация
        await discounts_repo.deactivate_discount(session, discount.id)
        active_after = await discounts_repo.get_active_discounts(session)
        assert not any(d.id == discount.id for d in active_after)
