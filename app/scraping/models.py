"""Result types for a single product scrape."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ScrapeStatus(StrEnum):
    """Outcome of scraping one product."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    ERROR = "error"


class PriceSource(StrEnum):
    """Data source a price was extracted from."""

    JSON_LD = "json_ld"
    MICRODATA = "microdata"
    SELECTOR = "selector"


@dataclass(slots=True, frozen=True)
class PriceResult:
    """Outcome of scraping one product.

    Populated fields depend on status: successful results carry a price
    and a source, while failures typically carry an error instead.
    """

    status: ScrapeStatus
    price: Decimal | None = None
    currency: str | None = None
    source: PriceSource | None = None
    error: str | None = None
