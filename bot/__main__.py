"""Главная точка входа бота Fishl Shop (aiogram 3.31).

Запуск:
    python -m bot
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent

from bot.config import (
    ADMIN_CHAT_IDS,
    BOT_TOKEN,
    GITHUB_BACKUP_BRANCH,
    GITHUB_BACKUP_INTERVAL_MINUTES,
    SHOP_NAME,
)
from bot.db.engine import dispose_engine
from bot.db.fsm_storage import SqliteStorage
from bot.db.setup import setup_database
from bot.handlers.client import router as client_router
from bot.handlers.manager import router as manager_router
from bot.middlewares import DbSessionMiddleware
from bot.services.backup import backup_loop, github_backup_enabled

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger("fishl_bot")


async def setup_bot_commands(bot: Bot) -> None:
    """Устанавливает списки команд для обычных пользователей и менеджеров."""
    client_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="myorders", description="Мои заказы"),
        BotCommand(command="help", description="Помощь"),
    ]
    manager_commands = client_commands + [
        BotCommand(command="manager", description="Панель менеджера"),
        BotCommand(command="orders", description="Активные заказы"),
        BotCommand(command="allorders", description="Все заказы"),
        BotCommand(command="backup", description="Сделать бэкап"),
        BotCommand(command="chatid", description="Показать ID чата"),
    ]

    try:
        await bot.set_my_commands(client_commands)
    except Exception:
        logger.exception("Не удалось установить общие команды бота")

    for chat_id in ADMIN_CHAT_IDS:
        try:
            await bot.set_my_commands(manager_commands, scope=BotCommandScopeChat(chat_id=chat_id))
        except Exception:
            logger.warning("Не удалось установить команды для чата менеджера %s", chat_id)


async def on_startup(bot: Bot, dispatcher: Dispatcher) -> None:
    """Хук старта бота: команды и запуск фонового бэкапа."""
    await setup_bot_commands(bot)

    backup_task = None
    if github_backup_enabled():
        interval = max(15, int(GITHUB_BACKUP_INTERVAL_MINUTES))
        backup_task = asyncio.create_task(backup_loop(interval))
        logger.info(
            "GitHub-бэкапы активированы: каждые %d минут, ветка=%s",
            interval,
            GITHUB_BACKUP_BRANCH,
        )

    dispatcher["backup_task"] = backup_task
    logger.info("Бот %s успешно запущен и готов к работе.", SHOP_NAME)


async def on_shutdown(bot: Bot, dispatcher: Dispatcher) -> None:
    """Хук завершения работы: отмена задач и закрытие соединений."""
    logger.info("Завершение работы бота...")
    backup_task: asyncio.Task | None = dispatcher.get("backup_task")
    if backup_task and not backup_task.done():
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            pass

    await bot.session.close()
    await dispose_engine()
    logger.info("Все подключения и ресурсы освобождены.")


async def on_error(event: ErrorEvent) -> bool:
    """Глобальный перехватчик необработанных исключений."""
    logger.exception("Необработанное исключение при обработке апдейта:", exc_info=event.exception)
    return True


async def main() -> None:
    """Основная асинхронная функция запуска бота."""
    if not BOT_TOKEN:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан в переменных окружения!")
        sys.exit(1)

    # 1. Инициализация и миграция БД
    sessionmaker = await setup_database()

    # 2. Инициализация диспетчера с постоянным FSM-хранилищем в БД
    dp = Dispatcher(storage=SqliteStorage(sessionmaker))

    # 3. Регистрация middleware сессии БД
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))

    # 4. Регистрация роутеров (менеджерский первым для приоритета фильтров)
    dp.include_router(manager_router)
    dp.include_router(client_router)

    # 5. Регистрация обработчика ошибок
    dp.errors.register(on_error)

    # 6. Регистрация хуков жизненного цикла aiogram 3
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 7. Инициализация экземпляра бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    # 8. Запуск поллинга
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
