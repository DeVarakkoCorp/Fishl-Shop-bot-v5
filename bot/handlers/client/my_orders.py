"""Клиентские хендлеры просмотра истории заказов (команда /myorders и callback my_orders)."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.db.repo.orders import get_client_orders
from bot.emojis import Emojis, emoji
from bot.keyboards.client import client_orders_keyboard
from bot.services.notify import format_client_order
from bot.services.ui import send_or_edit_screen

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="client_my_orders")


async def show_my_orders(
    event: Message | CallbackQuery,
    session: AsyncSession,
    edit: bool = False,
) -> None:
    """Отображает список последних заказов клиента (до 20 штук) с поддержкой баннера."""
    user_id = event.from_user.id
    rows = await get_client_orders(session, user_id)
    if not rows:
        text = f"{emoji(Emojis.ORDERS)} *Мои заказы*\n\nУ тебя пока нет оформленных заказов."
    else:
        blocks = [f"{emoji(Emojis.ORDERS)} *Мои заказы*\n"]
        for row in rows:
            blocks.append(format_client_order(row))
        blocks.append("\nПоказаны последние 20 заказов из всех доступных баз.")
        text = "\n\n".join(blocks)

    kb = client_orders_keyboard()
    await send_or_edit_screen(event, session, "my_orders", text, reply_markup=kb)


@router.message(Command("myorders"))
async def my_orders_command(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /myorders."""
    await show_my_orders(message, session, edit=False)


@router.callback_query(F.data == "my_orders")
async def my_orders_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Обработчик кнопки 'Мои заказы' и обновления списка."""
    await callback.answer()
    await show_my_orders(callback, session, edit=True)


__all__ = ["router", "show_my_orders", "my_orders_command", "my_orders_callback"]
