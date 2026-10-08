"""Shared input models."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProductInput:
    """A single product to scrape.

    The optional selector is used only as a fallback when structured data
    does not provide a price.
    """

    title: str
    url: str
    selector: str | None = None
