from decimal import Decimal

from app.scraping.parser import parse_price


def test_parse_price_with_currency() -> None:
    assert parse_price("82 030 ₽") == Decimal("82030")


def test_parse_price_with_comma_decimal() -> None:
    assert parse_price("965,33 ₽") == Decimal("965.33")


def test_parse_price_with_dot_thousands_separator() -> None:
    assert parse_price("82.030 ₽") == Decimal("82030")


def test_parse_price_returns_none_for_invalid_value() -> None:
    assert parse_price("Price unavailable") is None
