"""Общие клавиатуры бота (главное меню, навигация Назад/Главное меню)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constants import MAIN_MENU_BUTTONS

# Константная клавиатура главного меню
MAIN_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=title, callback_data=cb)]
        for title, cb in MAIN_MENU_BUTTONS
    ]
)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню бота."""
    return MAIN_MENU


def back_button(text: str = "⬅️ Назад", callback_data: str = "back") -> InlineKeyboardButton:
    """Кнопка возврата на предыдущий экран."""
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def home_button(text: str = "🏠 Главное меню", callback_data: str = "back") -> InlineKeyboardButton:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def back_keyboard(callback_data: str = "back") -> InlineKeyboardMarkup:
    """Клавиатура с одной кнопкой 'Назад'."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[back_button(callback_data=callback_data)]]
    )


def home_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с одной кнопкой 'Главное меню'."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[home_button()]]
    )
