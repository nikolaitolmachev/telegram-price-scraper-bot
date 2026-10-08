"""Aggregation of scraped prices per product."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.models import ProductInput
from app.scraping.models import PriceResult, ScrapeStatus


@dataclass(slots=True, frozen=True)
class PriceSummary:
    """Aggregated price statistics for one product title."""

    title: str
    sources_count: int
    average_price: Decimal
    min_price: Decimal
    max_price: Decimal


def build_price_summaries(
    results: list[tuple[ProductInput, PriceResult]],
) -> list[PriceSummary]:
    """Aggregate successful prices by product title.

    Only results with a SUCCESS status and a price contribute. Each
    summary reports the number of contributing sources and the average,
    minimum and maximum price.

    Returns:
        One summary per title that produced at least one price.
    """
    grouped: dict[str, list[Decimal]] = defaultdict(list)

    for product, result in results:
        if result.status is not ScrapeStatus.SUCCESS:
            continue

        if result.price is None:
            continue

        grouped[product.title].append(result.price)

    summaries: list[PriceSummary] = []

    for title, prices in grouped.items():
        total = sum(prices, Decimal("0"))

        summaries.append(
            PriceSummary(
                title=title,
                sources_count=len(prices),
                average_price=total / len(prices),
                min_price=min(prices),
                max_price=max(prices),
            )
        )

    return summaries
