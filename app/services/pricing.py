"""Aggregate scraped amounts by product title without accounting for currency."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.models import ProductInput
from app.scraping.models import PriceResult, ScrapeStatus


@dataclass(slots=True, frozen=True)
class PriceSummary:
    """Price statistics for one product title, without a currency designation.

    sources_count counts contributing results, not distinct stores or URLs.
    """

    title: str
    sources_count: int
    average_price: Decimal
    min_price: Decimal
    max_price: Decimal


def build_price_summaries(
    results: list[tuple[ProductInput, PriceResult]],
) -> list[PriceSummary]:
    """Aggregate successful prices by exact product title.

    Only results with a SUCCESS status and a non-None price contribute.
    Count each contributing result, including repeated URLs, and calculate
    the average, minimum and maximum amount. Currency is ignored: callers
    must provide prices in the same currency for a meaningful comparison.

    Returns:
        One summary per title with a contributing price, in the order
        those titles first appear among contributing results.
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
