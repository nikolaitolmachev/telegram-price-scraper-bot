"""Normalization of human-readable price strings into decimals."""

import re
from decimal import Decimal, InvalidOperation


def parse_price(value: str) -> Decimal | None:
    """Parse a human-readable price string into a Decimal.

    Currency symbols and whitespace are stripped, and common decimal and
    thousands separators are normalized.

    Returns:
        The parsed price, or None when the input is empty, invalid or not
        greater than zero.
    """
    if not value:
        return None

    cleaned = re.sub(r"[^\d,.\s]", "", value).strip()

    if not cleaned:
        return None

    cleaned = cleaned.replace("\xa0", " ").replace(" ", "")

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            cleaned = "".join(parts)

    try:
        price = Decimal(cleaned)
    except InvalidOperation:
        return None

    return price if price > 0 else None
