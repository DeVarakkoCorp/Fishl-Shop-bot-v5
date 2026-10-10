"""Клиентские хендлеры раздела 'Прайсы' (просмотр цен на зачистку, услуги и 57+ ранги)."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.constants import RANK57_CATEGORIES
from bot.db.repo.discounts import get_active_discounts
from bot.db.repo.prices import get_region_prices
from bot.db.repo.services import get_service_category
from bot.keyboards.client import (
    price_57_view_keyboard,
    price_category_view_keyboard,
    price_region_keyboard,
    price_region_view_keyboard,
    rank57_keyboard,
    region_keyboard,
)
from bot.keyboards.common import main_menu_keyboard
from bot.prices import EXTRA_PRICES, PRICE_CATEGORIES, PRICES
from bot.services.pricing import price_with_discount_text_sync
from bot.services.texts import format_rank57_prices, service_category_text

from bot.emojis import Emojis, emoji
from bot.services.ui import send_or_edit_screen

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="client_prices")


@router.callback_query(F.data == "prices")
async def prices_menu_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Главное меню прайсов."""
    await callback.answer()
    kb = await price_region_keyboard(session)
    text = f"{emoji(Emojis.MORA)} *Прайсы*\n\nВыбери раздел:"
    await send_or_edit_screen(callback, session, "prices", text, reply_markup=kb)


@router.callback_query(F.data == "price_cleanup")
async def price_cleanup_callback(callback: CallbackQuery) -> None:
    """Выбор региона для просмотра цен зачистки."""
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "🧹 *Прайс зачистки по регионам*\n\nВыбери регион:",
            reply_markup=region_keyboard("price_region"),
        )


@router.callback_query(F.data.startswith("price_region:"))
async def price_region_details_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Просмотр цен зачистки для конкретного региона с учётом скидок."""
    await callback.answer()
    if not callback.data:
        return
    region = callback.data.split(":", 1)[1]
    if region not in PRICES:
        if callback.message:
            await callback.message.edit_text("❌ Регион не найден.", reply_markup=main_menu_keyboard())
        return

    prices = await get_region_prices(session, region)
    active_discounts = await get_active_discounts(session)
    p0 = price_with_discount_text_sync(prices["0-100"], "Зачистка по регионам", active_discounts)
    p50 = price_with_discount_text_sync(prices["50-100"], "Зачистка по регионам", active_discounts)
    p80 = price_with_discount_text_sync(prices["80-100"], "Зачистка по регионам", active_discounts)

    text = (
        f"💰 *{region}*\n\n"
        f"0–100% — *{p0}*\n"
        f"50–100% — *{p50}*\n"
        f"80–100% — *{p80}*"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=price_region_view_keyboard())


@router.callback_query(F.data.startswith("price_category_db:"))
async def price_category_db_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Просмотр прайса динамической категории услуг из базы данных."""
    await callback.answer()
    if not callback.data:
        return
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        category_id = 0

    category = await get_service_category(session, category_id)
    if not category:
        if callback.message:
            kb = await price_region_keyboard(session)
            await callback.message.edit_text("❌ Раздел не найден.", reply_markup=kb)
        return

    cat_text = await service_category_text(session, category_id)
    if callback.message:
        await callback.message.edit_text(
            f"💰 *{category.name}*\n\n{cat_text}",
            reply_markup=price_category_view_keyboard(),
        )


@router.callback_query(F.data.startswith("price_category:"))
async def price_category_legacy_callback(callback: CallbackQuery) -> None:
    """Просмотр статического раздела цен из EXTRA_PRICES."""
    await callback.answer()
    if not callback.data:
        return
    try:
        index = int(callback.data.split(":", 1)[1])
        category = PRICE_CATEGORIES[index]
    except (ValueError, IndexError):
        if callback.message:
            await callback.message.edit_text("❌ Раздел не найден.", reply_markup=main_menu_keyboard())
        return

    text = f"💰 *{category}*\n\n{EXTRA_PRICES[category]}"
    if callback.message:
        await callback.message.edit_text(text, reply_markup=price_category_view_keyboard())


@router.callback_query(F.data == "price_57")
async def price_57_callback(callback: CallbackQuery) -> None:
    """Выбор раздела для 57+ рангов в меню прайсов."""
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "💰 *Для 57+ рангов*\n\nВыбери раздел:",
            reply_markup=rank57_keyboard("rank57_price_category"),
        )


@router.callback_query(F.data.startswith("rank57_price_category:"))
async def rank57_price_category_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Просмотр прайса конкретного раздела для 57+ рангов со скидками."""
    await callback.answer()
    if not callback.data:
        return
    try:
        index = int(callback.data.split(":", 1)[1])
        category = RANK57_CATEGORIES[index]
    except (ValueError, IndexError):
        if callback.message:
            kb = await price_region_keyboard(session)
            await callback.message.edit_text("❌ Раздел не найден.", reply_markup=kb)
        return

    text = await format_rank57_prices(session, category)
    if callback.message:
        await callback.message.edit_text(
            f"💰 *{category}*\n\n{text}",
            reply_markup=price_57_view_keyboard(),
        )
