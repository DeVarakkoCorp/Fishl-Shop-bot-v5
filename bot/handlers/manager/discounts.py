"""Управление скидками: добавление, просмотр активных скидок, отключение и настройка периодов."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db.repo.discounts import (
    create_discount,
    deactivate_discount,
    get_active_discounts,
)
from bot.filters import IsManager
from bot.keyboards.manager import (
    manager_back_to_panel_keyboard,
    manager_discount_manage_keyboard,
    manager_discount_period_keyboard,
    manager_discount_replace_keyboard,
    manager_discount_type_keyboard,
    manager_discount_value_type_keyboard,
    manager_keyboard,
)
from bot.services.pricing import discount_description
from bot.states import ManagerDiscount

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="manager_discounts")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())


async def finalize_discount_creation(
    event: Message | CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    delete_old: bool = False,
) -> None:
    """Завершает создание скидки, сохраняет её в БД и отправляет подтверждение."""
    data = await state.get_data()
    kind = str(data.get("manager_discount_kind") or "threshold")
    threshold = float(data.get("manager_discount_threshold", 0.0) or 0.0)
    service = str(data.get("manager_discount_service", "") or "")
    percent = float(data.get("manager_discount_percent", 0.0) or 0.0)
    value_type = str(data.get("manager_discount_value_type", "%") or "%")
    expires_at = data.get("manager_discount_expires_at")

    await create_discount(
        session,
        kind=kind,
        percent=percent,
        value_type=value_type,
        threshold=threshold,
        service=service,
        expires_at=expires_at,
        delete_old=delete_old,
    )
    period = "без срока" if not expires_at else f"до {expires_at}"
    await state.clear()
    msg = "🗑 Старые скидки отключены.\n\n" if delete_old else ""
    msg += f"✅ Скидка добавлена.\n⏱ Период: {period}"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(msg, reply_markup=manager_keyboard())
    else:
        await event.answer(msg, reply_markup=manager_keyboard())


# ---------------------------------------------------------
# Callback-обработчики скидок
# ---------------------------------------------------------

@router.callback_query(F.data == "mgr_discount_add")
async def mgr_discount_add_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Старт добавления скидки: выбор типа (от суммы заказа или на услугу)."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "➕ *Добавление скидки*\n\nВыбери тип скидки:",
        reply_markup=manager_discount_type_keyboard(),
    )


@router.callback_query(F.data.startswith("mgr_discount_type:"))
async def mgr_discount_type_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор единицы размера скидки: рубли или проценты."""
    kind = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.update_data(manager_discount_kind=kind)
    await callback.message.edit_text(
        "💵 *Как задать размер скидки?*",
        reply_markup=manager_discount_value_type_keyboard(),
    )


@router.callback_query(F.data.startswith("mgr_discount_value_type:"))
async def mgr_discount_value_type_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос суммы/названия услуги в зависимости от типа скидки."""
    value_type = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.update_data(manager_discount_value_type=value_type)
    data = await state.get_data()
    kind = data.get("manager_discount_kind")
    if kind == "threshold":
        await state.set_state(ManagerDiscount.threshold)
        await callback.message.edit_text(
            "💰 Введи минимальную сумму заказа в рублях, например `1000`."
        )
    elif kind == "service":
        await state.set_state(ManagerDiscount.service)
        await callback.message.edit_text(
            "🛒 Введи точное название услуги, например `Крутки` или `Диковинки`."
        )


@router.callback_query(F.data.startswith("mgr_discount_period:"))
async def mgr_discount_period_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Выбор срока действия скидки."""
    choice = callback.data.split(":", 1)[1]
    await callback.answer()
    if choice == "custom":
        await state.set_state(ManagerDiscount.expires_at)
        await callback.message.edit_text(
            "🗓 Введи дату окончания в формате `ДД.ММ.ГГГГ ЧЧ:ММ`, например `30.09.2026 23:59`."
        )
        return

    expires_at = None
    if choice != "none":
        try:
            expires_at = (datetime.now() + timedelta(days=int(choice))).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            expires_at = None

    await state.update_data(manager_discount_expires_at=expires_at)
    active = await get_active_discounts(session)
    if active:
        await callback.message.edit_text(
            "⚠️ Уже есть активные скидки.\n\nОставить их или удалить перед добавлением новой?",
            reply_markup=manager_discount_replace_keyboard(),
        )
    else:
        await finalize_discount_creation(callback, session, state, delete_old=False)


@router.callback_query(F.data == "mgr_discount_keep")
async def mgr_discount_keep_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Создание скидки с сохранением старых скидок."""
    await callback.answer()
    await finalize_discount_creation(callback, session, state, delete_old=False)


@router.callback_query(F.data == "mgr_discount_replace")
async def mgr_discount_replace_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Создание скидки с отключением старых активных скидок."""
    await callback.answer()
    await finalize_discount_creation(callback, session, state, delete_old=True)


@router.callback_query(F.data == "mgr_discount_list")
async def mgr_discount_list_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Просмотр списка всех активных скидок."""
    await state.clear()
    await callback.answer()
    rows = await get_active_discounts(session)
    text = "📋 *Активные скидки*\n\n" + (discount_description(rows) if rows else "Активных скидок нет.")
    await callback.message.edit_text(text, reply_markup=manager_back_to_panel_keyboard())


@router.callback_query(F.data == "mgr_discount_manage")
async def mgr_discount_manage_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Меню отключения отдельных скидок."""
    await state.clear()
    await callback.answer()
    rows = await get_active_discounts(session)
    markup = manager_discount_manage_keyboard(rows)
    text = "🗑 *Управление скидками*\n\n" + (discount_description(rows) if rows else "Активных скидок нет.")
    await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("mgr_discount_disable:"))
async def mgr_discount_disable_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Отключение выбранной скидки по её ID."""
    try:
        discount_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await deactivate_discount(session, discount_id)
    await callback.answer("Скидка отключена")
    rows = await get_active_discounts(session)
    markup = manager_discount_manage_keyboard(rows)
    text = "🗑 *Управление скидками*\n\n" + (discount_description(rows) if rows else "Активных скидок нет.")
    await callback.message.edit_text(text, reply_markup=markup)


# ---------------------------------------------------------
# FSM-обработчики текстового ввода ManagerDiscount
# ---------------------------------------------------------

@router.message(F.text, StateFilter(ManagerDiscount.threshold))
async def discount_threshold_input(message: Message, state: FSMContext) -> None:
    """Ввод порога суммы заказа для пороговой скидки."""
    text = (message.text or "").strip()
    try:
        threshold = float(text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи сумму числом, например 1000.")
        return
    if threshold <= 0:
        await message.answer("❌ Сумма должна быть больше 0.")
        return
    await state.update_data(manager_discount_threshold=threshold)
    await state.set_state(ManagerDiscount.value)
    data = await state.get_data()
    unit = "процентах" if data.get("manager_discount_value_type", "%") == "%" else "рублях"
    example = "10" if unit == "процентах" else "100"
    await message.answer(f"📉 Введи размер скидки в {unit}, например `{example}`.")


@router.message(F.text, StateFilter(ManagerDiscount.service))
async def discount_service_input(message: Message, state: FSMContext) -> None:
    """Ввод названия услуги для скидки на конкретную услугу."""
    text = (message.text or "").strip()
    if len(text) > 100:
        await message.answer("❌ Слишком длинное название услуги.")
        return
    await state.update_data(manager_discount_service=text)
    await state.set_state(ManagerDiscount.value)
    data = await state.get_data()
    unit = "процентах" if data.get("manager_discount_value_type", "%") == "%" else "рублях"
    example = "15" if unit == "процентах" else "100"
    await message.answer(f"📉 Введи размер скидки в {unit}, например `{example}`.")


@router.message(F.text, StateFilter(ManagerDiscount.value))
async def discount_value_input(message: Message, state: FSMContext) -> None:
    """Ввод величины скидки (процент или фиксированная сумма)."""
    text = (message.text or "").strip()
    data = await state.get_data()
    value_type = data.get("manager_discount_value_type", "%")
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        unit = "процент" if value_type == "%" else "рублей"
        await message.answer(f"❌ Введи размер скидки числом в {unit}, например 10.")
        return
    if value <= 0:
        await message.answer("❌ Размер скидки должен быть больше 0.")
        return
    if value_type == "%" and value > 100:
        await message.answer("❌ Процент должен быть от 0.01 до 100.")
        return

    await state.update_data(manager_discount_percent=value)
    await state.set_state(None)
    await message.answer(
        "⏱ *Период действия скидки*\n\nВыбери срок:",
        reply_markup=manager_discount_period_keyboard(),
    )


@router.message(F.text, StateFilter(ManagerDiscount.expires_at))
async def discount_expires_at_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Ввод произвольной даты окончания скидки."""
    text = (message.text or "").strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        if dt <= datetime.now():
            await message.answer("❌ Дата окончания должна быть в будущем.")
            return
        expires_at = dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        await message.answer("❌ Неверный формат. Пример: 30.09.2026 23:59")
        return

    await state.update_data(manager_discount_expires_at=expires_at)
    await state.set_state(None)
    active = await get_active_discounts(session)
    if active:
        await message.answer(
            "⚠️ Уже есть активные скидки. Оставить их или удалить перед добавлением новой?",
            reply_markup=manager_discount_replace_keyboard(),
        )
    else:
        await finalize_discount_creation(message, session, state, delete_old=False)
