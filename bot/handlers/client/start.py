"""Клиентские хендлеры стартовых команд и навигации (start, menu, help, chatid, back, contact)."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import SHOP_NAME
from bot.emojis import Emojis, emoji
from bot.filters import is_manager_user
from bot.keyboards.client import contact_keyboard
from bot.keyboards.common import main_menu_keyboard
from bot.services.ui import send_or_edit_screen

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="client_start")


@router.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession | None = None,
) -> None:
    """Обработчик команды /start: очистка FSM и вывод главного меню."""
    await state.clear()
    text = f"{emoji(Emojis.FISCHL)} *{SHOP_NAME}*\n\nВыбери нужный раздел:"
    if session is not None:
        await send_or_edit_screen(message, session, "main_menu", text, main_menu_keyboard())
    else:
        await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("menu"))
async def menu_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession | None = None,
) -> None:
    """Обработчик команды /menu: очистка FSM и вывод главного меню."""
    await state.clear()
    text = f"{emoji(Emojis.FISCHL)} *{SHOP_NAME}*\n\nВыбери нужный раздел:"
    if session is not None:
        await send_or_edit_screen(message, session, "main_menu", text, main_menu_keyboard())
    else:
        await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Показывает справку в зависимости от роли пользователя (менеджер / клиент)."""
    if is_manager_user(message.from_user):
        text = (
            f"{emoji(Emojis.CROWN)} *Помощь для менеджера*\n\n"
            "*Команды:*\n"
            "• `/start` — открыть главное меню.\n"
            "• `/menu` — снова открыть главное меню.\n"
            "• `/help` — показать эту справку.\n"
            "• `/manager` — открыть панель менеджера.\n"
            "• `/orders` — показать активные заказы и управление ими.\n"
            "• `/allorders` — посмотреть список заказов.\n"
            "• `/backup` — вручную сделать бэкап базы данных и кода на GitHub.\n"
            "• `/chatid` — показать ID текущего Telegram-чата.\n\n"
            "*Клиентский функционал:*\n"
            f"• {emoji(Emojis.MORA)} *Прайсы* — просмотр актуальных цен по доступным услугам.\n"
            f"• {emoji(Emojis.CART)} *Заказать услугу* — оформление заказа. При оформлении клиент указывает email, пароль и Telegram-юзернейм.\n"
            f"• {emoji(Emojis.ORDERS)} *Мои заказы* — просмотр последних заказов клиента.\n"
            f"• {emoji(Emojis.CONTACT)} *Связь* — контакты для связи.\n"
            "• Для услуг с количеством можно указать нужное количество; стоимость рассчитывается с учётом количества.\n"
            "• Если для заказа подходят несколько скидок, менеджер выбирает способ их применения.\n\n"
            "*Функции менеджера:*\n"
            "• 📦 *Все заказы* — просмотр заказов и изменение их статуса: взять, взять в работу, выполнить или отменить.\n"
            f"• {emoji(Emojis.FIRE)} *Скидки* — добавление, просмотр и отключение скидок; скидки могут быть в рублях или процентах.\n"
            "• 🛠 *Услуги и цены* — добавление услуг и вариантов, изменение цен и цен зачистки по регионам.\n"
            f"• {emoji(Emojis.BANNER)} *Баннеры* — загрузка и удаление фотобаннеров для разделов меню.\n"
            f"• {emoji(Emojis.BACKUP)} *Сделать бэкап* — ручной GitHub-бэкап базы данных и кода.\n"
            f"• После изменения статуса заказа клиент получает уведомление.\n"
        )
    else:
        text = (
            f"📖 *Помощь {SHOP_NAME}*\n\n"
            "*Доступные команды:*\n"
            "• `/start` — запустить бота и открыть главное меню.\n"
            "• `/menu` — открыть главное меню.\n"
            "• `/myorders` — посмотреть свои последние заказы.\n"
            "• `/help` — показать эту справку.\n\n"
            "*Доступные функции:*\n"
            f"• {emoji(Emojis.MORA)} *Прайсы* — посмотреть цены на доступные услуги.\n"
            f"• {emoji(Emojis.CART)} *Заказать услугу* — выбрать услугу и оформить заказ.\n"
            f"• {emoji(Emojis.ORDERS)} *Мои заказы* — посмотреть свои заказы и их статусы.\n"
            f"• {emoji(Emojis.CONTACT)} *Связь* — открыть контакты для связи.\n"
            "• При оформлении заказа нужно указать email, пароль и Telegram-юзернейм.\n"
            "• Для услуг с количеством можно выбрать или ввести нужное количество; итоговая цена зависит от количества.\n"
            "• Если действует скидка, она применяется к заказу по правилам магазина.\n"
            "• После изменения статуса заказа менеджером бот отправляет уведомление.\n\n"
            "*Контакты менеджеров:*\n"
            "💬 @fishlme — менеджер\n"
            "💬 @devarapq — менеджер\n"
        )
    await message.answer(text)


@router.message(Command("chatid"))
async def chat_id_command(message: Message) -> None:
    """Показывает ID текущего чата."""
    if message.chat:
        await message.answer(f"ID этого чата: `{message.chat.id}`")


@router.callback_query(F.data == "back")
async def back_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession | None = None,
) -> None:
    """Кнопка 'Назад' / 'Главное меню': для менеджера открывает панель, для клиента — главное меню."""
    await callback.answer()
    await state.clear()
    if is_manager_user(callback.from_user):
        try:
            from bot.handlers.manager.panel import show_manager_panel
            await show_manager_panel(callback, edit=True)
            return
        except ImportError:
            logger.debug("show_manager_panel not available yet, falling back to main menu")

    text = f"{emoji(Emojis.FISCHL)} *{SHOP_NAME}*\n\nВыбери нужный раздел:"
    if session is not None:
        await send_or_edit_screen(callback, session, "main_menu", text, main_menu_keyboard())
    elif callback.message:
        await callback.message.edit_text(text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "contact")
async def contact_callback(
    callback: CallbackQuery,
    session: AsyncSession | None = None,
) -> None:
    """Вывод раздела контактов менеджера и разработчика."""
    await callback.answer()
    text = (
        f"{emoji(Emojis.CONTACT)} *Связь*\n\n"
        "💬 *@fishlme — менеджер*\n"
        "Основной контакт для связи по заказам и вопросам.\n\n"
        "🛠 *@devarapq — разработчик*\n"
        "Связь с разработчиком только если менеджер не отвечает в течение нескольких часов."
    )
    if session is not None:
        await send_or_edit_screen(callback, session, "contact", text, contact_keyboard())
    elif callback.message:
        await callback.message.edit_text(text, reply_markup=contact_keyboard())


__all__ = ["router"]
