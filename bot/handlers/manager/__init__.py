"""Менеджерские хендлеры Fishl Shop бота.

Список ВСЕХ менеджерских callback_data из legacy/bot_ptb.py и их покрытие:
1.  mgr_panel - Главное меню панели менеджера (panel.py)
2.  mgr_back - Возврат в меню панели менеджера (panel.py)
3.  mgr_all_orders - Просмотр последних 50 заказов из всех баз (orders.py)
4.  mgr_backup - Ручное создание бэкапа БД и кода на GitHub (backup.py)
5.  mgr_services - Меню раздела 'Услуги и цены' (services.py)
6.  mgr_service_list - Текстовый список всех услуг и цен (services.py)
7.  mgr_service_add - Добавление новой услуги/категории (services.py)
8.  mgr_service_item_add - Выбор категории для добавления варианта (services.py)
9.  mgr_service_item_category:<category_id> - Ввод названия нового варианта услуги (services.py)
10. mgr_service_edit - Выбор категории для изменения цен вариантов (services.py)
11. mgr_service_edit_category:<category_id> - Выбор конкретного варианта для изменения цены (services.py)
12. mgr_service_price:<item_id> - Ввод новой цены варианта услуги (services.py)
13. mgr_region_edit - Меню выбора региона для изменения цен зачистки (services.py)
14. mgr_region:<region> - Меню выбора тарифа зачистки выбранного региона (services.py)
15. mgr_region_price:<region>:<tier> - Ввод новой цены тарифа зачистки региона (services.py)
16. mgr_discount_add - Выбор типа скидки (порог суммы или на услугу) (discounts.py)
17. mgr_discount_type:<kind> - Выбор типа значения скидки (RUB или %) (discounts.py)
18. mgr_discount_value_type:<value_type> - Ввод суммы/названия услуги для скидки (discounts.py)
19. mgr_discount_period:<choice> - Выбор срока действия скидки (none, 1, 7, 30, custom) (discounts.py)
20. mgr_discount_keep - Сохранение старых скидок при создании новой (discounts.py)
21. mgr_discount_replace - Отключение старых скидок при создании новой (discounts.py)
22. mgr_discount_list - Просмотр списка действующих активных скидок (discounts.py)
23. mgr_discount_manage - Меню отключения отдельных скидок (discounts.py)
24. mgr_discount_disable:<discount_id> - Отключение скидки по ID (discounts.py)
25. order_status:<order_id>:<new_status> - Смена статуса заказа (working, cancelled, done) (orders.py)
26. discount_sum:<order_id> - Применение скидок сложением процентов (orders.py)
27. discount_seq:<order_id> - Применение скидок последовательно (orders.py)

Команды менеджера:
- /manager - Панель менеджера (panel.py)
- /orders - Список активных заказов (orders.py)
- /allorders - Список всех заказов (orders.py)
- /backup - Сделать бэкап на GitHub (backup.py)
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.handlers.manager.backup import router as backup_router
from bot.handlers.manager.banners import router as banners_router
from bot.handlers.manager.discounts import router as discounts_router
from bot.handlers.manager.orders import (
    apply_order_discount_choice,
    orders_command,
    router as orders_router,
    show_manager_all_orders,
)
from bot.handlers.manager.panel import (
    router as panel_router,
    show_manager_panel,
)
from bot.handlers.manager.services import router as services_router

# Основной роутер менеджерских функций
router = Router(name="manager")

# Подключаем роутеры разделов (каждый фильтруется IsManager())
router.include_router(panel_router)
router.include_router(orders_router)
router.include_router(services_router)
router.include_router(discounts_router)
router.include_router(banners_router)
router.include_router(backup_router)

# Fallback роутер в КОНЦЕ для не-менеджеров:
# Если клик на менеджерский callback совершил не менеджер, показываем alert "Недоступно", как в legacy.
fallback_router = Router(name="manager_fallback")


@fallback_router.callback_query(
    F.data.startswith("mgr_")
    | F.data.startswith("order_status:")
    | F.data.regexp(r"^discount_(sum|seq):")
)
async def manager_unauthorized_callback(callback: CallbackQuery) -> None:
    """Отклоняет доступ не-менеджеров к менеджерским callback-кнопкам."""
    await callback.answer("Недоступно", show_alert=True)


router.include_router(fallback_router)

__all__ = [
    "apply_order_discount_choice",
    "orders_command",
    "router",
    "show_manager_all_orders",
    "show_manager_panel",
]
