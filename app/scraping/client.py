import asyncio

from playwright.async_api import (
    Browser,
    Playwright,
    async_playwright,
)

from app.models import ProductInput
from app.scraping.models import PriceResult
from app.scraping.scraper import scrape_product


MAX_CONCURRENCY = 4


class PriceScraper:
    def __init__(self, *, headless: bool = True) -> None:
        self.headless = headless

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "PriceScraper":
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
        )

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._browser is not None:
            await self._browser.close()

        if self._playwright is not None:
            await self._playwright.stop()

    async def scrape(self, product: ProductInput) -> PriceResult:
        if self._browser is None:
            raise RuntimeError("PriceScraper must be used as an async context manager.")

        context = await self._browser.new_context()
        page = await context.new_page()

        try:
            return await scrape_product(
                page,
                product,
            )
        finally:
            await context.close()

    async def scrape_many(
        self,
        products: list[ProductInput],
    ) -> list[tuple[ProductInput, PriceResult]]:
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def scrape_one(product: ProductInput) -> tuple[ProductInput, PriceResult]:
            async with semaphore:
                result = await self.scrape(product)
                return product, result

        results = await asyncio.gather(
            *(scrape_one(product) for product in products)
        )

        return list(results)
