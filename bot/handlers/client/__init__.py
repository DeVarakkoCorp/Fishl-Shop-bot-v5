"""Клиентские хендлеры Fishl Shop (aiogram 3.31).

Список всех клиентских callback_data из legacy button() и их покрытие:
========================================================================
1.  back
    - Назначение: возврат в главное меню (для клиентов) или вызов show_manager_panel (для менеджеров).
    - Обработчик: bot/handlers/client/start.py -> back_callback

2.  contact
    - Назначение: показ контактов менеджера (@fishlme) и разработчика (@devarapq).
    - Обработчик: bot/handlers/client/start.py -> contact_callback

3.  prices
    - Назначение: открытие главного меню прайсов (зачистка, динамические категории, 57+ ранги).
    - Обработчик: bot/handlers/client/prices.py -> prices_menu_callback

4.  price_cleanup
    - Назначение: просмотр списка регионов для зачистки в разделе прайсов.
    - Обработчик: bot/handlers/client/prices.py -> price_cleanup_callback

5.  price_region:<region>
    - Назначение: карточка цен зачистки конкретного региона (0–100%, 50–100%, 80–100%) со скидками.
    - Обработчик: bot/handlers/client/prices.py -> price_region_details_callback

6.  price_category_db:<category_id>
    - Назначение: просмотр прайса динамической категории услуг из базы данных.
    - Обработчик: bot/handlers/client/prices.py -> price_category_db_callback

7.  price_category:<index>
    - Назначение: просмотр прайса статического раздела из EXTRA_PRICES.
    - Обработчик: bot/handlers/client/prices.py -> price_category_legacy_callback

8.  price_57
    - Назначение: меню разделов прайса для 57+ рангов (Крутки, Эндгейм, Натиск, Театр).
    - Обработчик: bot/handlers/client/prices.py -> price_57_callback

9.  rank57_price_category:<index>
    - Назначение: детальный прайс выбранной категории 57+ рангов со скидками.
    - Обработчик: bot/handlers/client/prices.py -> rank57_price_category_callback

10. my_orders
    - Назначение: просмотр списка последних заказов клиента и кнопка обновления.
    - Обработчик: bot/handlers/client/my_orders.py -> my_orders_callback

11. cleanup
    - Назначение: заказ услуги — вывод списка категорий (зачистка, динамические, 57+).
    - Обработчик: bot/handlers/client/order.py -> cleanup_menu_callback

12. cleanup_regions
    - Назначение: заказ зачистки — вывод списка регионов.
    - Обработчик: bot/handlers/client/order.py -> cleanup_regions_callback

13. region:<region>
    - Назначение: выбор региона зачистки и вывод вариантов объёма (0–100%, 50–100%, 80–100%).
    - Обработчик: bot/handlers/client/order.py -> select_region_callback

14. tier:<region>:<tier_index>
    - Назначение: выбор процента зачистки региона и переход к шагу 1 (email).
    - Обработчик: bot/handlers/client/order.py -> select_tier_callback

15. service_57
    - Назначение: заказ услуги для 57+ рангов — выбор раздела.
    - Обработчик: bot/handlers/client/order.py -> service_57_menu_callback

16. service57_category:<index>
    - Назначение: список вариантов услуг выбранного раздела 57+ рангов.
    - Обработчик: bot/handlers/client/order.py -> service57_category_callback

17. rank57_item:<category_index>:<item_index>
    - Назначение: выбор варианта услуги 57+ рангов и переход к шагу 1 (email).
    - Обработчик: bot/handlers/client/order.py -> rank57_item_select_callback

18. service_category_db:<category_id>
    - Назначение: выбор категории услуг из БД и вывод её вариантов.
    - Обработчик: bot/handlers/client/order.py -> service_category_db_callback

19. service_category:<index>
    - Назначение: legacy-выбор категории услуг по индексу из PRICE_CATEGORIES.
    - Обработчик: bot/handlers/client/order.py -> service_category_legacy_callback

20. service_item_custom:<item_id>
    - Назначение: запрос произвольного количества для услуги с quantity_mode="quantity".
    - Обработчик: bot/handlers/client/order.py -> service_item_custom_callback

21. service_item_db:<item_id>
    - Назначение: выбор варианта услуги из БД (с фиксированной ценой или количеством).
    - Обработчик: bot/handlers/client/order.py -> service_item_db_callback

22. custom_quantity:<kind>:<value>
    - Назначение: legacy-запрос количества (spins, dikovinki, okuly).
    - Обработчик: bot/handlers/client/order.py -> custom_quantity_legacy_callback

23. service_item:<category_index>:<item_index>
    - Назначение: legacy-выбор варианта услуги по индексам категории и пункта.
    - Обработчик: bot/handlers/client/order.py -> service_item_legacy_callback

24. region_tp_qty:<order_id>:<quantity>
    - Назначение: перерасчёт стоимости зачистки региона по выбранному числу ТП.
    - Обработчик: bot/handlers/client/order.py -> region_tp_quantity_callback

25. confirm_order
    - Назначение: окончательное подтверждение заказа клиентом, создание записи в БД и отправка админам.
    - Обработчик: bot/handlers/client/order.py -> confirm_order_callback

26. cancel_order
    - Назначение: отмена оформления заказа и возврат в главное меню.
    - Обработчик: bot/handlers/client/order.py -> cancel_order_callback

Клиентские команды:
========================================================================
• /start, /menu, /help, /chatid -> bot/handlers/client/start.py
• /myorders                    -> bot/handlers/client/my_orders.py
"""
from __future__ import annotations

from aiogram import Router

from bot.handlers.client.my_orders import router as my_orders_router
from bot.handlers.client.order import router as order_router
from bot.handlers.client.prices import router as prices_router
from bot.handlers.client.start import router as start_router

router = Router(name="client")

router.include_router(start_router)
router.include_router(prices_router)
router.include_router(order_router)
router.include_router(my_orders_router)

__all__ = ["router"]
