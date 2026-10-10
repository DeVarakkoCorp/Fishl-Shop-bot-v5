"""Панель менеджера: команда /manager, вызов панели и возврат назад (mgr_panel, mgr_back)."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.filters import IsManager, is_manager_user
from bot.keyboards.manager import manager_keyboard

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

router = Router(name="manager_panel")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())


async def show_manager_panel(
    event: Message | CallbackQuery,
    edit: bool = False,
) -> None:
    """Отображает главное меню панели менеджера.

    Сигнатура async def show_manager_panel(event: Message | CallbackQuery, edit: bool = False)
    сохранена для переиспользования в клиентском коде и обработчиках возврата.
    """
    if not is_manager_user(event.from_user):
        if isinstance(event, CallbackQuery):
            if edit:
                await event.answer("Недоступно", show_alert=True)
            else:
                await event.message.answer("❌ Доступ запрещён.")
        else:
            await event.answer("❌ Доступ запрещён.")
        return

    text = "👨‍💼 *Панель менеджера*\n\nВыбери действие:"
    if edit and isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=manager_keyboard())
    elif isinstance(event, CallbackQuery):
        await event.message.answer(text, reply_markup=manager_keyboard())
    else:
        await event.answer(text, reply_markup=manager_keyboard())


@router.message(Command("manager"))
async def manager_command(message: Message, state: FSMContext) -> None:
    """Открывает панель менеджера по команде /manager."""
    await state.clear()
    try:
        await show_manager_panel(message, edit=False)
    except Exception:
        logger.exception("Failed to open manager panel via /manager")
        await message.answer("❌ Не удалось открыть панель менеджера. Проверь логи Railway.")


@router.callback_query(F.data.in_({"mgr_panel", "mgr_back"}))
async def manager_panel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в панель менеджера по кнопкам mgr_panel и mgr_back."""
    await state.clear()
    await callback.answer()
    await show_manager_panel(callback, edit=True)
