"""Сервис отображения экранов бота с поддержкой медиа-баннеров (bot.services.ui).

Предоставляет функцию send_or_edit_screen, которая бесшовно управляет
переходами между текстовыми экранами и экранами с фотобаннерами.
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputMediaPhoto, Message

from bot.db.repo.banners import get_banner

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _has_photo(msg: Any) -> bool:
    """Проверяет, содержит ли объект сообщения реальный список фотографий Telegram."""
    photo = getattr(msg, "photo", None)
    return isinstance(photo, list) and len(photo) > 0


async def send_or_edit_screen(
    event: Message | CallbackQuery,
    session: AsyncSession | None,
    banner_key: str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Универсально отправляет или редактирует экран бота с учётом установленного баннера.

    Обрабатывает:
    - Наличие/отсутствие баннера в БД для раздела `banner_key`
    - Переходы text -> photo и photo -> text (безопасное удаление старого и отправка нового)
    - Переходы photo -> photo (edit_media с InputMediaPhoto)
    - Переходы text -> text (edit_text)
    - Командные события Message (/start, /menu)
    """
    file_id = None
    if session is not None:
        try:
            banner = await get_banner(session, banner_key)
            if banner and banner.file_id:
                file_id = banner.file_id
        except Exception:
            logger.exception("Ошибка при загрузке баннера для %s", banner_key)

    # 1. Событие от inline-кнопки (CallbackQuery)
    if isinstance(event, CallbackQuery):
        msg = event.message
        if not msg:
            return None

        # Если для экрана задан баннер (фото + подпись)
        if file_id:
            if _has_photo(msg):
                try:
                    return await msg.edit_media(
                        media=InputMediaPhoto(media=file_id, caption=text),
                        reply_markup=reply_markup,
                    )
                except TelegramBadRequest as err:
                    if "message is not modified" in str(err).lower():
                        return msg
                    logger.debug("Не удалось отредактировать медиа, отправляем новое: %s", err)

            try:
                await msg.delete()
            except Exception:
                pass
            return await msg.answer_photo(
                file_id,
                caption=text,
                reply_markup=reply_markup,
            )

        # Если баннера нет (чистый текст)
        else:
            if _has_photo(msg):
                try:
                    await msg.delete()
                except Exception:
                    pass
                return await msg.answer(
                    text,
                    reply_markup=reply_markup,
                )
            else:
                try:
                    return await msg.edit_text(
                        text,
                        reply_markup=reply_markup,
                    )
                except TelegramBadRequest as err:
                    if "message is not modified" in str(err).lower():
                        return msg
                    logger.debug("Не удалось отредактировать текст: %s", err)
                    return await msg.answer(text, reply_markup=reply_markup)

    # 2. Событие от текстовой команды (Message)
    else:
        if file_id:
            return await event.answer_photo(
                file_id,
                caption=text,
                reply_markup=reply_markup,
            )
        else:
            return await event.answer(
                text,
                reply_markup=reply_markup,
            )


__all__ = ["send_or_edit_screen"]
