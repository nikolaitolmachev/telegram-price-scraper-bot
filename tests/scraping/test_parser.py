"""Test supported price formats and rejection of invalid or ambiguous values."""

from decimal import Decimal

import pytest

from app.scraping.parser import parse_price


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("100", "100"),
        (" 100 ₽ ", "100"),
        ("82 030 ₽", "82030"),
        ("82\xa0030 ₽", "82030"),
        ("82\u202f030 ₽", "82030"),
        ("965,33 ₽", "965.33"),
        ("965.33", "965.33"),
        ("965,3", "965.3"),
        ("0.99", "0.99"),
        ("82.030 ₽", "82030"),
        ("1,299", "1299"),
        ("1,299.99", "1299.99"),
        ("1.299,99", "1299.99"),
        ("1 299,99 руб.", "1299.99"),
        ("1 299.99 RUB", "1299.99"),
        ("1,234,567.89", "1234567.89"),
        ("1.234.567,89", "1234567.89"),
        ("1 234 567", "1234567"),
        ("1,234,567", "1234567"),
        ("1.234.567", "1234567"),
        ("$1,299.99", "1299.99"),
        ("€ 1.299,99", "1299.99"),
        ("100 usd", "100"),
        ("100 BYN", "100"),
    ],
)
def test_parse_price_with_supported_format(value: str, expected: str) -> None:
    """Preserve the amount across supported grouping and currency formats."""
    assert parse_price(value) == Decimal(expected)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "Price unavailable",
        "-100 ₽",
        "−100 ₽",
        "$-100",
        "0",
        "0,00 ₽",
        "100–200 ₽",
        "100-200 ₽",
        "100 / 200 ₽",
        "100 ₽ вместо 200 ₽",
        "100 ₽ 200 ₽",
        "от 990 ₽",
        "до 990 ₽",
        "~990 ₽",
        "100 ₽/мес.",
        "12 34 ₽",
        "1 23 456",
        "1,23,456",
        "1.23.456",
        "1,234.567,89",
        "1.234,567.89",
        "100,,00",
        "100..00",
        "1 299,999",
        "100\n200",
        "100\t200",
        "1e3",
        "NaN",
        "Infinity",
        "$100 RUB",
        "100%",
    ],
)
def test_parse_price_returns_none_for_invalid_value(value: str) -> None:
    """Reject ambiguous text and invalid amounts instead of joining digits."""
    assert parse_price(value) is None
