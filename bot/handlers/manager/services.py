"""Управление услугами и ценами: добавление услуг, вариантов, редактирование цен и тарифов зачистки."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.constants import TIER_KEYS
from bot.db.repo.prices import get_region_prices, update_region_price
from bot.db.repo.services import (
    create_service_category,
    create_service_item,
    get_service_categories,
    get_service_category,
    get_service_item,
    get_service_items,
    update_service_item_price,
)
from bot.filters import IsManager
from bot.keyboards.manager import (
    manager_keyboard,
    manager_region_select_keyboard,
    manager_region_tiers_keyboard_db,
    manager_service_list_back_keyboard,
    manager_service_select_category_keyboard_db,
    manager_service_select_item_keyboard_db,
    manager_services_menu_keyboard,
)
from bot.prices import PRICES
from bot.services.pricing import format_price
from bot.states import ManagerService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="manager_services")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())


# ---------------------------------------------------------
# Callback-обработчики меню "Услуги и цены"
# ---------------------------------------------------------

@router.callback_query(F.data == "mgr_services")
async def mgr_services_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Главное меню раздела 'Услуги и цены'."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "🛠 *Услуги и цены*\n\nДобавляй новые услуги и меняй цены прямо из бота.",
        reply_markup=manager_services_menu_keyboard(),
    )


@router.callback_query(F.data == "mgr_service_list")
async def mgr_service_list_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Текстовый список всех услуг и вариантов с ценами."""
    await state.clear()
    await callback.answer()
    categories = await get_service_categories(session, active_only=False)
    lines = ["🛠 *Услуги и цены*", ""]
    for cat in categories:
        lines.append(f"*{cat.name}*")
        items = await get_service_items(session, cat.id, active_only=False)
        for item in items:
            suffix = f"/{item.unit}" if item.quantity_mode == "quantity" else ""
            lines.append(f"• {item.name} — {format_price(item.price)} ₽{suffix}")
        lines.append("")
    await callback.message.edit_text(
        "\n".join(lines)[:4000],
        reply_markup=manager_service_list_back_keyboard(),
    )


@router.callback_query(F.data == "mgr_service_add")
async def mgr_service_add_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Запуск добавления новой услуги."""
    await state.clear()
    await state.set_state(ManagerService.name)
    await callback.answer()
    await callback.message.edit_text("➕ *Новая услуга*\n\nВведи название новой услуги:")


@router.callback_query(F.data == "mgr_service_item_add")
async def mgr_service_item_add_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Выбор существующей услуги для добавления нового варианта."""
    await state.clear()
    await callback.answer()
    markup = await manager_service_select_category_keyboard_db(
        session,
        prefix="mgr_service_item_category",
    )
    await callback.message.edit_text(
        "➕ *Новый вариант*\n\nВыбери существующую услугу:",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("mgr_service_item_category:"))
async def mgr_service_item_category_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Категория выбрана, запрос названия нового варианта."""
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        category_id = 0
    cat = await get_service_category(session, category_id)
    if not cat:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await state.set_state(ManagerService.item_name)
    await state.update_data(manager_service_category_id=category_id)
    await callback.message.edit_text(f"➕ *{cat.name}*\n\nВведи название нового варианта:")


@router.callback_query(F.data == "mgr_service_edit")
async def mgr_service_edit_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Выбор услуги для изменения цены варианта."""
    await state.clear()
    await callback.answer()
    markup = await manager_service_select_category_keyboard_db(
        session,
        prefix="mgr_service_edit_category",
    )
    await callback.message.edit_text(
        "✏️ *Изменение цены*\n\nВыбери услугу:",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("mgr_service_edit_category:"))
async def mgr_service_edit_category_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Выбор конкретного варианта выбранной услуги для изменения цены."""
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        category_id = 0
    cat = await get_service_category(session, category_id)
    if not cat:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await callback.answer()
    markup = await manager_service_select_item_keyboard_db(session, category_id)
    await callback.message.edit_text(
        f"✏️ *{cat.name}*\n\nВыбери пункт:",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("mgr_service_price:"))
async def mgr_service_price_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Выбран вариант услуги для изменения цены, запрос ввода новой цены."""
    try:
        item_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        item_id = 0
    item = await get_service_item(session, item_id)
    if not item:
        await callback.answer("Пункт не найден", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await state.set_state(ManagerService.price)
    await state.update_data(manager_service_item_id=item_id)
    await callback.message.edit_text(
        f"✏️ *{item.name}*\n\n"
        f"Текущая цена: *{format_price(item.price)} ₽*\n\n"
        "Введи новую цену:"
    )


@router.callback_query(F.data == "mgr_region_edit")
async def mgr_region_edit_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор региона для изменения цен зачистки."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "🧹 *Изменение цен зачистки*\n\nВыбери регион:",
        reply_markup=manager_region_select_keyboard(),
    )


@router.callback_query(F.data.startswith("mgr_region:"))
async def mgr_region_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Выбор тарифа зачистки для указанного региона."""
    region = callback.data.split(":", 1)[1]
    if region not in PRICES:
        await callback.answer("Регион не найден", show_alert=True)
        return
    await callback.answer()
    markup = await manager_region_tiers_keyboard_db(session, region)
    await callback.message.edit_text(
        f"🧹 *{region}*\n\nВыбери цену:",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("mgr_region_price:"))
async def mgr_region_price_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Запрос ввода новой цены для выбранного уровня зачистки региона."""
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        return
    region, tier = parts[1], parts[2]
    if region not in PRICES or tier not in TIER_KEYS:
        await callback.answer("Некорректная цена", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await state.set_state(ManagerService.region_price)
    await state.update_data(manager_region=region, manager_tier=tier)
    prices = await get_region_prices(session, region)
    await callback.message.edit_text(
        f"✏️ *{region} — {tier}*\n\n"
        f"Текущая цена: *{format_price(prices[tier])} ₽*\n\n"
        "Введи новую цену:"
    )


# ---------------------------------------------------------
# FSM-обработчики текстового ввода ManagerService
# ---------------------------------------------------------

@router.message(F.text, StateFilter(ManagerService.name))
async def service_name_input(message: Message, state: FSMContext) -> None:
    """Ввод названия новой категории услуги."""
    text = (message.text or "").strip()
    if not text or len(text) > 80:
        await message.answer("❌ Название должно содержать от 1 до 80 символов.")
        return
    await state.update_data(manager_service_name=text)
    await state.set_state(ManagerService.price)
    await message.answer("💰 Введи цену первой услуги в рублях, например 150.")


@router.message(F.text, StateFilter(ManagerService.price))
async def service_price_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Ввод цены услуги (создание новой либо обновление существующей)."""
    text = (message.text or "").strip()
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи цену числом.")
        return
    if value <= 0 or value > 1_000_000:
        await message.answer("❌ Цена должна быть от 0 до 1 000 000 ₽.")
        return

    data = await state.get_data()
    item_id = data.get("manager_service_item_id")
    if item_id:
        await update_service_item_price(session, item_id, value)
        await state.clear()
        await message.answer("✅ Цена изменена.", reply_markup=manager_keyboard())
        return

    name = data.get("manager_service_name")
    if not name:
        await state.clear()
        await message.answer("❌ Не удалось определить услугу.", reply_markup=manager_keyboard())
        return

    cat = await create_service_category(session, name=name)
    await create_service_item(
        session,
        category_id=cat.id,
        name=name,
        price=value,
        quantity_mode="fixed",
        unit="шт.",
        sort_order=0,
    )
    await state.clear()
    await message.answer(
        f"✅ Услуга {name} добавлена с ценой {format_price(value)} ₽.",
        reply_markup=manager_keyboard(),
    )


@router.message(F.text, StateFilter(ManagerService.item_name))
async def service_item_name_input(message: Message, state: FSMContext) -> None:
    """Ввод названия нового варианта услуги."""
    text = (message.text or "").strip()
    if not text or len(text) > 100:
        await message.answer("❌ Название должно содержать от 1 до 100 символов.")
        return
    await state.update_data(manager_service_item_name=text)
    await state.set_state(ManagerService.item_price)
    await message.answer("💰 Введи цену варианта в рублях:")


@router.message(F.text, StateFilter(ManagerService.item_price))
async def service_item_price_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Ввод цены нового варианта услуги."""
    text = (message.text or "").strip()
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи цену числом.")
        return
    if value <= 0 or value > 1_000_000:
        await message.answer("❌ Цена должна быть от 0 до 1 000 000 ₽.")
        return

    data = await state.get_data()
    cid = data.get("manager_service_category_id")
    name = data.get("manager_service_item_name")
    if not cid or not name:
        await state.clear()
        await message.answer("❌ Не удалось сохранить вариант.", reply_markup=manager_keyboard())
        return

    await create_service_item(
        session,
        category_id=cid,
        name=name,
        price=value,
        quantity_mode="fixed",
        unit="шт.",
    )
    await state.clear()
    await message.answer("✅ Вариант добавлен.", reply_markup=manager_keyboard())


@router.message(F.text, StateFilter(ManagerService.region_price))
async def service_region_price_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Ввод новой цены для уровня зачистки региона."""
    text = (message.text or "").strip()
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи цену числом.")
        return
    if value <= 0 or value > 1_000_000:
        await message.answer("❌ Цена должна быть от 0 до 1 000 000 ₽.")
        return

    data = await state.get_data()
    region = data.get("manager_region")
    tier = data.get("manager_tier")
    if not region or region not in PRICES or not tier or tier not in TIER_KEYS:
        await state.clear()
        await message.answer("❌ Регион или уровень не найден.", reply_markup=manager_keyboard())
        return

    await update_region_price(session, region, tier, value)
    await state.clear()
    await message.answer("✅ Цена зачистки изменена.", reply_markup=manager_keyboard())
