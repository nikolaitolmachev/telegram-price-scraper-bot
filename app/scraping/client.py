from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.models import ProductInput
from app.scraping.models import PriceResult
from app.scraping.scraper import scrape_product


class PriceScraper:
    def __init__(self, *, headless: bool = True) -> None:
        self.headless = headless

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> "PriceScraper":
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
        )

        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._context is not None:
            await self._context.close()

        if self._browser is not None:
            await self._browser.close()

        if self._playwright is not None:
            await self._playwright.stop()

    async def scrape(self, product: ProductInput) -> PriceResult:
        if self._page is None:
            raise RuntimeError("PriceScraper must be used as an async context manager.")

        return await scrape_product(
            self._page,
            product,
        )
