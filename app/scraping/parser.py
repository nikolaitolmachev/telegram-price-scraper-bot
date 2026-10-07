import re
from decimal import Decimal, InvalidOperation


def parse_price(value: str) -> Decimal | None:
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
