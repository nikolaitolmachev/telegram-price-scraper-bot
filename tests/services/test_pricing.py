from decimal import Decimal

from app.models import ProductInput
from app.scraping.models import PriceResult, ScrapeStatus
from app.services.pricing import build_price_summaries


def test_build_price_summaries() -> None:
    product_1 = ProductInput(
        title="Test Product",
        url="https://example.com/1",
    )
    product_2 = ProductInput(
        title="Test Product",
        url="https://example.com/2",
    )

    results = [
        (
            product_1,
            PriceResult(
                status=ScrapeStatus.SUCCESS,
                price=Decimal("100"),
            ),
        ),
        (
            product_2,
            PriceResult(
                status=ScrapeStatus.SUCCESS,
                price=Decimal("200"),
            ),
        ),
    ]

    summaries = build_price_summaries(results)

    assert len(summaries) == 1

    summary = summaries[0]

    assert summary.title == "Test Product"
    assert summary.sources_count == 2
    assert summary.average_price == Decimal("150")
    assert summary.min_price == Decimal("100")
    assert summary.max_price == Decimal("200")
