"""Тесты клиентских хендлеров Fishl Shop (tests/test_client_handlers.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User

from bot.config import MANAGER_USERNAMES, SHOP_NAME
from bot.db.engine import dispose_engine
from bot.db.repo import discounts as discounts_repo
from bot.db.repo import orders as orders_repo
from bot.db.repo import services as services_repo
from bot.db.setup import setup_database
from bot.handlers.client.my_orders import my_orders_callback, my_orders_command, show_my_orders
from bot.handlers.client.order import (
    cancel_order_callback,
    cleanup_menu_callback,
    cleanup_regions_callback,
    confirm_order_callback,
    process_order_text_input,
    rank57_item_select_callback,
    select_region_callback,
    select_tier_callback,
    service_57_menu_callback,
    service_category_db_callback,
    service_item_custom_callback,
    service_item_db_callback,
)
from bot.handlers.client.prices import (
    price_57_callback,
    price_category_db_callback,
    price_category_legacy_callback,
    price_cleanup_callback,
    price_region_details_callback,
    prices_menu_callback,
    rank57_price_category_callback,
)
from bot.handlers.client.start import (
    back_callback,
    chat_id_command,
    contact_callback,
    help_command,
    menu_command,
    start_command,
)
from bot.states import OrderFlow


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await dispose_engine()


@pytest.fixture
async def db_session(tmp_path: Path):
    db_file = tmp_path / "orders.db"
    sessionmaker = await setup_database(db_file)
    async with sessionmaker() as session:
        yield session


def make_user(username: str = "customer", user_id: int = 1001) -> User:
    return User(id=user_id, is_bot=False, first_name="Тестер", username=username)


def make_message(text: str, user: User, bot: MagicMock) -> Message:
    chat = Chat(id=user.id, type="private")
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.from_user = user
    msg.chat = chat
    msg.bot = bot
    msg.answer = AsyncMock()
    return msg


def make_callback(data: str, user: User, bot: MagicMock) -> CallbackQuery:
    chat = Chat(id=user.id, type="private")
    parent_msg = MagicMock(spec=Message)
    parent_msg.chat = chat
    parent_msg.message_id = 42
    parent_msg.edit_text = AsyncMock()
    parent_msg.answer = AsyncMock()

    cb = MagicMock(spec=CallbackQuery)
    cb.data = data
    cb.from_user = user
    cb.message = parent_msg
    cb.bot = bot
    cb.answer = AsyncMock()
    return cb


def make_fsm_context(bot: MagicMock, user: User) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=user.id, user_id=user.id)
    return FSMContext(storage=storage, key=key)


# =========================================================================
# Тесты start.py
# =========================================================================

async def test_start_and_menu_commands():
    bot = MagicMock()
    user = make_user()
    state = make_fsm_context(bot, user)
    await state.set_state(OrderFlow.waiting_input)

    msg = make_message("/start", user, bot)
    await start_command(msg, state)
    msg.answer.assert_awaited_once()
    assert SHOP_NAME in msg.answer.await_args[0][0]
    assert await state.get_state() is None

    msg_menu = make_message("/menu", user, bot)
    await menu_command(msg_menu, state)
    msg_menu.answer.assert_awaited_once()
    assert SHOP_NAME in msg_menu.answer.await_args[0][0]


async def test_help_command_client_and_manager():
    bot = MagicMock()
    client = make_user("client_test", 1001)
    msg_client = make_message("/help", client, bot)
    await help_command(msg_client)
    assert "Помощь Fishl Shop" in msg_client.answer.await_args[0][0]

    mgr_username = next(iter(MANAGER_USERNAMES)) if MANAGER_USERNAMES else "admin"
    manager = make_user(mgr_username, 9001)
    msg_mgr = make_message("/help", manager, bot)
    await help_command(msg_mgr)
    assert "Помощь для менеджера" in msg_mgr.answer.await_args[0][0]


async def test_chat_id_command():
    bot = MagicMock()
    user = make_user()
    msg = make_message("/chatid", user, bot)
    await chat_id_command(msg)
    msg.answer.assert_awaited_once()
    assert str(user.id) in msg.answer.await_args[0][0]


async def test_back_callback_client_and_contact():
    bot = MagicMock()
    user = make_user("regular_client", 1001)
    state = make_fsm_context(bot, user)
    await state.set_state(OrderFlow.waiting_input)

    cb = make_callback("back", user, bot)
    await back_callback(cb, state)
    cb.answer.assert_awaited_once()
    cb.message.edit_text.assert_awaited_once()
    assert SHOP_NAME in cb.message.edit_text.await_args[0][0]
    assert await state.get_state() is None

    cb_contact = make_callback("contact", user, bot)
    await contact_callback(cb_contact)
    cb_contact.answer.assert_awaited_once()
    assert "@fishlme" in cb_contact.message.edit_text.await_args[0][0]


# =========================================================================
# Тесты prices.py
# =========================================================================

async def test_prices_navigation(db_session):
    bot = MagicMock()
    user = make_user()

    # Главное меню прайсов
    cb_prices = make_callback("prices", user, bot)
    await prices_menu_callback(cb_prices, db_session)
    assert "Прайсы" in cb_prices.message.edit_text.await_args[0][0]

    # Прайс зачистки
    cb_cleanup = make_callback("price_cleanup", user, bot)
    await price_cleanup_callback(cb_cleanup)
    assert "Прайс зачистки по регионам" in cb_cleanup.message.edit_text.await_args[0][0]

    # Детали региона
    cb_region = make_callback("price_region:Ли Юэ", user, bot)
    await price_region_details_callback(cb_region, db_session)
    assert "Ли Юэ" in cb_region.message.edit_text.await_args[0][0]

    # Прайс 57+
    cb_57 = make_callback("price_57", user, bot)
    await price_57_callback(cb_57)
    assert "Для 57+ рангов" in cb_57.message.edit_text.await_args[0][0]

    # Раздел 57+
    cb_rank = make_callback("rank57_price_category:0", user, bot)
    await rank57_price_category_callback(cb_rank, db_session)
    assert "Крутки" in cb_rank.message.edit_text.await_args[0][0]

    # Статический прайс EXTRA_PRICES
    cb_legacy = make_callback("price_category:0", user, bot)
    await price_category_legacy_callback(cb_legacy)
    assert "Крутки" in cb_legacy.message.edit_text.await_args[0][0]

    # Динамическая услуга из БД
    cat = await services_repo.create_service_category(db_session, "Кастомная услуга")
    await services_repo.create_service_item(db_session, cat.id, "Вариант 1", 500)
    cb_db = make_callback(f"price_category_db:{cat.id}", user, bot)
    await price_category_db_callback(cb_db, db_session)
    assert "Кастомная услуга" in cb_db.message.edit_text.await_args[0][0]


# =========================================================================
# Тесты my_orders.py
# =========================================================================

async def test_my_orders_empty_and_with_orders(db_session):
    bot = MagicMock()
    user = make_user("client_orders", 2002)

    # Пустой список
    msg = make_message("/myorders", user, bot)
    await my_orders_command(msg, db_session)
    assert "нет оформленных заказов" in msg.answer.await_args[0][0]

    # Создаём заказ
    await orders_repo.create_order(
        db_session,
        client_telegram_id=user.id,
        client_name="Клиент",
        price=1000,
        region="Инадзума",
        tier="0-100%",
        service="Зачистка по регионам",
    )

    cb = make_callback("my_orders", user, bot)
    await my_orders_callback(cb, db_session)
    cb.message.edit_text.assert_awaited_once()
    assert "Заказ №" in cb.message.edit_text.await_args[0][0]
    assert "Инадзума" in cb.message.edit_text.await_args[0][0]


# =========================================================================
# Тесты order.py (выбор услуги, FSM ввод, confirm/cancel)
# =========================================================================

async def test_order_flow_full_cycle(db_session):
    bot = MagicMock()
    bot.send_message = AsyncMock()
    user = make_user("buyer", 3003)
    state = make_fsm_context(bot, user)

    # 1. Меню услуг
    cb_clean = make_callback("cleanup", user, bot)
    await cleanup_menu_callback(cb_clean, state, db_session)
    assert "Заказать услугу" in cb_clean.message.edit_text.await_args[0][0]

    # 2. Выбор зачистки регионов
    cb_clean_reg = make_callback("cleanup_regions", user, bot)
    await cleanup_regions_callback(cb_clean_reg, state)
    assert "Зачистка по регионам" in cb_clean_reg.message.edit_text.await_args[0][0]

    # 3. Выбор региона
    cb_reg = make_callback("region:Мондштат", user, bot)
    await select_region_callback(cb_reg, state, db_session)
    assert "Мондштат" in cb_reg.message.edit_text.await_args[0][0]

    # 4. Выбор яруса (tier)
    cb_tier = make_callback("tier:Мондштат:0", user, bot)
    await select_tier_callback(cb_tier, state, db_session)
    assert await state.get_state() == OrderFlow.waiting_input.state
    data = await state.get_data()
    assert data["step"] == "login"
    assert data["region"] == "Мондштат"

    # 5. Ввод некорректного email
    msg_bad_email = make_message("not-an-email", user, bot)
    await process_order_text_input(msg_bad_email, state, db_session)
    assert "не похоже на корректный адрес" in msg_bad_email.answer.await_args[0][0]

    # 6. Ввод корректного email
    msg_email = make_message("client@example.com", user, bot)
    await process_order_text_input(msg_email, state, db_session)
    assert "Шаг 2 из 3" in msg_email.answer.await_args[0][0]
    data = await state.get_data()
    assert data["step"] == "password"
    assert data["login"] == "client@example.com"

    # 7. Ввод пароля
    msg_pass = make_message("SecretPass123", user, bot)
    await process_order_text_input(msg_pass, state, db_session)
    assert "Шаг 3 из 3" in msg_pass.answer.await_args[0][0]
    data = await state.get_data()
    assert data["step"] == "telegram_username"
    assert data["password"] == "SecretPass123"

    # 8. Ввод неверного tg username
    msg_bad_tg = make_message("@@@", user, bot)
    await process_order_text_input(msg_bad_tg, state, db_session)
    assert "Некорректный Telegram-юзернейм" in msg_bad_tg.answer.await_args[0][0]

    # 9. Ввод корректного tg username -> проверка заказа (confirm)
    msg_tg = make_message("@buyer_username", user, bot)
    await process_order_text_input(msg_tg, state, db_session)
    assert "Проверь заказ" in msg_tg.answer.await_args[0][0]
    assert await state.get_state() == OrderFlow.confirm.state
    data = await state.get_data()
    assert data["telegram_username"] == "@buyer_username"

    # 10. Подтверждение заказа
    cb_confirm = make_callback("confirm_order", user, bot)
    with patch("bot.handlers.client.order.ADMIN_CHAT_IDS", [99999]):
        await confirm_order_callback(cb_confirm, state, db_session)

    assert "Заказ оформлен" in cb_confirm.message.edit_text.await_args[0][0]
    assert await state.get_state() is None

    # Проверяем, что заказ создался в БД
    orders = await orders_repo.get_client_orders(db_session, user.id)
    assert len(orders) == 1
    assert orders[0].region == "Мондштат"
    assert orders[0].price == 1000


async def test_order_custom_quantity_and_cancel(db_session):
    bot = MagicMock()
    user = make_user("buyer2", 4004)
    state = make_fsm_context(bot, user)

    # Создаём услугу со свободным количеством в БД
    cat = await services_repo.create_service_category(db_session, "Кастомные крутки")
    item = await services_repo.create_service_item(
        db_session,
        cat.id,
        "Крутка",
        price=25.0,
        quantity_mode="quantity",
        unit="крутка",
    )

    cb_item = make_callback(f"service_item_custom:{item.id}", user, bot)
    await service_item_custom_callback(cb_item, state, db_session)
    assert "Введи нужное количество" in cb_item.message.edit_text.await_args[0][0]
    data = await state.get_data()
    assert data["step"] == "quantity"

    # Некорректное количество
    msg_bad_q = make_message("abc", user, bot)
    await process_order_text_input(msg_bad_q, state, db_session)
    assert "целое положительное количество" in msg_bad_q.answer.await_args[0][0]

    # Корректное количество
    msg_q = make_message("10", user, bot)
    await process_order_text_input(msg_q, state, db_session)
    assert "Количество: *10*" in msg_q.answer.await_args[0][0]
    data = await state.get_data()
    assert data["price"] == 250.0
    assert data["step"] == "login"

    # Отмена заказа
    cb_cancel = make_callback("cancel_order", user, bot)
    await cancel_order_callback(cb_cancel, state)
    cb_cancel.answer.assert_awaited_once_with("Заказ отменён")
    assert "Заказ отменён" in cb_cancel.message.edit_text.await_args[0][0]
    assert await state.get_state() is None
