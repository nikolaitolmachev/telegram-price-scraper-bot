from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProductInput:
    title: str
    url: str
    selector: str | None = None
