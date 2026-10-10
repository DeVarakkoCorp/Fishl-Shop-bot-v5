"""Управление заказами менеджером: /orders, /allorders, mgr_all_orders, смены статусов и скидки."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import ADMIN_CHAT_IDS
from bot.constants import STATUS_CLIENT_MESSAGES, STATUS_LABELS
from bot.db.repo.discounts import get_active_discounts
from bot.db.repo.orders import (
    get_active_orders,
    get_all_manager_orders,
    get_order_by_id,
    update_order_discount,
    update_order_status,
)
from bot.filters import IsManager, is_manager_user
from bot.keyboards.manager import admin_keyboard, manager_all_orders_keyboard
from bot.services.notify import format_admin_order, send_to_admin_chats
from bot.services.pricing import calculate_discount, filter_applicable_discounts

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Хранилище временных credentials в памяти процесса (до применения скидки менеджером)
PENDING_CREDENTIALS: dict[int, str] = {}

router = Router(name="manager_orders")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())


async def show_manager_all_orders(
    event: Message | CallbackQuery,
    session: AsyncSession,
    edit: bool = False,
) -> None:
    """Отображает список всех заказов (до 50 штук) из БД с кнопками управления."""
    if not is_manager_user(event.from_user):
        if isinstance(event, CallbackQuery):
            if edit:
                await event.answer("Недоступно", show_alert=True)
            else:
                await event.message.answer("❌ Доступ запрещён.")
        else:
            await event.answer("❌ Доступ запрещён.")
        return

    rows = await get_all_manager_orders(session, limit=50)
    if not rows:
        text = "📦 *Все заказы из всех доступных баз*\n\nЗаказов пока нет."
        if edit and isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=manager_all_orders_keyboard())
        elif isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=manager_all_orders_keyboard())
        else:
            await event.answer(text, reply_markup=manager_all_orders_keyboard())
        return

    header_text = (
        "📦 *Все заказы из всех доступных баз*\n\n"
        "Ниже показаны последние 50 уникальных заказов."
    )
    if edit and isinstance(event, CallbackQuery):
        await event.message.edit_text(header_text, reply_markup=manager_all_orders_keyboard())
    elif isinstance(event, CallbackQuery):
        await event.message.answer(header_text, reply_markup=manager_all_orders_keyboard())
    else:
        await event.answer(header_text, reply_markup=manager_all_orders_keyboard())

    chat_id = event.message.chat.id if isinstance(event, CallbackQuery) else event.chat.id
    bot = event.bot

    for row in rows:
        text = format_admin_order(row)
        is_archive = getattr(row, "_is_archive", False)
        if is_archive:
            source_db = getattr(row, "_source_db", "orders.db")
            text += (
                f"\n\n🗄 Источник: `{source_db}`\n"
                "⚠️ Архивный заказ — изменение статуса из этой панели недоступно."
            )
            markup = None
        else:
            status = getattr(row, "status", "new")
            markup = (
                admin_keyboard(row.id, status)
                if status in ("new", "taken", "working")
                else None
            )
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


@router.message(Command("orders"))
async def orders_command(message: Message, session: AsyncSession) -> None:
    """Выводит список активных заказов (статусы new, taken, working) до 20 штук."""
    rows = await get_active_orders(session, limit=20)
    if not rows:
        await message.answer("📭 Активных заказов нет.")
        return
    for row in rows:
        await message.answer(
            format_admin_order(row),
            reply_markup=admin_keyboard(row.id, row.status),
        )


@router.message(Command("allorders"))
async def all_orders_command(message: Message, session: AsyncSession) -> None:
    """Команда /allorders для просмотра всех заказов."""
    await show_manager_all_orders(message, session, edit=False)


@router.callback_query(F.data == "mgr_all_orders")
async def mgr_all_orders_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Кнопка 'Все заказы' в панели менеджера."""
    await callback.answer()
    await show_manager_all_orders(callback, session, edit=True)


@router.callback_query(F.data.startswith("order_status:"))
async def order_status_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Смена статуса заказа менеджером: working, cancelled, done."""
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    try:
        order_id = int(parts[1])
    except ValueError:
        return
    new_status = parts[2]
    if new_status not in STATUS_LABELS:
        return

    manager = (
        f"@{callback.from_user.username}"
        if callback.from_user.username
        else callback.from_user.full_name
    )
    order = await update_order_status(
        session,
        order_id=order_id,
        status=new_status,
        manager_name=manager,
    )
    if not order:
        await callback.message.edit_text("❌ Заказ не найден.")
        return

    # Уведомление клиенту при смене статуса заказа
    client_msg_template = STATUS_CLIENT_MESSAGES.get(new_status)
    if client_msg_template and order.client_telegram_id:
        try:
            await callback.bot.send_message(
                chat_id=order.client_telegram_id,
                text=client_msg_template.format(order_id=order_id, manager=manager),
            )
        except Exception:
            logger.exception("Failed to notify client for order %s", order_id)

    await callback.message.edit_text(
        format_admin_order(order),
        reply_markup=admin_keyboard(order_id, new_status),
    )


@router.callback_query(F.data.regexp(r"^discount_(sum|seq):(\d+)$"))
async def apply_order_discount_choice(callback: CallbackQuery, session: AsyncSession) -> None:
    """Выбор способа применения скидок к заказу менеджером (сложить проценты или последовательно)."""
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 2:
        return
    try:
        order_id = int(parts[1])
    except ValueError:
        return

    mode = "summed" if callback.data.startswith("discount_sum:") else "sequential"
    order = await get_order_by_id(session, order_id)
    if not order:
        await callback.message.edit_text("❌ Заказ не найден.")
        return

    base = float(order.original_price if order.original_price is not None else order.price)
    order_for_calc = {"price": base, "service": order.service}
    active_discounts = await get_active_discounts(session)
    applicable = filter_applicable_discounts(order_for_calc, active_discounts)
    final, amount = calculate_discount(base, applicable, mode=mode)

    updated_order = await update_order_discount(
        session,
        order_id=order_id,
        price=final,
        original_price=base,
        discount_amount=amount,
        discount_mode=mode,
    )
    if not updated_order:
        await callback.message.edit_text("❌ Заказ не найден.")
        return

    await callback.message.edit_text(
        format_admin_order(updated_order),
        reply_markup=admin_keyboard(order_id, updated_order.status),
    )

    # Credentials хранятся в памяти до подтверждения выбора скидки менеджером
    pending = None
    try:
        if hasattr(callback.bot, "workflow_data"):
            pending = callback.bot.workflow_data.get("pending_credentials", {}).pop(order_id, None)
    except Exception:
        pass
    if not pending:
        pending = PENDING_CREDENTIALS.pop(order_id, None)

    if pending and ADMIN_CHAT_IDS:
        await send_to_admin_chats(callback.bot, pending)
