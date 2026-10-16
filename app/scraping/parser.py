"""Validation and normalization of single positive prices into decimals."""

import re
from decimal import Decimal

CURRENCY_PATTERN = r"(?:₽|\$|€|£|RUB|USD|EUR|GBP|BYN|руб\.?|р\.?)"
NUMBER_PATTERN = (
    r"(?:"
    r"[0-9]{1,3}(?: [0-9]{3})+(?:[.,][0-9]{1,2})?"
    r"|[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?"
    r"|[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?"
    r"|[0-9]+(?:[.,][0-9]{1,2})?"
    r")"
)
PRICE_PATTERN = re.compile(
    rf"(?P<prefix>{CURRENCY_PATTERN})? *"
    rf"(?P<number>{NUMBER_PATTERN})"
    rf" *(?P<suffix>{CURRENCY_PATTERN})?",
    re.IGNORECASE,
)


def parse_price(value: str) -> Decimal | None:
    """Parse a single positive price into a Decimal.

    Accept at most one currency marker, before or after the number:
    ₽, $, €, £, RUB, USD, EUR, GBP, BYN, руб or р (with an optional period
    for the Russian abbreviations). Currency labels are case-insensitive.
    Return only the amount; the marker does not affect its value.

    Thousands must be grouped in threes using a consistent separator:
    spaces (including nonbreaking spaces), commas or dots. Decimal fractions
    may contain one or two digits. A comma or dot followed by three digits
    is accepted only as part of valid thousands grouping.

    Args:
        value: A price string, optionally surrounded by whitespace.

    Returns:
        The parsed price, or None for malformed numbers, nonpositive
        values, ranges, approximate prices or text containing multiple prices.
    """
    normalized = value.replace("\xa0", " ").replace("\u202f", " ").strip()
    match = PRICE_PATTERN.fullmatch(normalized)

    if match is None or (match["prefix"] and match["suffix"]):
        return None

    number = match["number"].replace(" ", "")

    if "," in number and "." in number:
        decimal_separator = "," if number.rfind(",") > number.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number = number.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in number or "." in number:
        separator = "," if "," in number else "."
        if len(number.rsplit(separator, 1)[1]) == 3:
            number = number.replace(separator, "")
        else:
            number = number.replace(separator, ".")

    price = Decimal(number)

    return price if price > 0 else None
