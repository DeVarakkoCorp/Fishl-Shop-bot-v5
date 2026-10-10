"""Клиентские хендлеры оформления заказа (выбор услуг, FSM ввода данных, подтверждение и отмена)."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import ADMIN_CHAT_IDS, MANAGER_USERNAME, SHOP_NAME
from bot.constants import (
    DIKOVINKI_PRICES,
    EMAIL_REGEX,
    OKULY_PRICES,
    RANK57_CATEGORIES,
    TG_USERNAME_REGEX,
    TIER_KEYS,
    TIER_NAMES,
)
from bot.db.repo.discounts import calculate_discount
from bot.db.repo.orders import create_order
from bot.db.repo.prices import get_region_prices
from bot.db.repo.services import (
    get_service_categories,
    get_service_category,
    get_service_item,
    get_service_items,
)
from bot.keyboards.client import (
    order_confirm_keyboard,
    order_placed_keyboard,
    rank57_item_keyboard,
    rank57_keyboard,
    region_keyboard,
    service_category_keyboard,
    service_item_keyboard,
    tier_keyboard,
)
from bot.keyboards.common import main_menu_keyboard
from bot.keyboards.manager import admin_keyboard, manager_discount_choice_keyboard
from bot.prices import PRICE_CATEGORIES, PRICES
from bot.services.notify import (
    format_admin_order,
    format_order_credentials,
    pending_credentials,
    send_to_admin_chats,
)
from bot.services.pricing import (
    format_price,
    get_applicable_discounts,
    get_service_discounted_price,
    price_with_discount_text,
    region_tp_price,
)
from bot.services.texts import (
    format_discount_choice,
    format_order_summary,
    format_rank57_prices,
    rank57_item_data,
    service_category_text,
)
from bot.emojis import Emojis, emoji
from bot.services.ui import send_or_edit_screen
from bot.states import OrderFlow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="client_order")


# =========================================================================
# 1. Выбор категории услуги / зачистки
# =========================================================================

@router.callback_query(F.data == "cleanup")
async def cleanup_menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Старт заказа: сброс FSM и вывод списка категорий услуг."""
    await callback.answer()
    await state.clear()
    kb = await service_category_keyboard(session)
    text = f"{emoji(Emojis.CART)} *Заказать услугу*\n\nВыбери нужную услугу:"
    await send_or_edit_screen(callback, session, "order", text, reply_markup=kb)


@router.callback_query(F.data == "cleanup_regions")
async def cleanup_regions_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор региона для зачистки."""
    await callback.answer()
    await state.clear()
    await state.update_data(service="Зачистка по регионам")
    if callback.message:
        await callback.message.edit_text(
            "🧹 *Зачистка по регионам*\n\nВыбери регион:",
            reply_markup=region_keyboard(),
        )


@router.callback_query(F.data.startswith("region:"))
async def select_region_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Выбор региона: вывод уровней зачистки с ценами со скидкой."""
    await callback.answer()
    if not callback.data:
        return
    region = callback.data.split(":", 1)[1]
    if region not in PRICES:
        if callback.message:
            await callback.message.edit_text(
                "❌ Регион не найден. Нажми /start.",
                reply_markup=main_menu_keyboard(),
            )
        return

    await state.update_data(region=region, service="Зачистка по регионам")
    kb = await tier_keyboard(session, region)
    if callback.message:
        await callback.message.edit_text(
            f"🧹 *{region}*\n\nВыбери объём зачистки:",
            reply_markup=kb,
        )


@router.callback_query(F.data.startswith("tier:"))
async def select_tier_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Выбор уровня зачистки: переход к шагу 1 (email)."""
    await callback.answer()
    if not callback.data:
        return
    parts = callback.data.split(":", 2)
    if len(parts) != 3 or parts[1] not in PRICES or parts[2] not in ("0", "1", "2"):
        if callback.message:
            await callback.message.edit_text(
                "❌ Ошибка выбора. Нажми /start.",
                reply_markup=main_menu_keyboard(),
            )
        return

    region, tier_index = parts[1], int(parts[2])
    prices = await get_region_prices(session, region)
    price = prices[TIER_KEYS[tier_index]]

    await state.clear()
    await state.update_data(
        region=region,
        tier_index=tier_index,
        price=price,
        service="Зачистка по регионам",
        service_item=f"Зачистка {TIER_NAMES[tier_index]}",
        step="login",
    )
    await state.set_state(OrderFlow.waiting_input)

    shown_price = await price_with_discount_text(session, price, "Зачистка по регионам")
    if callback.message:
        await callback.message.edit_text(
            f"🧹 *Зачистка по регионам*\n\n"
            f"Регион: *{region}*\n"
            f"Объём: *{TIER_NAMES[tier_index]}*\n"
            f"💰 Цена: *{shown_price}*\n\n"
            "🔐 *Шаг 1 из 3*\n\n"
            "Отправь почту (email), привязанную к аккаунту.\n\n"
            "⚠️ Отправляй только данные от аккаунта, который используется для заказа."
        )


# =========================================================================
# 2. Услуги для 57+ рангов
# =========================================================================

@router.callback_query(F.data == "service_57")
async def service_57_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню разделов 57+ рангов для оформления заказа."""
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            "🛒 *Для 57+ рангов*\n\nВыбери раздел:",
            reply_markup=rank57_keyboard("service57_category"),
        )


@router.callback_query(F.data.startswith("service57_category:"))
async def service57_category_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Список вариантов услуг внутри выбранного раздела 57+ рангов."""
    await callback.answer()
    if not callback.data:
        return
    try:
        index = int(callback.data.split(":", 1)[1])
        category = RANK57_CATEGORIES[index]
    except (ValueError, IndexError):
        if callback.message:
            kb = await service_category_keyboard(session)
            await callback.message.edit_text("❌ Раздел не найден.", reply_markup=kb)
        return

    price_text = await format_rank57_prices(session, category)
    if callback.message:
        await callback.message.edit_text(
            f"🛒 *{category}*\n\n{price_text}\n\nВыбери вариант для заказа:",
            reply_markup=rank57_item_keyboard(index),
        )


@router.callback_query(F.data.startswith("rank57_item:"))
async def rank57_item_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор конкретного пункта услуги 57+ рангов."""
    await callback.answer()
    if not callback.data:
        return
    try:
        _, category_index_s, item_index_s = callback.data.split(":", 2)
        category_index = int(category_index_s)
        item_index = int(item_index_s)
        item = rank57_item_data(category_index, item_index)
    except (ValueError, IndexError):
        item = None

    if not item:
        if callback.message:
            await callback.message.edit_text("❌ Услуга не найдена.", reply_markup=main_menu_keyboard())
        return

    category, item_name, price = item
    await state.clear()
    await state.update_data(
        service=category,
        service_item=item_name,
        price=price,
        step="login",
    )
    await state.set_state(OrderFlow.waiting_input)

    if callback.message:
        await callback.message.edit_text(
            f"🛒 *Заказ услуги*\n\n*{category}*\n{item_name}\n\n"
            "🔐 *Шаг 1 из 3*\n\n"
            "Отправь почту (email), привязанную к аккаунту.\n\n"
            "⚠️ Отправляй только данные от аккаунта, который используется для заказа."
        )


# =========================================================================
# 3. Динамические услуги из базы данных и legacy-форматы
# =========================================================================

@router.callback_query(F.data.startswith("service_category_db:"))
async def service_category_db_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Вывод вариантов услуги из динамической базы данных."""
    await callback.answer()
    if not callback.data:
        return
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        category_id = 0

    category = await get_service_category(session, category_id)
    if not category or not category.active:
        if callback.message:
            kb = await service_category_keyboard(session)
            await callback.message.edit_text("❌ Услуга не найдена.", reply_markup=kb)
        return

    cat_text = await service_category_text(session, category_id)
    kb = await service_item_keyboard(session, category_id)
    if callback.message:
        await callback.message.edit_text(
            f"🛒 *{category.name}*\n\n{cat_text}\n\nВыбери вариант для заказа:",
            reply_markup=kb,
        )


@router.callback_query(F.data.startswith("service_category:"))
async def service_category_legacy_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Обработка выбора категории по индексу из PRICE_CATEGORIES (legacy-кнопки)."""
    await callback.answer()
    if not callback.data:
        return
    try:
        category_name = PRICE_CATEGORIES[int(callback.data.split(":", 1)[1])]
        categories = await get_service_categories(session, active_only=True)
        category = next((c for c in categories if c.name == category_name), None)
    except (ValueError, IndexError):
        category = None

    if not category:
        if callback.message:
            await callback.message.edit_text("❌ Услуга не найдена.", reply_markup=main_menu_keyboard())
        return

    cat_text = await service_category_text(session, category.id)
    kb = await service_item_keyboard(session, category.id)
    if callback.message:
        await callback.message.edit_text(
            f"🛒 *{category.name}*\n\n{cat_text}\n\nВыбери вариант для заказа:",
            reply_markup=kb,
        )


@router.callback_query(F.data.startswith("service_item_custom:"))
async def service_item_custom_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Запрос свободного количества для услуги (например, крутки)."""
    await callback.answer()
    if not callback.data:
        return
    try:
        item_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        item_id = 0

    item = await get_service_item(session, item_id)
    if not item or not item.active:
        if callback.message:
            kb = await service_category_keyboard(session)
            await callback.message.edit_text("❌ Пункт услуги не найден.", reply_markup=kb)
        return

    await state.clear()
    await state.update_data(
        service=item.category_name,
        service_item=item.name,
        quantity_unit=item.unit,
        unit_price=float(item.price),
        step="quantity",
    )
    await state.set_state(OrderFlow.waiting_input)

    shown_price = await price_with_discount_text(session, item.price, item.category_name)
    if callback.message:
        await callback.message.edit_text(
            f"✏️ *{item.name}*\n\n"
            f"Цена: *{shown_price} за 1 {item.unit}*\n\n"
            "Введи нужное количество:"
        )


@router.callback_query(F.data.startswith("service_item_db:"))
async def service_item_db_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Выбор варианта услуги из базы данных."""
    await callback.answer()
    if not callback.data:
        return
    try:
        item_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        item_id = 0

    item = await get_service_item(session, item_id)
    if not item or not item.active:
        if callback.message:
            kb = await service_category_keyboard(session)
            await callback.message.edit_text("❌ Этот пункт услуги недоступен.", reply_markup=kb)
        return

    if item.quantity_mode == "quantity":
        await state.clear()
        await state.update_data(
            service=item.category_name,
            service_item=item.name,
            quantity_unit=item.unit,
            unit_price=float(item.price),
            step="quantity",
        )
        await state.set_state(OrderFlow.waiting_input)
        shown_price = await price_with_discount_text(session, item.price, item.category_name)
        if callback.message:
            await callback.message.edit_text(
                f"✏️ *{item.name}*\n\n"
                f"Цена: *{shown_price} за 1 {item.unit}*\n\n"
                "Введи нужное количество:"
            )
        return

    await state.clear()
    await state.update_data(
        service=item.category_name,
        service_item=item.name,
        price=float(item.price),
        step="login",
    )
    await state.set_state(OrderFlow.waiting_input)
    shown_price = await price_with_discount_text(session, item.price, item.category_name)
    if callback.message:
        await callback.message.edit_text(
            f"🛒 *Заказ услуги*\n\n"
            f"*{item.category_name}*\n{item.name}\n\n"
            f"💰 Цена: *{shown_price}*\n\n"
            "🔐 *Шаг 1 из 3*\n\n"
            "Отправь почту (email), привязанную к аккаунту."
        )


@router.callback_query(F.data.startswith("custom_quantity:"))
async def custom_quantity_legacy_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Обработка устаревших inline-кнопок custom_quantity (крутки, диковинки, окулы)."""
    await callback.answer()
    if not callback.data:
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    kind, value = parts[1], parts[2]

    if kind == "spins":
        categories = await get_service_categories(session, active_only=True)
        cat = next((c for c in categories if c.name == "Крутки"), None)
        items = await get_service_items(session, cat.id, active_only=True) if cat else []
        unit_price = float(items[0].price) if items else 24.0
        shown_price = await price_with_discount_text(session, unit_price, "Крутки")
        order_dict = {"service": "Крутки", "quantity_unit": "крутка", "unit_price": unit_price}
        prompt = f"✏️ *Крутки*\n\nЦена: *{shown_price} за 1 крутку*.\n\nВведи нужное количество круток:"
    elif kind == "dikovinki":
        try:
            region = list(DIKOVINKI_PRICES.keys())[int(value)]
        except (ValueError, IndexError):
            return
        categories = await get_service_categories(session, active_only=True)
        cat = next((c for c in categories if c.name == "Диковинки"), None)
        items = await get_service_items(session, cat.id, active_only=True) if cat else []
        item = next((i for i in items if i.name == region), None)
        unit_price = float(item.price) if item else DIKOVINKI_PRICES[region]
        shown_price = await price_with_discount_text(session, unit_price, "Диковинки")
        order_dict = {"service": "Диковинки", "region": region, "quantity_unit": "шт.", "unit_price": unit_price}
        prompt = f"✏️ *Диковинки — {region}*\n\nЦена: *{shown_price} за 1 шт.*\n\nВведи нужное количество:"
    elif kind == "okuly":
        try:
            item_name = OKULY_PRICES[int(value)][0]
        except (ValueError, IndexError):
            return
        categories = await get_service_categories(session, active_only=True)
        cat = next((c for c in categories if c.name == "Окулы"), None)
        items = await get_service_items(session, cat.id, active_only=True) if cat else []
        item = next((i for i in items if i.name == item_name), None)
        unit_price = float(item.price) if item else float(OKULY_PRICES[int(value)][1])
        shown_price = await price_with_discount_text(session, unit_price, "Окулы")
        order_dict = {"service": "Окулы", "service_item": item_name, "quantity_unit": "шт.", "unit_price": unit_price}
        prompt = f"✏️ *{item_name}*\n\nЦена: *{shown_price} за 1 шт.*\n\nВведи нужное количество:"
    else:
        return

    await state.clear()
    await state.update_data(**order_dict, step="quantity")
    await state.set_state(OrderFlow.waiting_input)
    if callback.message:
        await callback.message.edit_text(prompt)


@router.callback_query(F.data.startswith("service_item:"))
async def service_item_legacy_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Обработка устаревших inline-кнопок service_item:<cat_idx>:<item_idx>."""
    await callback.answer()
    if not callback.data:
        return
    try:
        _, ci_s, ii_s = callback.data.split(":", 2)
        ci, ii = int(ci_s), int(ii_s)
        category_name = PRICE_CATEGORIES[ci]
        categories = await get_service_categories(session, active_only=True)
        category = next((c for c in categories if c.name == category_name), None)
        items = await get_service_items(session, category.id, active_only=True) if category else []
        item = items[ii]
    except (ValueError, IndexError, KeyError):
        item = None

    if not item:
        if callback.message:
            kb = await service_category_keyboard(session)
            await callback.message.edit_text("❌ Пункт услуги не найден.", reply_markup=kb)
        return

    if item.quantity_mode == "quantity":
        await state.clear()
        await state.update_data(
            service=category_name,
            service_item=item.name,
            quantity_unit=item.unit,
            unit_price=float(item.price),
            step="quantity",
        )
        await state.set_state(OrderFlow.waiting_input)
        if callback.message:
            await callback.message.edit_text(
                f"✏️ *{item.name}*\n\n"
                f"Цена: *{format_price(item.price)} ₽ за 1 {item.unit}*\n\n"
                "Введи нужное количество:"
            )
        return

    await state.clear()
    await state.update_data(
        service=category_name,
        service_item=item.name,
        price=float(item.price),
        step="login",
    )
    await state.set_state(OrderFlow.waiting_input)
    if callback.message:
        await callback.message.edit_text(
            f"🛒 *Заказ услуги*\n\n*{category_name}*\n{item.name}\n\n"
            "🔐 *Шаг 1 из 3*\n\nОтправь почту (email), привязанную к аккаунту."
        )


@router.callback_query(F.data.startswith("region_tp_qty:"))
async def region_tp_quantity_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Выбор количества ТП для пропорционального расчёта цены зачистки."""
    if not callback.data:
        return
    try:
        _, order_id_s, qty_s = callback.data.split(":", 2)
        order_id = int(order_id_s)
        quantity = int(qty_s)
    except (ValueError, TypeError):
        await callback.answer("Некорректное количество ТП.", show_alert=True)
        return

    data = await state.get_data()
    if not data or data.get("id") != order_id:
        await callback.answer("Заказ не найден. Начните оформление заново.", show_alert=True)
        return

    base_price = float(data.get("price", 0))
    new_price = region_tp_price(base_price, quantity)
    await state.update_data(quantity=quantity, price=new_price)

    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            f"Вы выбрали **{quantity} ТП**.\n"
            f"Стоимость: **{format_price(new_price)} ₽**\n\n"
            "Теперь продолжайте оформление заказа."
        )


# =========================================================================
# 4. Текстовые шаги клиентского оформления заказа (FSM)
# =========================================================================

@router.message(
    StateFilter(
        OrderFlow.waiting_input,
        OrderFlow.quantity,
        OrderFlow.login,
        OrderFlow.password,
        OrderFlow.telegram_username,
    ),
    F.text,
)
async def process_order_text_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Обработка текстовых шагов заказа: quantity -> login -> password -> telegram_username."""
    text = (message.text or "").strip()
    data = await state.get_data()
    step = data.get("step")
    if not step:
        current_state = await state.get_state()
        if current_state == OrderFlow.quantity.state:
            step = "quantity"
        elif current_state == OrderFlow.login.state:
            step = "login"
        elif current_state == OrderFlow.password.state:
            step = "password"
        elif current_state == OrderFlow.telegram_username.state:
            step = "telegram_username"

    # Шаг 0: ввод количества
    if step == "quantity":
        if not re.fullmatch(r"[1-9]\d{0,5}", text):
            await message.answer("❌ Введи целое положительное количество, например: 37.")
            return
        quantity = int(text)
        if quantity > 100000:
            await message.answer("❌ Максимальное количество — 100000 шт.")
            return

        unit_price = float(data.get("unit_price", 0))
        raw_price = round(quantity * unit_price, 2)
        service = data.get("service", "")

        if service == "Диковинки":
            region = data.get("region", "")
            item_line = f"{region} — {quantity} шт. × {format_price(unit_price)} ₽"
        elif service == "Окулы":
            item_line = f"{data.get('service_item', '')} — {quantity} шт. × {format_price(unit_price)} ₽"
        elif service == "Телепорты":
            item_line = f"{data.get('service_item', '')} — {quantity} ТП × {format_price(unit_price)} ₽"
        else:
            item_line = f"{quantity} круток × {format_price(unit_price)} ₽"

        discounted_price = await get_service_discounted_price(session, raw_price, service)
        was_price_str = f" (было {format_price(raw_price)} ₽)" if discounted_price < raw_price else ""

        await state.update_data(
            quantity=quantity,
            price=raw_price,
            service_item=item_line,
            step="login",
        )

        await message.answer(
            f"✅ Количество: *{quantity}*\n"
            f"💰 Стоимость: *{format_price(discounted_price)} ₽*{was_price_str}\n\n"
            "🔐 *Шаг 1 из 3*\n\n"
            "Отправь почту (email), привязанную к аккаунту."
        )
        return

    # Шаг 1: ввод email (логина)
    if step == "login":
        if len(text) > 254 or not re.fullmatch(EMAIL_REGEX, text):
            await message.answer(
                "❌ Это не похоже на корректный адрес электронной почты.\n\n"
                "Отправь почту аккаунта ещё раз, например: `example@mail.com`"
            )
            return

        await state.update_data(login=text, step="password")
        await message.answer(
            "🔐 *Шаг 2 из 3*\n\nОтправь пароль аккаунта."
        )
        return

    # Шаг 2: ввод пароля
    if step == "password":
        if not text or len(text) > 256:
            await message.answer("❌ Некорректный пароль. Отправь пароль ещё раз.")
            return

        await state.update_data(password=text, step="telegram_username")
        await message.answer(
            "🔐 *Шаг 3 из 3*\n\nОтправь свой Telegram-юзернейм.\n\n"
            "Например: @username"
        )
        return

    # Шаг 3: ввод Telegram-юзернейма
    if step == "telegram_username":
        username = text.strip()
        normalized = username if username.startswith("@") else "@" + username
        username_without_at = normalized[1:]
        if not re.fullmatch(TG_USERNAME_REGEX, username_without_at):
            await message.answer(
                "❌ Некорректный Telegram-юзернейм.\n\n"
                "Отправь юзернейм в формате @username.\n"
                "Допустимы латинские буквы, цифры и символ _."
            )
            return

        await state.update_data(telegram_username=normalized)
        await state.set_state(OrderFlow.confirm)

        order = await state.get_data()
        display_name = f"@{message.from_user.username}" if message.from_user and message.from_user.username else (message.from_user.full_name if message.from_user else "Клиент")

        base_price = float(order.get("price", 0))
        applicable_discounts = await get_applicable_discounts(session, order)
        final_price, discount_amount = calculate_discount(base_price, applicable_discounts, mode="sequential")

        summary = format_order_summary(
            client_name=display_name,
            telegram_username=normalized,
            region=order.get("region"),
            service=order.get("service"),
            service_item=order.get("service_item"),
            tier_index=order.get("tier_index"),
            base_price=base_price,
            final_price=final_price,
            discount_amount=discount_amount,
            details=order.get("details"),
        )
        await message.answer(summary, reply_markup=order_confirm_keyboard())
        return


# =========================================================================
# 5. Подтверждение и отмена заказа
# =========================================================================

@router.callback_query(F.data == "confirm_order")
async def confirm_order_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Подтверждение заказа: сохранение в БД, отправка админам и показ карточки успеха."""
    await callback.answer()
    order = await state.get_data()
    if not order or "price" not in order:
        if callback.message:
            await callback.message.edit_text(
                "❌ Заказ не найден. Нажми /start.",
                reply_markup=main_menu_keyboard(),
            )
        return

    display_name = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name
    base_price = float(order["price"])
    applicable = await get_applicable_discounts(session, order)

    # Если подходит несколько скидок, менеджер выберет способ применения
    if len(applicable) > 1:
        final_price = base_price
        discount_amount = 0.0
        discount_mode = "pending"
    elif len(applicable) == 1:
        final_price, discount_amount = calculate_discount(base_price, applicable, mode="sequential")
        discount_mode = "automatic"
    else:
        final_price, discount_amount, discount_mode = base_price, 0.0, "none"

    tier_index = order.get("tier_index")
    if tier_index is not None and 0 <= tier_index < len(TIER_NAMES):
        tier_name = TIER_NAMES[tier_index]
    else:
        tier_name = order.get("service_item") or order.get("service") or "Услуга"

    new_order = await create_order(
        session,
        client_telegram_id=callback.from_user.id,
        client_name=display_name,
        price=final_price,
        region=order.get("region", "Не требуется"),
        tier=tier_name,
        service=order.get("service", "Зачистка по регионам"),
        details=order.get("details", ""),
        original_price=base_price,
        discount_amount=discount_amount,
        discount_mode=discount_mode,
    )

    credentials_text = format_order_credentials(
        order_id=new_order.id,
        client_name=display_name,
        login=order.get("login", ""),
        password=order.get("password", ""),
        telegram_username=order.get("telegram_username", ""),
    )

    admin_status = ""
    if ADMIN_CHAT_IDS:
        sent, failed = await send_to_admin_chats(
            callback.bot,
            format_admin_order(new_order),
            reply_markup=admin_keyboard(new_order.id),
        )
        if sent:
            if len(applicable) > 1:
                # Сохраняем учётные данные в памяти до выбора скидки менеджером
                pending_credentials[new_order.id] = credentials_text
                if not hasattr(callback.bot, "pending_credentials"):
                    callback.bot.pending_credentials = {}
                callback.bot.pending_credentials[new_order.id] = credentials_text

                choice_kb = manager_discount_choice_keyboard(new_order.id)
                await send_to_admin_chats(
                    callback.bot,
                    format_discount_choice(new_order.id, applicable),
                    reply_markup=choice_kb,
                )
                admin_status = "Заявка отправлена менеджерам. Менеджер выберет способ применения скидок."
            else:
                await send_to_admin_chats(callback.bot, credentials_text)
                admin_status = "Заявка и данные для входа отправлены менеджерам."
            if failed:
                admin_status += " ⚠️ Не удалось отправить одному из чатов менеджеров."
        else:
            admin_status = "⚠️ Заказ сохранён, но не удалось отправить его в чаты менеджеров. Проверь ADMIN_CHAT_IDS."
    else:
        admin_status = "⚠️ ADMIN_CHAT_IDS пока не настроен."

    kb = order_placed_keyboard(MANAGER_USERNAME)
    if callback.message:
        await callback.message.edit_text(
            f"✅ *Заказ оформлен!*\n\n{admin_status}\n\nОжидай ответа менеджера.",
            reply_markup=kb,
        )
    await state.clear()


@router.callback_query(F.data == "cancel_order")
async def cancel_order_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена заказа пользователем."""
    await callback.answer("Заказ отменён")
    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            f"🎮 *{SHOP_NAME}*\n\nЗаказ отменён. Выбери раздел:",
            reply_markup=main_menu_keyboard(),
        )
