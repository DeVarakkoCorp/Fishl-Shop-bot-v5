"""Резервное копирование: команда /backup и кнопка mgr_backup."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.filters import IsManager
from bot.keyboards.manager import manager_keyboard
from bot.services.backup import upload_github_backup_async

logger = logging.getLogger(__name__)

router = Router(name="manager_backup")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())


@router.message(Command("backup"))
async def backup_command(message: Message) -> None:
    """Создание бэкапа по команде /backup."""
    try:
        ok = await upload_github_backup_async()
        text = (
            "✅ Бэкап БД и кода загружен на GitHub."
            if ok
            else "⚠️ GitHub-бэкап не настроен. Проверь GITHUB_* в Railway."
        )
        await message.answer(text, reply_markup=manager_keyboard())
    except Exception as exc:
        logger.exception("Manual GitHub backup command failed")
        await message.answer(f"❌ Не удалось сделать бэкап: {exc}")


@router.callback_query(F.data == "mgr_backup")
async def mgr_backup_callback(callback: CallbackQuery) -> None:
    """Создание бэкапа по кнопке mgr_backup в панели менеджера."""
    await callback.answer("Делаю бэкап...")
    try:
        ok = await upload_github_backup_async()
        if ok:
            text = "✅ Бэкап БД и кода загружен на GitHub."
        else:
            text = "⚠️ GitHub-бэкап не настроен. Добавь переменные GITHUB_* в Railway."
        await callback.message.edit_text(text, reply_markup=manager_keyboard())
    except Exception as exc:
        logger.exception("Manual GitHub backup failed")
        await callback.message.edit_text(
            f"❌ Не удалось сделать бэкап: {exc}",
            reply_markup=manager_keyboard(),
        )
