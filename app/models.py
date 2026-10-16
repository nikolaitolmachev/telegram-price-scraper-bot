"""Shared input models."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProductInput:
    """A product title, source URL and optional fallback selector.

    The selector may use CSS or XPath and is tried only when structured data
    does not provide a price. The title is used to group collected prices.
    """

    title: str
    url: str
    selector: str | None = None
