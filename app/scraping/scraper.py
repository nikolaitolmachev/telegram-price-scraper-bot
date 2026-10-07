from decimal import Decimal

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.models import ProductInput
from app.scraping.extractors import (
    extract_json_ld_price,
    extract_microdata_price,
)
from app.scraping.models import PriceResult, PriceSource, ScrapeStatus
from app.scraping.parser import parse_price


async def scrape_product(page: Page, product: ProductInput) -> PriceResult:
    try:
        response = await page.goto(
            product.url,
            wait_until="domcontentloaded",
            timeout=30_000,
        )
    except PlaywrightTimeoutError:
        return PriceResult(
            status=ScrapeStatus.TIMEOUT,
            error="Navigation timeout",
        )
    except Exception as exc:
        return PriceResult(
            status=ScrapeStatus.ERROR,
            error=str(exc),
        )

    if response is not None and response.status in {401, 403, 429, 503}:
        return PriceResult(
            status=ScrapeStatus.BLOCKED,
            error=f"HTTP {response.status}",
        )

    if response is not None and response.status >= 400:
        return PriceResult(
            status=ScrapeStatus.ERROR,
            error=f"HTTP {response.status}",
        )

    return await extract_price_from_page(
        page,
        selector=product.selector,
    )


async def extract_price_from_page(page: Page, selector: str | None = None) -> PriceResult:
    html = await page.content()

    price, currency = extract_json_ld_price(html)

    if price is not None:
        return PriceResult(
            status=ScrapeStatus.SUCCESS,
            price=price,
            currency=currency,
            source=PriceSource.JSON_LD,
        )

    price, currency = extract_microdata_price(html)

    if price is not None:
        return PriceResult(
            status=ScrapeStatus.SUCCESS,
            price=price,
            currency=currency,
            source=PriceSource.MICRODATA,
        )

    if selector:
        selector_price = await _extract_price_by_selector(page, selector)

        if selector_price is not None:
            return PriceResult(
                status=ScrapeStatus.SUCCESS,
                price=selector_price,
                source=PriceSource.SELECTOR,
            )

    return PriceResult(status=ScrapeStatus.NOT_FOUND)


async def _extract_price_by_selector(page: Page, selector: str) -> Decimal | None:
    normalized_selector = _normalize_selector(selector)

    locator = page.locator(normalized_selector).first

    try:
        text = await locator.inner_text()
    except Exception:  # noqa
        return None

    return parse_price(text)


def _normalize_selector(selector: str) -> str:
    selector = selector.strip()

    if selector.startswith(("css=", "xpath=")):
        return selector

    if selector.startswith(("//", "/", "(")):
        return f"xpath={selector}"

    return selector
