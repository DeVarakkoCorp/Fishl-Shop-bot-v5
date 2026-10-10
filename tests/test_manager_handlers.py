"""Тесты менеджерских хендлеров (tests/test_manager_handlers.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Chat, Message, User

from bot.config import MANAGER_USERNAMES
from bot.db.engine import dispose_engine
from bot.db.repo import discounts as discounts_repo
from bot.db.repo import orders as orders_repo
from bot.db.repo import services as services_repo
from bot.db.setup import setup_database
from bot.handlers.manager import fallback_router, router, show_manager_panel
from bot.handlers.manager.orders import apply_order_discount_choice, order_status_callback
from bot.states import ManagerDiscount, ManagerService


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await dispose_engine()


def make_user(username: str, user_id: int = 1001) -> User:
    return User(id=user_id, is_bot=False, first_name="Tester", username=username)


def make_message(text: str, user: User, bot: MagicMock) -> Message:
    chat = Chat(id=user.id, type="private")
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.from_user = user
    msg.chat = chat
    msg.bot = bot
    msg.answer = AsyncMock()
    msg.reply_text = AsyncMock()
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


async def test_show_manager_panel_unauthorized():
    bot = MagicMock()
    non_manager = make_user("stranger", 9999)
    msg = make_message("/manager", non_manager, bot)
    await show_manager_panel(msg, edit=False)
    msg.answer.assert_awaited_once_with("❌ Доступ запрещён.")

    cb = make_callback("mgr_panel", non_manager, bot)
    await show_manager_panel(cb, edit=True)
    cb.answer.assert_awaited_once_with("Недоступно", show_alert=True)


async def test_show_manager_panel_authorized():
    bot = MagicMock()
    manager_username = next(iter(MANAGER_USERNAMES)) if MANAGER_USERNAMES else "admin"
    manager = make_user(manager_username, 1111)

    msg = make_message("/manager", manager, bot)
    await show_manager_panel(msg, edit=False)
    msg.answer.assert_awaited_once()
    assert "Панель менеджера" in msg.answer.await_args[0][0]

    cb = make_callback("mgr_panel", manager, bot)
    await show_manager_panel(cb, edit=True)
    cb.message.edit_text.assert_awaited_once()
    assert "Панель менеджера" in cb.message.edit_text.await_args[0][0]


async def test_fallback_unauthorized_alert():
    bot = MagicMock()
    non_manager = make_user("stranger", 9999)
    cb = make_callback("mgr_services", non_manager, bot)
    # Вызываем хендлер fallback роутера напрямую
    handler = fallback_router.callback_query.handlers[0].callback
    await handler(cb)
    cb.answer.assert_awaited_once_with("Недоступно", show_alert=True)


async def test_order_status_workflow(tmp_path: Path):
    db_file = tmp_path / "test_orders_mgr.db"
    sessionmaker = await setup_database(db_file)
    bot = MagicMock()
    bot.send_message = AsyncMock()

    manager_username = next(iter(MANAGER_USERNAMES)) if MANAGER_USERNAMES else "admin"
    manager = make_user(manager_username, 1111)

    async with sessionmaker() as session:
        order = await orders_repo.create_order(
            session,
            client_telegram_id=55555,
            client_name="Client1",
            price=1000,
            status="new",
        )
        order_id = order.id

        cb = make_callback(f"order_status:{order_id}:working", manager, bot)
        await order_status_callback(cb, session)

        updated = await orders_repo.get_order_by_id(session, order_id)
        assert updated.status == "working"
        assert updated.manager_name == f"@{manager_username}"
        cb.message.edit_text.assert_awaited_once()
        bot.send_message.assert_awaited_once()
        assert "взят в работу" in bot.send_message.await_args.kwargs["text"]


async def test_apply_order_discount_choice(tmp_path: Path):
    db_file = tmp_path / "test_discounts_order.db"
    sessionmaker = await setup_database(db_file)
    bot = MagicMock()
    bot.workflow_data = {}

    manager_username = next(iter(MANAGER_USERNAMES)) if MANAGER_USERNAMES else "admin"
    manager = make_user(manager_username, 1111)

    async with sessionmaker() as session:
        await discounts_repo.create_discount(
            session,
            kind="threshold",
            percent=10,
            threshold=500,
            value_type="%",
        )
        order = await orders_repo.create_order(
            session,
            client_telegram_id=55555,
            client_name="Client1",
            price=1000,
            original_price=1000,
            status="new",
        )
        order_id = order.id

        cb = make_callback(f"discount_sum:{order_id}", manager, bot)
        await apply_order_discount_choice(cb, session)

        updated = await orders_repo.get_order_by_id(session, order_id)
        assert updated.price == 900
        assert updated.discount_amount == 100
        assert updated.discount_mode == "summed"
