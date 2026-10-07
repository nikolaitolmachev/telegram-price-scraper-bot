from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ScrapeStatus(StrEnum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    ERROR = "error"


class PriceSource(StrEnum):
    JSON_LD = "json_ld"
    MICRODATA = "microdata"
    SELECTOR = "selector"


@dataclass(slots=True, frozen=True)
class PriceResult:
    status: ScrapeStatus
    price: Decimal | None = None
    currency: str | None = None
    source: PriceSource | None = None
    error: str | None = None
