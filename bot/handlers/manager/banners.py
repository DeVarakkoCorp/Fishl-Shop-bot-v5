"""Управление баннерами менеджером (bot.handlers.manager.banners).

Позволяет просматривать, устанавливать (загружать фото) и удалять медиа-баннеры
для разделов: Главное меню, Прайсы, Заказ услуг, Мои заказы, Связь.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from bot.db.repo.banners import (
    BANNER_SECTIONS,
    delete_banner,
    get_all_banners,
    get_banner,
    set_banner,
)
from bot.filters import IsManager
from bot.keyboards.manager import (
    manager_banner_cancel_keyboard,
    manager_banner_item_keyboard,
    manager_banners_menu_keyboard,
)
from bot.states import ManagerBanner

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="manager_banners")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())


@router.callback_query(F.data == "mgr_banners")
async def show_banners_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Отображает список экранов и статус баннеров для каждого."""
    await state.clear()
    await callback.answer()
    banners = await get_all_banners(session)
    text = (
        "🖼 *Управление баннерами экранов*\n\n"
        "Здесь можно установить визуальный медиа-баннер (фото) "
        "для любого из ключевых разделов бота.\n\n"
        "Выбери раздел для настройки:"
    )
    if callback.message and callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=manager_banners_menu_keyboard(banners))
    elif callback.message:
        await callback.message.edit_text(text, reply_markup=manager_banners_menu_keyboard(banners))


@router.callback_query(F.data.startswith("mgr_banner_view:"))
async def show_banner_item(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Просмотр текущего баннера выбранного раздела."""
    await state.clear()
    await callback.answer()
    parts = callback.data.split(":")
    key = parts[1] if len(parts) > 1 else "main_menu"
    title = BANNER_SECTIONS.get(key, key)
    banner = await get_banner(session, key)

    kb = manager_banner_item_keyboard(key, has_banner=bool(banner))
    if not callback.message:
        return

    if banner:
        text = f"🖼 *Баннер раздела {title}*\n\nСтатус: ✅ Установлен (обновлён: {banner.updated_at})"
        if callback.message.photo:
            try:
                await callback.message.edit_media(
                    media=InputMediaPhoto(media=banner.file_id, caption=text),
                    reply_markup=kb,
                )
                return
            except Exception:
                pass
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(photo=banner.file_id, caption=text, reply_markup=kb)
    else:
        text = f"🖼 *Баннер раздела {title}*\n\nСтатус: ⚪ Не установлен (используется обычный текст)."
        if callback.message.photo:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("mgr_banner_upload:"))
async def request_banner_photo(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Запрос фото для баннера."""
    await callback.answer()
    parts = callback.data.split(":")
    key = parts[1] if len(parts) > 1 else "main_menu"
    title = BANNER_SECTIONS.get(key, key)

    await state.set_state(ManagerBanner.waiting_photo)
    await state.update_data(banner_key=key)

    text = (
        f"📸 *Загрузка баннера для раздела {title}*\n\n"
        "Отправь фото, которое будет отображаться в шапке этого раздела.\n"
        "Рекомендуемый формат: горизонтальное изображение 16:9 или 2:1."
    )
    kb = manager_banner_cancel_keyboard(key)
    if callback.message:
        if callback.message.photo:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)


@router.message(ManagerBanner.waiting_photo, F.photo)
async def process_banner_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Сохранение присланного фото баннера."""
    data = await state.get_data()
    key = data.get("banner_key", "main_menu")
    title = BANNER_SECTIONS.get(key, key)
    photo = message.photo[-1]

    await set_banner(session, key=key, file_id=photo.file_id)
    await state.clear()

    await message.answer(
        f"✅ *Баннер для раздела {title} успешно установлен!*\n\n"
        "Теперь клиенты будут видеть его при открытии этого экрана.",
        reply_markup=manager_banner_item_keyboard(key, has_banner=True),
    )


@router.message(ManagerBanner.waiting_photo)
async def process_banner_invalid(message: Message, state: FSMContext) -> None:
    """Подсказка при отправке текста вместо фото."""
    data = await state.get_data()
    key = data.get("banner_key", "main_menu")
    await message.answer(
        "❌ Пожалуйста, отправь изображение (фото) как картинку, или нажми отмену:",
        reply_markup=manager_banner_cancel_keyboard(key),
    )


@router.callback_query(F.data.startswith("mgr_banner_delete:"))
async def process_banner_delete(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Удаление баннера раздела."""
    await state.clear()
    parts = callback.data.split(":")
    key = parts[1] if len(parts) > 1 else "main_menu"
    title = BANNER_SECTIONS.get(key, key)

    await delete_banner(session, key)
    await callback.answer("Баннер удалён", show_alert=True)

    text = f"🖼 *Баннер раздела {title}*\n\nСтатус: ⚪ Не установлен (удалён)."
    kb = manager_banner_item_keyboard(key, has_banner=False)
    if callback.message:
        if callback.message.photo:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)


__all__ = ["router"]
