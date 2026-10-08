"""Test page scraper navigation, source priority and selector fallback."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.models import ProductInput
from app.scraping.models import PriceSource, ScrapeStatus
from app.scraping.scraper import (
    _normalize_selector,        # noqa
    extract_price_from_page,
    scrape_product,
)


def make_page(
    html: str = "",
    *,
    status: int = 200,
) -> MagicMock:
    page = MagicMock()
    page.goto = AsyncMock()
    page.goto.return_value.status = status
    page.content = AsyncMock(return_value=html)

    return page


@pytest.fixture
def product() -> ProductInput:
    return ProductInput(
        title="Test Product",
        url="https://example.com/product",
    )


async def test_json_ld_takes_priority_over_microdata() -> None:
    html = """
    <script type="application/ld+json">
    {
        "@type": "Product",
        "offers": {"price": "100", "priceCurrency": "RUB"}
    }
    </script>
    <meta itemprop="price" content="200">
    """

    result = await extract_price_from_page(make_page(html))

    assert result.status is ScrapeStatus.SUCCESS
    assert result.price == Decimal("100")
    assert result.currency == "RUB"
    assert result.source is PriceSource.JSON_LD


async def test_microdata_used_when_json_ld_is_missing() -> None:
    html = """
    <meta itemprop="price" content="200">
    <meta itemprop="priceCurrency" content="RUB">
    """

    result = await extract_price_from_page(make_page(html))

    assert result.status is ScrapeStatus.SUCCESS
    assert result.price == Decimal("200")
    assert result.currency == "RUB"
    assert result.source is PriceSource.MICRODATA


async def test_selector_used_as_fallback() -> None:
    page = make_page("<div class='price'>300 ₽</div>")

    locator = MagicMock()
    locator.inner_text = AsyncMock(return_value="300 ₽")
    page.locator.return_value.first = locator

    result = await extract_price_from_page(page, selector=".price")

    assert result.status is ScrapeStatus.SUCCESS
    assert result.price == Decimal("300")
    assert result.source is PriceSource.SELECTOR
    page.locator.assert_called_once_with(".price")


async def test_selector_not_used_when_json_ld_exists() -> None:
    html = """
    <script type="application/ld+json">
    {"@type": "Product", "offers": {"price": "150"}}
    </script>
    """

    page = make_page(html)

    result = await extract_price_from_page(
        page,
        selector=".price",
    )

    assert result.source is PriceSource.JSON_LD
    page.locator.assert_not_called()


async def test_price_not_found() -> None:
    result = await extract_price_from_page(
        make_page("<html></html>")
    )

    assert result.status is ScrapeStatus.NOT_FOUND
    assert result.price is None


async def test_selector_failure_returns_not_found() -> None:
    page = make_page("<html></html>")

    locator = MagicMock()
    locator.inner_text = AsyncMock(side_effect=RuntimeError("Element not found"))
    page.locator.return_value.first = locator

    result = await extract_price_from_page(page, selector=".missing")

    assert result.status is ScrapeStatus.NOT_FOUND


@pytest.mark.parametrize(
    "selector, expected",
    [
        (".price", ".price"),
        ("css=.price", "css=.price"),
        ("//span[@class='price']", "xpath=//span[@class='price']"),
        ("xpath=//span", "xpath=//span"),
    ],
)
def test_normalize_selector(selector: str, expected: str) -> None:
    assert _normalize_selector(selector) == expected


@pytest.mark.parametrize("status", [401, 403, 429, 503])
async def test_blocked_http_status(product: ProductInput, status: int) -> None:
    page = make_page(status=status)

    result = await scrape_product(page, product)

    assert result.status is ScrapeStatus.BLOCKED
    assert result.error == f"HTTP {status}"
    page.content.assert_not_awaited()


async def test_http_error(product: ProductInput) -> None:
    page = make_page(status=404)

    result = await scrape_product(page, product)

    assert result.status is ScrapeStatus.ERROR
    assert result.error == "HTTP 404"


async def test_navigation_timeout(product: ProductInput) -> None:
    page = make_page()
    page.goto.side_effect = PlaywrightTimeoutError("Navigation timed out")

    result = await scrape_product(page, product)

    assert result.status is ScrapeStatus.TIMEOUT
    assert result.error == "Navigation timeout"


async def test_navigation_error(product: ProductInput) -> None:
    page = make_page()
    page.goto.side_effect = RuntimeError("Connection failed")

    result = await scrape_product(page, product)

    assert result.status is ScrapeStatus.ERROR
    assert result.error == "Connection failed"
