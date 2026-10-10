"""FSM-хранилище на базе SQLAlchemy/SQLite для aiogram 3.31 (bot.db.fsm_storage).

Реализует BaseStorage с сохранением состояний и данных в таблицу fsm_state.
Полностью переживает перезапуск бота и контейнера.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.engine import get_sessionmaker
from bot.db.models import FsmState

logger = logging.getLogger(__name__)


class SqliteStorage(BaseStorage):
    """Асинхронное постоянное хранилище FSM для aiogram 3.31."""

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_maker = session_maker

    def _get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        if self._session_maker is not None:
            return self._session_maker
        return get_sessionmaker()

    @staticmethod
    def _make_key(key: StorageKey) -> str:
        """Преобразует StorageKey в строковый первичный ключ."""
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id}:{key.business_connection_id}:{key.destiny}"

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        """Устанавливает или сбрасывает состояние пользователя."""
        state_str = state.state if isinstance(state, State) else state
        str_key = self._make_key(key)
        session_maker = self._get_session_maker()

        async with session_maker() as session:
            try:
                obj = await session.get(FsmState, str_key)
                if obj:
                    obj.state = state_str
                else:
                    obj = FsmState(key=str_key, state=state_str, data="{}")
                    session.add(obj)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Ошибка при установке FSM state для %s", str_key)
                raise

    async def get_state(self, key: StorageKey) -> str | None:
        """Возвращает текущее состояние пользователя."""
        str_key = self._make_key(key)
        session_maker = self._get_session_maker()

        async with session_maker() as session:
            obj = await session.get(FsmState, str_key)
            return obj.state if obj else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        """Перезаписывает данные FSM для ключа."""
        str_key = self._make_key(key)
        raw_data = json.dumps(dict(data), ensure_ascii=False)
        session_maker = self._get_session_maker()

        async with session_maker() as session:
            try:
                obj = await session.get(FsmState, str_key)
                if obj:
                    obj.data = raw_data
                else:
                    obj = FsmState(key=str_key, state=None, data=raw_data)
                    session.add(obj)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Ошибка при сохранении FSM data для %s", str_key)
                raise

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        """Возвращает сохранённые данные FSM."""
        str_key = self._make_key(key)
        session_maker = self._get_session_maker()

        async with session_maker() as session:
            obj = await session.get(FsmState, str_key)
            if obj and obj.data:
                try:
                    return json.loads(obj.data)
                except Exception:
                    logger.warning("Повреждённые данные JSON в FSM state для ключа %s", str_key)
                    return {}
            return {}

    async def update_data(self, key: StorageKey, data: Mapping[str, Any]) -> dict[str, Any]:
        """Обновляет и возвращает объединённые данные FSM."""
        str_key = self._make_key(key)
        session_maker = self._get_session_maker()

        async with session_maker() as session:
            try:
                obj = await session.get(FsmState, str_key)
                current_data: dict[str, Any] = {}
                if obj and obj.data:
                    try:
                        current_data = json.loads(obj.data)
                    except Exception:
                        current_data = {}
                current_data.update(data)
                raw_data = json.dumps(current_data, ensure_ascii=False)

                if obj:
                    obj.data = raw_data
                else:
                    obj = FsmState(key=str_key, state=None, data=raw_data)
                    session.add(obj)
                await session.commit()
                return current_data
            except Exception:
                await session.rollback()
                logger.exception("Ошибка при обновлении FSM data для %s", str_key)
                raise

    async def close(self) -> None:
        """Освобождает ресурсы хранилища при завершении работы."""
        pass


__all__ = ["SqliteStorage"]
