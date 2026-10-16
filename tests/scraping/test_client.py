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
    """Provide a product input for isolated scraper tests."""
    return ProductInput(
        title="Test Product",
        url="https://example.com/product",
    )


def make_scraper() -> tuple[PriceScraper, MagicMock]:
    """Create a scraper with a mocked browser and no real Playwright process."""
    scraper = PriceScraper()
    browser = MagicMock()
    scraper._browser = browser

    return scraper, browser


async def test_scrape_requires_context_manager(product: ProductInput) -> None:
    """Reject scraping before a browser has been started."""
    scraper = PriceScraper()

    with pytest.raises(RuntimeError, match="async context manager"):
        await scraper.scrape(product)


async def test_scrape_creates_and_closes_context(product: ProductInput) -> None:
    """Create a dedicated context and close it after a successful scrape."""
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
    """Close the browser context and propagate a scraping exception."""
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
    """Return results in input order even when scrapes finish out of order."""
    scraper = PriceScraper()

    products = [
        ProductInput(title=f"Product {i}", url=f"https://example.com/{i}")
        for i in range(3)
    ]

    async def fake_scrape(product: ProductInput) -> PriceResult:
        """Delay the first product so it finishes after the others."""
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
    """Keep concurrent scrapes within MAX_CONCURRENCY."""
    scraper = PriceScraper()

    products = [
        ProductInput(title=f"Product {i}", url=f"https://example.com/{i}")
        for i in range(MAX_CONCURRENCY + 3)
    ]

    active = 0
    peak = 0

    async def fake_scrape(_product: ProductInput) -> PriceResult:
        """Track active scrapes while allowing other tasks to run."""
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
    """Return no results without starting a scrape for an empty input list."""
    scraper = PriceScraper()
    scraper.scrape = AsyncMock()

    results = await scraper.scrape_many([])

    assert results == []
    scraper.scrape.assert_not_awaited()


async def test_scraper_stops_playwright_on_launch_error() -> None:
    """Stop the started Playwright service when Chromium cannot launch."""
    scraper = PriceScraper()
    playwright = MagicMock()
    playwright.chromium.launch = AsyncMock(side_effect=RuntimeError("Launch failed"))
    playwright.stop = AsyncMock()

    with patch("app.scraping.client.async_playwright") as mock_playwright:
        mock_playwright.return_value.start = AsyncMock(return_value=playwright)

        with pytest.raises(RuntimeError, match="Launch failed"):
            async with scraper:
                pytest.fail("The context body must not run after a launch error.")

    playwright.stop.assert_awaited_once()


async def test_scraper_stops_playwright_on_browser_close_error() -> None:
    """Stop Playwright even when closing the browser raises an exception."""
    scraper = PriceScraper()
    playwright = MagicMock()
    browser = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    playwright.stop = AsyncMock()
    browser.close = AsyncMock(side_effect=RuntimeError("Close failed"))

    with patch("app.scraping.client.async_playwright") as mock_playwright:
        mock_playwright.return_value.start = AsyncMock(return_value=playwright)

        with pytest.raises(RuntimeError, match="Close failed"):
            async with scraper:
                pass

    browser.close.assert_awaited_once()
    playwright.stop.assert_awaited_once()


async def test_scraper_closes_browser_and_stops_playwright() -> None:
    """Release both browser and Playwright after normal context manager use."""
    scraper = PriceScraper()
    playwright = MagicMock()
    browser = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    playwright.stop = AsyncMock()
    browser.close = AsyncMock()

    with patch("app.scraping.client.async_playwright") as mock_playwright:
        mock_playwright.return_value.start = AsyncMock(return_value=playwright)

        async with scraper as active_scraper:
            assert active_scraper is scraper

    browser.close.assert_awaited_once()
    playwright.stop.assert_awaited_once()


async def test_scrape_closes_context_on_page_creation_error(product: ProductInput) -> None:
    """Close the created browser context when opening its page fails."""
    scraper, browser = make_scraper()
    context = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    context.new_page = AsyncMock(side_effect=RuntimeError("Page creation failed"))
    context.close = AsyncMock()

    with pytest.raises(RuntimeError, match="Page creation failed"):
        await scraper.scrape(product)

    context.close.assert_awaited_once()
