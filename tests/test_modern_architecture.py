"""Тесты современных архитектурных решений (tests/test_modern_architecture.py).

Проверяет:
1. Typed CallbackData (bot.callbacks): корректная сериализация и распаковка в aiogram 3.31
2. Настройки Settings (bot.config): валидация, разрешение админ-чатов, маскирование
3. Построители клавиатур (InlineKeyboardBuilder в bot.keyboards)
4. ORM-связи SQLAlchemy 2.0 (ServiceCategory <-> ServiceItem, каскадное удаление, __repr__)
5. Асинхронный контекстный менеджер get_session() (bot.db.engine)
6. Гранулярные FSM-состояния (OrderFlow, ManagerService, ManagerDiscount)
"""
from __future__ import annotations

from pathlib import Path
import pytest
from sqlalchemy import select

from bot.callbacks import (
    OrderStatusCallback,
    OrderTierCallback,
    PriceRegionCallback,
    RegionTpQuantityCallback,
    ServiceCategoryDbCallback,
    ServiceItemDbCallback,
)
from bot.config import Settings
from bot.db.engine import dispose_engine, get_session
from bot.db.models import Discount, Order, ServiceCategory, ServiceItem
from bot.db.setup import setup_database
from bot.keyboards.client import (
    cleanup_region_keyboard,
    contact_keyboard,
    order_confirm_keyboard,
    region_tp_quantity_keyboard,
)
from bot.keyboards.manager import (
    admin_keyboard,
    manager_keyboard,
    manager_services_menu_keyboard,
)
from bot.states import ManagerBanner, ManagerDiscount, ManagerService, OrderFlow


@pytest.fixture(autouse=True)
async def cleanup_db():
    yield
    await dispose_engine()


def test_typed_callback_data_pack_unpack():
    """Проверка работы CallbackData моделей aiogram 3.31."""
    # 1. OrderTierCallback
    tier_cb = OrderTierCallback(region="Мондштат", tier_index=1)
    packed_tier = tier_cb.pack()
    assert packed_tier == "tier:Мондштат:1"
    unpacked_tier = OrderTierCallback.unpack(packed_tier)
    assert unpacked_tier.region == "Мондштат"
    assert unpacked_tier.tier_index == 1

    # 2. RegionTpQuantityCallback
    tp_cb = RegionTpQuantityCallback(order_id="42", quantity=20)
    packed_tp = tp_cb.pack()
    assert packed_tp == "region_tp_qty:42:20"
    unpacked_tp = RegionTpQuantityCallback.unpack(packed_tp)
    assert unpacked_tp.order_id == "42"
    assert unpacked_tp.quantity == 20

    # 3. OrderStatusCallback
    status_cb = OrderStatusCallback(order_id="101", status="working")
    packed_status = status_cb.pack()
    assert packed_status == "order_status:101:working"
    unpacked_status = OrderStatusCallback.unpack(packed_status)
    assert unpacked_status.order_id == "101"
    assert unpacked_status.status == "working"

    # 4. Price & Service CallbackData
    cat_cb = ServiceCategoryDbCallback(category_id=5)
    assert cat_cb.pack() == "service_category_db:5"

    item_cb = ServiceItemDbCallback(item_id=12)
    assert item_cb.pack() == "service_item_db:12"


def test_settings_dataclass():
    """Проверка типизированного класса Settings."""
    cfg = Settings(
        admin_chat_id=111,
        admin_chat_ids=(222, 333),
    )
    resolved = cfg.resolved_admin_chat_ids()
    assert resolved == [111, 222, 333]
    assert "devarapq" in cfg.manager_usernames


def test_keyboard_builders():
    """Проверка генерации клавиатур через InlineKeyboardBuilder."""
    # Главная панель менеджера
    mgr_kb = manager_keyboard()
    assert len(mgr_kb.inline_keyboard) >= 5

    # Меню услуг
    services_kb = manager_services_menu_keyboard()
    assert len(services_kb.inline_keyboard) >= 5

    # Кнопки статуса заказа
    admin_kb = admin_keyboard(order_id=99, status="new")
    assert admin_kb is not None
    assert len(admin_kb.inline_keyboard) == 2
    assert admin_kb.inline_keyboard[0][0].callback_data == "order_status:99:working"

    # Клавиатура ТП
    tp_kb = region_tp_quantity_keyboard(order_id=55)
    assert len(tp_kb.inline_keyboard) == 2  # 6 кнопок с adjust(3) -> 2 ряда
    assert tp_kb.inline_keyboard[0][0].callback_data == "region_tp_qty:55:1"


async def test_orm_relationships_and_cascade(tmp_path: Path):
    """Проверка связей (relationship), каскадного удаления и repr в SQLAlchemy 2.0."""
    db_file = tmp_path / "orm_test.db"
    sessionmaker = await setup_database(db_file)

    async with get_session() as session:
        # 1. Создание категории с дочерними элементами через relationship
        category = ServiceCategory(name="Тестовый набор")
        item1 = ServiceItem(name="Вариант А", price=100.0, category=category)
        item2 = ServiceItem(name="Вариант Б", price=200.0, category=category)
        session.add_all([category, item1, item2])
        await session.commit()
        await session.refresh(category)

        # Проверка отношения
        assert len(category.items) == 2
        assert item1.category_name == "Тестовый набор"
        assert item2.category_name == "Тестовый набор"

        # Проверка __repr__
        assert "Тестовый набор" in repr(category)
        assert "Вариант А" in repr(item1)

        # 2. Проверка каскадного удаления
        await session.delete(category)
        await session.commit()

        # Проверяем, что связанные items удалились каскадно
        res = await session.execute(select(ServiceItem).where(ServiceItem.name.in_(["Вариант А", "Вариант Б"])))
        remaining_items = res.scalars().all()
        assert len(remaining_items) == 0


def test_fsm_states_definitions():
    """Проверка гранулярных состояний FSM."""
    assert OrderFlow.quantity.state == "OrderFlow:quantity"
    assert OrderFlow.login.state == "OrderFlow:login"
    assert OrderFlow.password.state == "OrderFlow:password"
    assert OrderFlow.telegram_username.state == "OrderFlow:telegram_username"
    assert OrderFlow.confirm.state == "OrderFlow:confirm"

    assert ManagerService.name.state == "ManagerService:name"
    assert ManagerService.price.state == "ManagerService:price"

    assert ManagerDiscount.threshold.state == "ManagerDiscount:threshold"
    assert ManagerBanner.waiting_photo.state == "ManagerBanner:waiting_photo"


def test_premium_emojis_formatting():
    """Проверка работы тематических Telegram Premium кастомных эмодзи."""
    from bot.emojis import Emojis, emoji

    # 1. Форматирование Markdown и HTML
    fischl = Emojis.FISCHL
    assert fischl.fallback == "⚡"
    assert fischl.as_markdown(use_custom=True) == f"[⚡](tg://emoji?id={fischl.custom_id})"
    assert fischl.as_markdown(use_custom=False) == "⚡"
    assert fischl.as_html(use_custom=True) == f'<tg-emoji emoji-id="{fischl.custom_id}">⚡</tg-emoji>'

    # 2. Проверка ключевых игровых эмодзи
    assert Emojis.PRIMO.fallback == "💫"
    assert Emojis.MORA.fallback == "💰"
    assert Emojis.CART.fallback == "🛒"
    assert Emojis.CROWN.fallback == "👑"
    assert Emojis.BANNER.fallback == "🖼"
    assert Emojis.BACKUP.fallback == "💾"

    # 3. Хелпер emoji()
    rendered = emoji(Emojis.PRIMO)
    assert "💫" in rendered

    # 4. Проверка активного эмодзи-пака news_genshins
    from bot.emojis import EMOJI_PACK_NAME, EMOJI_PACK_URL, EMOJI_PACK_TG_URI
    assert EMOJI_PACK_NAME == "news_genshins"
    assert EMOJI_PACK_URL == "https://t.me/addemoji/news_genshins"
    assert EMOJI_PACK_TG_URI == "tg://addemoji?set=news_genshins"
    assert Emojis.PACK_NAME == "news_genshins"
    assert Emojis.PACK_URL == "https://t.me/addemoji/news_genshins"


async def test_banners_crud_and_repo(tmp_path: Path):
    """Проверка репозитория баннеров (bot.db.repo.banners)."""
    from bot.db.repo.banners import (
        BANNER_SECTIONS,
        delete_banner,
        get_all_banners,
        get_banner,
        set_banner,
    )

    db_file = tmp_path / "banners_test.db"
    sessionmaker = await setup_database(db_file)

    async with sessionmaker() as session:
        # Изначально баннеров нет
        b = await get_banner(session, "main_menu")
        assert b is None

        # Установка баннера
        saved = await set_banner(session, "main_menu", "AgACAgIAAxkBAAI...")
        assert saved.key == "main_menu"
        assert saved.file_id == "AgACAgIAAxkBAAI..."

        # Чтение
        loaded = await get_banner(session, "main_menu")
        assert loaded is not None
        assert loaded.file_id == "AgACAgIAAxkBAAI..."

        # Обновление
        updated = await set_banner(session, "main_menu", "AgACAgIAAxkBAAI_NEW...")
        assert updated.file_id == "AgACAgIAAxkBAAI_NEW..."

        # Получение всех баннеров
        await set_banner(session, "prices", "AgAC_PRICES...")
        all_b = await get_all_banners(session)
        assert len(all_b) == 2
        assert "main_menu" in all_b
        assert "prices" in all_b

        # Удаление
        deleted = await delete_banner(session, "main_menu")
        assert deleted is True
        assert await get_banner(session, "main_menu") is None


async def test_ui_send_or_edit_screen(tmp_path: Path):
    """Проверка сервиса ui.send_or_edit_screen при наличии и отсутствии баннера."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.types import Chat, Message, User, CallbackQuery
    from bot.db.repo.banners import set_banner
    from bot.services.ui import send_or_edit_screen

    db_file = tmp_path / "ui_test.db"
    sessionmaker = await setup_database(db_file)

    async with sessionmaker() as session:
        user = User(id=777, is_bot=False, first_name="Тест")
        chat = Chat(id=777, type="private")

        # 1. Без баннера — отправка текстового сообщения
        msg = MagicMock(spec=Message)
        msg.from_user = user
        msg.chat = chat
        msg.answer = AsyncMock()

        await send_or_edit_screen(msg, session, "main_menu", "Привет без баннера")
        msg.answer.assert_awaited_once_with("Привет без баннера", reply_markup=None)

        # 2. Устанавливаем баннер для main_menu
        await set_banner(session, "main_menu", "PHOTO_FILE_ID_123")

        # 3. С баннером — вызов answer_photo
        msg_with_banner = MagicMock(spec=Message)
        msg_with_banner.from_user = user
        msg_with_banner.chat = chat
        msg_with_banner.answer_photo = AsyncMock()

        await send_or_edit_screen(msg_with_banner, session, "main_menu", "Привет с баннером")
        msg_with_banner.answer_photo.assert_awaited_once_with(
            "PHOTO_FILE_ID_123", caption="Привет с баннером", reply_markup=None
        )


async def test_manager_banner_handlers(tmp_path: Path):
    """Проверка менеджерских хендлеров управления баннерами."""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.types import CallbackQuery, Chat, Message, PhotoSize, User
    from bot.handlers.manager.banners import (
        process_banner_delete,
        process_banner_photo,
        request_banner_photo,
        show_banners_menu,
    )

    db_file = tmp_path / "mgr_banners.db"
    sessionmaker = await setup_database(db_file)

    async with sessionmaker() as session:
        user = User(id=888, is_bot=False, first_name="Менеджер", username="devarapq")
        chat = Chat(id=888, type="private")
        bot = MagicMock()
        storage = MemoryStorage()
        state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=888, user_id=888))

        # 1. Меню баннеров
        parent_msg = MagicMock(spec=Message)
        parent_msg.photo = None
        parent_msg.edit_text = AsyncMock()
        cb = MagicMock(spec=CallbackQuery)
        cb.data = "mgr_banners"
        cb.from_user = user
        cb.message = parent_msg
        cb.answer = AsyncMock()

        await show_banners_menu(cb, session, state)
        parent_msg.edit_text.assert_awaited_once()
        assert "Управление баннерами" in parent_msg.edit_text.await_args[0][0]

        # 2. Запрос фото для раздела main_menu
        cb_req = MagicMock(spec=CallbackQuery)
        cb_req.data = "mgr_banner_upload:main_menu"
        cb_req.from_user = user
        cb_req.message = parent_msg
        cb_req.answer = AsyncMock()

        await request_banner_photo(cb_req, state)
        assert await state.get_state() == ManagerBanner.waiting_photo.state
        data = await state.get_data()
        assert data["banner_key"] == "main_menu"

        # 3. Отправка фото менеджером
        msg_photo = MagicMock(spec=Message)
        msg_photo.from_user = user
        msg_photo.chat = chat
        photo = PhotoSize(file_id="NEW_BANNER_PHOTO_1", file_unique_id="u1", width=800, height=600)
        msg_photo.photo = [photo]
        msg_photo.answer = AsyncMock()

        await process_banner_photo(msg_photo, state, session)
        msg_photo.answer.assert_awaited_once()
        assert "успешно установлен" in msg_photo.answer.await_args[0][0]
        assert await state.get_state() is None

        # 4. Удаление баннера
        cb_del = MagicMock(spec=CallbackQuery)
        cb_del.data = "mgr_banner_delete:main_menu"
        cb_del.from_user = user
        cb_del.message = parent_msg
        cb_del.answer = AsyncMock()

        await process_banner_delete(cb_del, session, state)
        cb_del.answer.assert_awaited_once_with("Баннер удалён", show_alert=True)

