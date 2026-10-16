"""Playwright lifecycle management and concurrent product scraping."""

import asyncio
from types import TracebackType

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
    """Own a Playwright browser and scrape products concurrently.

    Must be used as an async context manager: entering the context starts
    Playwright and launches Chromium, and exiting releases both. Each
    product is scraped in its own isolated browser context.
    """

    def __init__(self, *, headless: bool = True) -> None:
        """Store the browser launch option without starting Playwright."""
        self.headless = headless

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "PriceScraper":
        """Start Playwright and Chromium, stopping Playwright if launch fails."""
        self._playwright = await async_playwright().start()

        try:
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
        except BaseException:
            await self._playwright.stop()
            raise

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the browser and stop Playwright even if browser cleanup fails."""
        try:
            if self._browser is not None:
                await self._browser.close()
        finally:
            if self._playwright is not None:
                await self._playwright.stop()

    async def scrape(self, product: ProductInput) -> PriceResult:
        """Scrape a single product in a dedicated browser context.

        The context is closed after each call, including when page creation
        or scraping fails.

        Raises:
            RuntimeError: If the scraper was not entered as an async
                context manager.
        """
        if self._browser is None:
            raise RuntimeError("PriceScraper must be used as an async context manager.")

        context = await self._browser.new_context()

        try:
            page = await context.new_page()
            return await scrape_product(page, product)
        finally:
            await context.close()

    async def scrape_many(
        self,
        products: list[ProductInput],
    ) -> list[tuple[ProductInput, PriceResult]]:
        """Scrape many products concurrently, preserving input order.

        At most MAX_CONCURRENCY scrapes run at once, and results follow the
        order of the input products regardless of completion time. Unexpected
        exceptions from an individual scrape propagate to the caller.

        Returns:
            Product inputs paired with their results, or an empty list when
            no products were supplied.
        """
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def scrape_one(product: ProductInput) -> tuple[ProductInput, PriceResult]:
            """Scrape one product while holding a slot in the concurrency limit."""
            async with semaphore:
                result = await self.scrape(product)
                return product, result

        results = await asyncio.gather(
            *(scrape_one(product) for product in products)
        )

        return list(results)
