"""Price extraction from embedded JSON-LD and Microdata markup."""

import json
from decimal import Decimal
from typing import Any

from bs4 import BeautifulSoup

from app.scraping.parser import parse_price


def extract_microdata_price(
    html: str,
) -> tuple[Decimal | None, str | None]:
    """Extract a price and optional currency from Microdata markup.

    Read the first price item in the document, preferring its content
    attribute over its text, and pair it with the first currency item.
    The items are not restricted to the same Product or Offer container.

    Returns:
        A (price, currency) pair, or (None, None) when the first price is
        absent or invalid. Currency may be None even with a valid price.
    """
    soup = BeautifulSoup(html, "html.parser")

    price_element = soup.select_one('[itemprop="price"]')

    if price_element is None:
        return None, None

    raw_price = price_element.get("content")

    if raw_price is None:
        raw_price = price_element.get_text(strip=True)

    price = parse_price(str(raw_price))

    if price is None:
        return None, None

    currency_element = soup.select_one('[itemprop="priceCurrency"]')

    currency = None
    if currency_element is not None:
        currency = currency_element.get("content") or currency_element.get_text(strip=True) or None

    return price, currency


def extract_json_ld_price(
    html: str,
) -> tuple[Decimal | None, str | None]:
    """Extract the first valid price from JSON-LD Product markup.

    Inspect application/ld+json scripts in document order, skipping empty
    scripts and invalid JSON. Search nested Product nodes for offer prices.

    Returns:
        A (price, currency) pair, or (None, None) when no valid product
        price is found. Currency may be None even with a valid price.
    """
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue

        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue

        result = _find_product_price(data)
        if result is not None:
            return result

    return None, None


def _find_product_price(
    data: Any,
) -> tuple[Decimal, str | None] | None:
    """Search parsed JSON-LD data for the first Product price.

    Traverses lists and nested dictionaries, recognizing a Product node by
    its @type.

    Returns:
        A (price, currency) pair, or None when no product price is found.
    """
    if isinstance(data, list):
        for item in data:
            result = _find_product_price(item)
            if result is not None:
                return result

        return None

    if not isinstance(data, dict):
        return None

    node_type = data.get("@type")

    if isinstance(node_type, str):
        is_product = node_type == "Product"
    elif isinstance(node_type, list):
        is_product = "Product" in node_type
    else:
        is_product = False

    if is_product:
        result = _extract_offer_price(data.get("offers"))

        if result is not None:
            return result

    for value in data.values():
        if isinstance(value, (dict, list)):
            result = _find_product_price(value)

            if result is not None:
                return result

    return None


def _extract_offer_price(
    offers: Any,
) -> tuple[Decimal, str | None] | None:
    """Read the first valid price and optional currency from offers.

    Accept a single offer dictionary or a list. Use price when truthy,
    otherwise lowPrice; a present but unparseable price does not trigger
    a second attempt using lowPrice. Validate amounts with parse_price.

    Returns:
        A (price, currency) pair, or None when no valid price is found.
    """
    if isinstance(offers, list):
        for offer in offers:
            result = _extract_offer_price(offer)

            if result is not None:
                return result

        return None

    if not isinstance(offers, dict):
        return None

    raw_price = offers.get("price") or offers.get("lowPrice")

    if raw_price is None:
        return None

    price = parse_price(str(raw_price))

    if price is None:
        return None

    currency = offers.get("priceCurrency")

    return price, currency
