"""Тесты для сервиса ценообразования (bot/services/pricing.py)."""
from dataclasses import dataclass
from typing import Optional
import pytest

from bot.services.pricing import (
    calculate_discount,
    calculate_service_discounted_price,
    discount_description,
    discount_kind_label,
    discount_period_label,
    discount_value_label,
    filter_applicable_discounts,
    format_price,
    format_price_with_discount,
    region_tp_price,
)


@dataclass
class DummyDiscount:
    id: int
    kind: str
    threshold: float = 0.0
    service: str = ""
    percent: float = 0.0
    value_type: str = "%"
    active: int = 1
    created_at: str = "2026-10-06 12:00:00"
    expires_at: Optional[str] = None


class TestFormatPrice:
    def test_integers(self):
        assert format_price(0) == "0"
        assert format_price(150) == "150"
        assert format_price(2400) == "2400"
        assert format_price(-10) == "-10"

    def test_floats_with_zero_fraction(self):
        assert format_price(150.0) == "150"
        assert format_price(24.00) == "24"
        assert format_price(0.0) == "0"

    def test_floats_with_fraction(self):
        assert format_price(1.5) == "1.5"
        assert format_price(1.50) == "1.5"
        assert format_price(1.25) == "1.25"
        assert format_price(91.67) == "91.67"

    def test_strings(self):
        assert format_price("24") == "24"
        assert format_price("1.50") == "1.5"


class TestRegionTpPrice:
    def test_proportional_pricing(self):
        assert region_tp_price(1000, 100) == 1000
        assert region_tp_price(1000, 50) == 500
        assert region_tp_price(1000, 10) == 100
        assert region_tp_price(1000, 5) == 50
        assert region_tp_price(1000, 1) == 10

    def test_rounding(self):
        # 1500 * 5 / 100 = 75
        assert region_tp_price(1500, 5) == 75
        # 1600 * 20 / 100 = 320
        assert region_tp_price(1600, 20) == 320
        # 2500 * 1 / 100 = 25
        assert region_tp_price(2500, 1) == 25


class TestCalculateDiscount:
    def test_no_discounts(self):
        final, amount = calculate_discount(1000, [])
        assert final == 1000.0
        assert amount == 0.0

    def test_sequential_single_percent(self):
        # В sequential процент — это доля оставшейся цены (91.67% от 24 ₽ = 22 ₽)
        discounts = [{"kind": "service", "service": "Крутки", "percent": 91.67, "value_type": "%"}]
        final, amount = calculate_discount(24, discounts, mode="sequential")
        assert final == 22.0
        assert amount == 2.0

    def test_sequential_single_rub(self):
        discounts = [{"kind": "service", "service": "Театр", "percent": 50, "value_type": "RUB"}]
        final, amount = calculate_discount(350, discounts, mode="sequential")
        assert final == 300.0
        assert amount == 50.0

    def test_sequential_ordering_threshold_then_service(self):
        # Порядок в списке обратный, но внутри threshold должен примениться первым
        d_service = {"kind": "service", "service": "Зачистка", "percent": 50, "value_type": "RUB"}
        d_thresh = {"kind": "threshold", "threshold": 1000, "percent": 100, "value_type": "RUB"}
        final, amount = calculate_discount(2000, [d_service, d_thresh], mode="sequential")
        # 2000 - 100 - 50 = 1850
        assert final == 1850.0
        assert amount == 150.0

    def test_sequential_percent_and_rub(self):
        # 1000 * 0.9 = 900; 900 - 100 = 800
        d_thresh = {"kind": "threshold", "threshold": 500, "percent": 90.0, "value_type": "%"}
        d_service = {"kind": "service", "service": "Зачистка", "percent": 100.0, "value_type": "RUB"}
        final, amount = calculate_discount(1000, [d_thresh, d_service], mode="sequential")
        assert final == 800.0
        assert amount == 200.0

    def test_summed_percentages(self):
        # В summed проценты складываются как скидка: 10% + 5% = 15% скидки
        d1 = {"kind": "threshold", "threshold": 500, "percent": 10, "value_type": "%"}
        d2 = {"kind": "service", "service": "Крутки", "percent": 5, "value_type": "%"}
        final, amount = calculate_discount(1000, [d1, d2], mode="summed")
        assert final == 850.0
        assert amount == 150.0

    def test_summed_percent_and_rub(self):
        # 10% (100 ₽) + 50 ₽ = 150 ₽ скидки
        d1 = {"kind": "threshold", "threshold": 500, "percent": 10, "value_type": "%"}
        d2 = {"kind": "service", "service": "Крутки", "percent": 50, "value_type": "RUB"}
        final, amount = calculate_discount(1000, [d1, d2], mode="summed")
        assert final == 850.0
        assert amount == 150.0

    def test_summed_exceeding_base(self):
        d1 = {"kind": "threshold", "threshold": 100, "percent": 500, "value_type": "RUB"}
        final, amount = calculate_discount(200, [d1], mode="summed")
        assert final == 0.0
        assert amount == 200.0

    def test_with_orm_like_objects(self):
        d1 = DummyDiscount(id=1, kind="threshold", threshold=500, percent=10, value_type="%")
        d2 = DummyDiscount(id=2, kind="service", service="Крутки", percent=50, value_type="RUB")
        final, amount = calculate_discount(1000, [d1, d2], mode="summed")
        assert final == 850.0
        assert amount == 150.0


class TestDiscountLabelsAndFiltering:
    def test_labels(self):
        row_thresh = {"kind": "threshold", "threshold": 1500, "percent": 10, "value_type": "%", "expires_at": None}
        assert discount_kind_label(row_thresh) == "На заказ от 1500 ₽"
        assert discount_value_label(row_thresh) == "10%"
        assert discount_period_label(row_thresh) == "без срока"

        row_serv = DummyDiscount(id=5, kind="service", service="Крутки", percent=100, value_type="RUB", expires_at="2026-12-31 23:59")
        assert discount_kind_label(row_serv) == "На услугу: Крутки"
        assert discount_value_label(row_serv) == "100 ₽"
        assert discount_period_label(row_serv) == "до 2026-12-31 23:59"

    def test_discount_description(self):
        rows = [
            {"id": 1, "kind": "threshold", "threshold": 1000, "percent": 10, "value_type": "%", "expires_at": None},
        ]
        desc = discount_description(rows)
        assert "#1 — На заказ от 1000 ₽ — *10%* — без срока" == desc

    def test_filter_applicable_discounts(self):
        d1 = {"kind": "threshold", "threshold": 1000, "percent": 10}
        d2 = {"kind": "threshold", "threshold": 2000, "percent": 15}
        d3 = {"kind": "service", "service": "Крутки", "percent": 5}
        d4 = {"kind": "service", "service": "Окулы", "percent": 5}

        order = {"price": 1500, "service": "крутки"}
        matched = filter_applicable_discounts(order, [d1, d2, d3, d4])
        assert matched == [d1, d3]

    def test_format_price_with_discount(self):
        assert format_price_with_discount(24, 22) == "22 ₽ (было 24 ₽)"
        assert format_price_with_discount(24, 24) == "24 ₽"
