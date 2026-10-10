"""Репозиторий баннеров экранов бота (bot.db.repo.banners).

Позволяет сохранять, загружать и удалять Telegram file_id баннеров (фотографий)
для ключевых экранов бота (главное меню, прайсы, заказ, мои заказы, связь).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from bot.db.models import Banner

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Доступные разделы для установки баннеров менеджером
BANNER_SECTIONS: dict[str, str] = {
    "main_menu": "🏠 Главное меню",
    "prices": "💰 Прайсы",
    "order": "🛒 Заказ услуг",
    "my_orders": "📋 Мои заказы",
    "contact": "📞 Связь",
}


async def get_banner(session: AsyncSession, key: str) -> Banner | None:
    """Возвращает баннер по ключу раздела."""
    return await session.get(Banner, key)


async def get_all_banners(session: AsyncSession) -> dict[str, Banner]:
    """Возвращает словарь всех установленных баннеров {key: Banner}."""
    stmt = select(Banner)
    result = await session.execute(stmt)
    return {b.key: b for b in result.scalars().all()}


async def set_banner(session: AsyncSession, key: str, file_id: str) -> Banner:
    """Сохраняет или обновляет file_id баннера для указанного раздела."""
    banner = await session.get(Banner, key)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if banner:
        banner.file_id = file_id
        banner.updated_at = now_str
    else:
        banner = Banner(key=key, file_id=file_id, updated_at=now_str)
        session.add(banner)

    await session.commit()
    await session.refresh(banner)
    return banner


async def delete_banner(session: AsyncSession, key: str) -> bool:
    """Удаляет баннер для указанного раздела (возвращает экран к чистому тексту)."""
    banner = await session.get(Banner, key)
    if not banner:
        return False
    await session.delete(banner)
    await session.commit()
    return True


__all__ = [
    "BANNER_SECTIONS",
    "get_banner",
    "get_all_banners",
    "set_banner",
    "delete_banner",
]
