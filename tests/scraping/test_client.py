"""Test browser lifecycle, context isolation and concurrency control."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import ProductInput
from app.scraping.client import MAX_CONCURRENCY, PriceScraper
from app.scraping.models import PriceResult, ScrapeStatus


@pytest.fixture
def product() -> ProductInput:
    return ProductInput(
        title="Test Product",
        url="https://example.com/product",
    )


def make_scraper() -> tuple[PriceScraper, MagicMock]:
    scraper = PriceScraper()
    browser = MagicMock()
    scraper._browser = browser

    return scraper, browser


async def test_scrape_requires_context_manager(product: ProductInput) -> None:
    scraper = PriceScraper()

    with pytest.raises(RuntimeError, match="async context manager"):
        await scraper.scrape(product)


async def test_scrape_creates_and_closes_context(product: ProductInput) -> None:
    scraper, browser = make_scraper()

    context = MagicMock()
    page = MagicMock()

    browser.new_context = AsyncMock(return_value=context)
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()

    expected = PriceResult(
        status=ScrapeStatus.SUCCESS,
        price=Decimal("100"),
    )

    with patch(
        "app.scraping.client.scrape_product",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_scrape:
        result = await scraper.scrape(product)

    assert result == expected

    browser.new_context.assert_awaited_once()
    context.new_page.assert_awaited_once()
    mock_scrape.assert_awaited_once_with(page, product)
    context.close.assert_awaited_once()


async def test_scrape_closes_context_on_error(product: ProductInput) -> None:
    scraper, browser = make_scraper()

    context = MagicMock()
    context.new_page = AsyncMock(return_value=MagicMock())
    context.close = AsyncMock()

    browser.new_context = AsyncMock(return_value=context)

    with patch(
        "app.scraping.client.scrape_product",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Scraping failed"),
    ):
        with pytest.raises(RuntimeError, match="Scraping failed"):
            await scraper.scrape(product)

    context.close.assert_awaited_once()


async def test_scrape_many_preserves_order() -> None:
    scraper = PriceScraper()

    products = [
        ProductInput(title=f"Product {i}", url=f"https://example.com/{i}")
        for i in range(3)
    ]

    async def fake_scrape(product: ProductInput) -> PriceResult:
        # First product finishes last.
        if product.title == "Product 0":
            await asyncio.sleep(0.02)

        return PriceResult(
            status=ScrapeStatus.SUCCESS,
            price=Decimal(product.title.split()[-1]) + 1,
        )

    scraper.scrape = AsyncMock(side_effect=fake_scrape)

    results = await scraper.scrape_many(products)

    assert [product for product, _ in results] == products
    assert [result.price for _, result in results] == [
        Decimal("1"),
        Decimal("2"),
        Decimal("3"),
    ]


async def test_scrape_many_respects_concurrency_limit() -> None:
    scraper = PriceScraper()

    products = [
        ProductInput(title=f"Product {i}", url=f"https://example.com/{i}")
        for i in range(MAX_CONCURRENCY + 3)
    ]

    active = 0
    peak = 0

    async def fake_scrape(_product: ProductInput) -> PriceResult:
        nonlocal active, peak

        active += 1
        peak = max(peak, active)

        try:
            await asyncio.sleep(0.02)
            return PriceResult(status=ScrapeStatus.SUCCESS)
        finally:
            active -= 1

    scraper.scrape = AsyncMock(side_effect=fake_scrape)

    results = await scraper.scrape_many(products)

    assert len(results) == len(products)
    assert peak == MAX_CONCURRENCY


async def test_scrape_many_handles_empty_list() -> None:
    scraper = PriceScraper()
    scraper.scrape = AsyncMock()

    results = await scraper.scrape_many([])

    assert results == []
    scraper.scrape.assert_not_awaited()
