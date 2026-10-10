"""Сервис ценообразования и расчёта скидок Fishl Shop."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Sequence

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Универсальное чтение поля из словаря, sqlite3.Row или ORM-модели SQLAlchemy."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    if hasattr(obj, key):
        val = getattr(obj, key)
        return val if val is not None else default
    if hasattr(obj, "__getitem__"):
        try:
            return obj[key]
        except (KeyError, TypeError, IndexError):
            pass
    return default


def format_price(value: float | int | str) -> str:
    """Форматирует число цены: целые без нулей после запятой, дробные компактно."""
    val = float(value)
    if val.is_integer():
        return str(int(val))
    return f"{val:.2f}".rstrip("0").rstrip(".")


def region_tp_price(base_price: float | int, quantity: int) -> int:
    """Расчёт стоимости зачистки региона пропорционально выбранному количеству ТП."""
    return round(float(base_price) * quantity / 100)


def discount_kind_label(row: Any) -> str:
    """Текстовая метка типа скидки."""
    if _get(row, "kind") == "threshold":
        return f"На заказ от {format_price(_get(row, 'threshold', 0))} ₽"
    return f"На услугу: {_get(row, 'service', '')}"


def discount_value_label(row: Any) -> str:
    """Текстовая метка размера скидки (% или ₽)."""
    value_type = _get(row, "value_type", "%")
    suffix = "%" if value_type == "%" else " ₽"
    return f"{format_price(_get(row, 'percent', 0))}{suffix}"


def discount_period_label(row: Any) -> str:
    """Текстовая метка срока действия скидки."""
    expires_at = _get(row, "expires_at")
    return "без срока" if not expires_at else f"до {expires_at}"


def discount_description(rows: Iterable[Any]) -> str:
    """Строковое описание списка скидок для менеджера."""
    return "\n".join(
        f"#{_get(row, 'id')} — {discount_kind_label(row)} — *{discount_value_label(row)}* — {discount_period_label(row)}"
        for row in rows
    )


def calculate_discount(
    base_price: float | int,
    discounts: Sequence[Any],
    mode: str = "sequential",
) -> tuple[float, float]:
    """Вычисляет итоговую цену со скидкой и размер скидки.

    Сохраняет логику legacy/bot_ptb.py:
    - 'sequential': сначала применяются пороговые (threshold), затем по услугам (service).
      Для RUB вычитается фиксированная сумма, для % значение используется как доля цены,
      которую нужно оставить (например 91.67% от 24 = 22).
    - 'summed': складываются все проценты и фиксированные рубли.
    Возвращает (final_price, discount_amount).
    """
    base = float(base_price)
    if not discounts:
        return base, 0.0

    threshold = [d for d in discounts if _get(d, "kind") == "threshold"]
    service = [d for d in discounts if _get(d, "kind") == "service"]
    ordered = threshold + service

    def val_type(d: Any) -> str:
        return _get(d, "value_type", "%")

    if mode == "summed":
        percent = sum(
            min(max(float(_get(d, "percent", 0)), 0.0), 100.0)
            for d in ordered
            if val_type(d) == "%"
        )
        fixed = sum(
            max(float(_get(d, "percent", 0)), 0.0)
            for d in ordered
            if val_type(d) == "RUB"
        )
        discount_amount = min(base, base * min(percent, 100.0) / 100.0 + fixed)
        final = base - discount_amount
    else:
        final = base
        for d in ordered:
            value = max(float(_get(d, "percent", 0)), 0.0)
            if val_type(d) == "RUB":
                final -= value
            else:
                # Процентная скидка хранится как доля цены, которую нужно оставить
                final *= min(value, 100.0) / 100.0
            final = max(final, 0.0)
        discount_amount = base - final

    final = round(max(final, 0.0), 2)
    return final, round(base - final, 2)


def filter_applicable_discounts(order: Any, discounts: Sequence[Any]) -> list[Any]:
    """Фильтрует список скидок, применимых к заказу (по порогу суммы или услуге)."""
    total = float(_get(order, "price", 0))
    service = str(_get(order, "service", "") or "").strip().lower()
    result = []
    for row in discounts:
        kind = _get(row, "kind")
        if kind == "threshold" and total >= float(_get(row, "threshold", 0)):
            result.append(row)
        elif kind == "service" and service and service == str(_get(row, "service", "") or "").strip().lower():
            result.append(row)
    return result


def calculate_service_discounted_price(
    base_price: float | int,
    service: str,
    discounts: Sequence[Any],
) -> float:
    """Чистый расчёт скидочной цены для конкретной услуги по списку скидок."""
    base = float(base_price)
    service_name = str(service or "").strip().lower()
    if not service_name:
        return round(base, 2)
    service_discounts = [
        row
        for row in discounts
        if _get(row, "kind") == "service"
        and service_name == str(_get(row, "service", "") or "").strip().lower()
    ]
    if not service_discounts:
        return round(base, 2)
    final, _ = calculate_discount(base, service_discounts, mode="sequential")
    return round(final, 2)


def format_price_with_discount(base_price: float | int, final_price: float | int) -> str:
    """Форматирует строку вида '22 ₽ (было 24 ₽)' или '24 ₽'."""
    base = float(base_price)
    final = float(final_price)
    if final < base:
        return f"{format_price(final)} ₽ (было {format_price(base)} ₽)"
    return f"{format_price(base)} ₽"


def price_with_discount_text_sync(
    base_price: float | int,
    service: str,
    discounts: Sequence[Any],
) -> str:
    """Синхронная чистая версия price_with_discount_text при наличии загруженных скидок."""
    final = calculate_service_discounted_price(base_price, service, discounts)
    return format_price_with_discount(base_price, final)


# ---------------------------------------------------------
# Асинхронные функции, работающие с сессией БД
# ---------------------------------------------------------

async def get_active_discounts(session: AsyncSession) -> Sequence[Any]:
    """Возвращает актуальные активные скидки из репозитория."""
    from bot.db.repo.discounts import get_active_discounts as repo_get_active_discounts
    return await repo_get_active_discounts(session)


async def get_applicable_discounts(
    session_or_order: AsyncSession | Any,
    order_or_discounts: Any = None,
) -> list[Any]:
    """Возвращает применимые скидки к заказу.

    Поддерживает варианты вызова:
    - get_applicable_discounts(session, order) -> асинхронно читает скидки из БД
    - get_applicable_discounts(order, discounts) -> чистая фильтрация без БД
    """
    if hasattr(session_or_order, "execute"):
        session: AsyncSession = session_or_order
        order = order_or_discounts
        active = await get_active_discounts(session)
        return filter_applicable_discounts(order, active)
    # Иначе session_or_order это заказ, а order_or_discounts это список скидок
    return filter_applicable_discounts(session_or_order, order_or_discounts or [])


async def get_service_discounted_price(
    session_or_base: AsyncSession | float | int,
    base_or_service: float | int | str,
    service_or_discounts: str | Sequence[Any] | None = None,
    *,
    discounts: Sequence[Any] | None = None,
) -> float:
    """Возвращает цену услуги со скидкой.

    Может принимать:
    - (session, base_price, service) -> загружает скидки из БД
    - (base_price, service, discounts=...) -> использует переданный список скидок
    """
    if hasattr(session_or_base, "execute"):
        session: AsyncSession = session_or_base
        base_price = float(base_or_service)
        service = str(service_or_discounts or "")
        active_discounts = await get_active_discounts(session)
        return calculate_service_discounted_price(base_price, service, active_discounts)

    base_price = float(session_or_base)
    service = str(base_or_service or "")
    discs = discounts if discounts is not None else (
        service_or_discounts if isinstance(service_or_discounts, (list, tuple)) else []
    )
    return calculate_service_discounted_price(base_price, service, discs)


async def price_with_discount_text(
    session_or_base: AsyncSession | float | int,
    base_or_service: float | int | str,
    service_or_discounts: str | Sequence[Any] | None = None,
    *,
    discounts: Sequence[Any] | None = None,
) -> str:
    """Возвращает строку с ценой и зачёркнутой старой ценой (если есть скидка).

    Может принимать:
    - (session, base_price, service) -> загружает скидки из БД
    - (base_price, service, discounts=...) -> использует переданный список скидок
    """
    if hasattr(session_or_base, "execute"):
        session: AsyncSession = session_or_base
        base_price = float(base_or_service)
        service = str(service_or_discounts or "")
        final = await get_service_discounted_price(session, base_price, service)
        return format_price_with_discount(base_price, final)

    base_price = float(session_or_base)
    service = str(base_or_service or "")
    discs = discounts if discounts is not None else (
        service_or_discounts if isinstance(service_or_discounts, (list, tuple)) else []
    )
    final = calculate_service_discounted_price(base_price, service, discs)
    return format_price_with_discount(base_price, final)
