"""Тематические Telegram Premium кастомные эмодзи для Fishl Shop (bot.emojis).

Содержит:
- Идентификаторы (custom_emoji_id) премиум-эмодзи по стилистике Genshin Impact и Fischl Shop
- Стандартные эмодзи-фоллбэки для пользователей без Telegram Premium
- Функции форматирования для Markdown ([fallback](tg://emoji?id=...)) и HTML (<tg-emoji>)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EmojiItem:
    """Элемент эмодзи с текстовым фоллбэком и ID премиум-стикера."""
    fallback: str
    custom_id: str

    def as_markdown(self, use_custom: bool = True) -> str:
        """Форматирование для Markdown (ParseMode.MARKDOWN): [alt](tg://emoji?id=...)."""
        if use_custom and self.custom_id:
            return f"[{self.fallback}](tg://emoji?id={self.custom_id})"
        return self.fallback

    def as_html(self, use_custom: bool = True) -> str:
        """Форматирование для HTML (ParseMode.HTML): <tg-emoji emoji-id="...">alt</tg-emoji>."""
        if use_custom and self.custom_id:
            return f'<tg-emoji emoji-id="{self.custom_id}">{self.fallback}</tg-emoji>'
        return self.fallback

    def __str__(self) -> str:
        return self.fallback


# =========================================================================
# Конфигурация активного премиум эмодзи-пака Genshin Impact
# Первый выбранный пак: news_genshins (t.me/addemoji/news_genshins)
# =========================================================================
EMOJI_PACK_NAME = os.getenv("EMOJI_PACK_NAME", "news_genshins")
EMOJI_PACK_URL = f"https://t.me/addemoji/{EMOJI_PACK_NAME}"
EMOJI_PACK_TG_URI = f"tg://addemoji?set={EMOJI_PACK_NAME}"

# Настройка использования кастомных эмодзи из окружения (по умолчанию включена)
USE_PREMIUM_EMOJIS = os.getenv("USE_PREMIUM_EMOJIS", "true").lower() in ("1", "true", "yes")


# =========================================================================
# Набор тематических эмодзи для Genshin Impact / Fischl Shop
# =========================================================================
class Emojis:
    """Коллекция премиум эмодзи бота из набора news_genshins."""

    PACK_NAME = EMOJI_PACK_NAME
    PACK_URL = EMOJI_PACK_URL
    PACK_TG_URI = EMOJI_PACK_TG_URI


    # Фишль и Электро (Молния / Принцесса Осуждения)
    FISCHL = EmojiItem("⚡", os.getenv("EMOJI_FISCHL_ID", "5382061099688463996"))

    # Примогемы / Камни истока / Крутки
    PRIMO = EmojiItem("💫", os.getenv("EMOJI_PRIMO_ID", "5368324170671202286"))

    # Мора / Цены / Деньги
    MORA = EmojiItem("💰", os.getenv("EMOJI_MORA_ID", "5465465465465465465"))

    # Корзина / Услуги / Оформление
    CART = EmojiItem("🛒", os.getenv("EMOJI_CART_ID", "5427009714745786222"))

    # Корона / Менеджер / Администрация
    CROWN = EmojiItem("👑", os.getenv("EMOJI_CROWN_ID", "5380061214878297924"))

    # Огонь / Скидки / Горячие предложения
    FIRE = EmojiItem("🔥", os.getenv("EMOJI_FIRE_ID", "5373030364177587129"))

    # Галочка / Успех / Выполнено
    CHECK = EmojiItem("✅", os.getenv("EMOJI_CHECK_ID", "5424750942548805988"))

    # Крестик / Отмена / Ошибка
    CROSS = EmojiItem("❌", os.getenv("EMOJI_CROSS_ID", "5424750942548805989"))

    # Эндгейм / Бездна / Меч / Битва
    SWORD = EmojiItem("🌟", os.getenv("EMOJI_SWORD_ID", "5377465922858882772"))

    # Зачистка / Сундук / Регионы
    CHEST = EmojiItem("🧹", os.getenv("EMOJI_CHEST_ID", "5377465922858882773"))

    # Баннер / Изображение
    BANNER = EmojiItem("🖼", os.getenv("EMOJI_BANNER_ID", "5442993888565103986"))

    # Бэкап / Диск
    BACKUP = EmojiItem("💾", os.getenv("EMOJI_BACKUP_ID", "5443015481664176442"))

    # Мои заказы / Список
    ORDERS = EmojiItem("📋", os.getenv("EMOJI_ORDERS_ID", "5427009714745786223"))

    # Контакты / Связь
    CONTACT = EmojiItem("📞", os.getenv("EMOJI_CONTACT_ID", "5427009714745786224"))

    # Телепорт / Магия
    TELEPORT = EmojiItem("🔮", os.getenv("EMOJI_TELEPORT_ID", "5382061099688463997"))


# Хелпер для быстрого получения Markdown-эмодзи
def emoji(item: EmojiItem) -> str:
    """Возвращает эмодзи в формате Markdown с поддержкой Premium emoji."""
    return item.as_markdown(USE_PREMIUM_EMOJIS)


__all__ = [
    "EMOJI_PACK_NAME",
    "EMOJI_PACK_URL",
    "EMOJI_PACK_TG_URI",
    "EmojiItem",
    "Emojis",
    "USE_PREMIUM_EMOJIS",
    "emoji",
]
