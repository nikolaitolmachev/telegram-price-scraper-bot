"""Test the Excel upload workflow, user feedback and resource cleanup."""

from decimal import Decimal
from functools import partial
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message

from app.bot import handlers
from app.bot.keyboards import upload_keyboard
from app.bot.states import UploadExcel
from app.models import ProductInput
from app.scraping.models import PriceResult, ScrapeStatus


@pytest.fixture
def message() -> MagicMock:
    """Create a valid Excel upload message without contacting Telegram."""
    message = MagicMock(spec=Message)
    message.document = MagicMock(
        file_name="products.xlsx",
        file_id="test-file",
        file_size=1024,
    )
    message.from_user = MagicMock(id=123)
    message.answer = AsyncMock()
    message.bot = MagicMock()
    message.bot.get_file = AsyncMock(return_value=MagicMock(file_path="products.xlsx"))
    message.bot.download_file = AsyncMock()
    return message


@pytest.fixture
def state() -> AsyncMock:
    """Simulate transitions between waiting, processing and cleared states."""
    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = UploadExcel.waiting_for_file.state

    async def set_state(value: State) -> None:
        """Store the selected state for subsequent get_state calls."""
        state.get_state.return_value = value.state

    async def clear() -> None:
        """Make subsequent get_state calls return no active state."""
        state.get_state.return_value = None

    state.set_state.side_effect = set_state
    state.clear.side_effect = clear
    return state


@pytest.fixture(autouse=True)
def temporary_uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep uploaded temporary workbooks inside the test directory."""
    monkeypatch.setattr(
        handlers,
        "NamedTemporaryFile",
        partial(NamedTemporaryFile, dir=tmp_path),
    )


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace workbook loading, scraping and persistence with isolated mocks."""
    services = MagicMock()
    services.load_products.return_value = [
        ProductInput("Test Product", "https://example.com/1"),
        ProductInput("Test Product", "https://example.com/2"),
        ProductInput("Test Product", "https://example.com/3"),
    ]
    services.create_run = AsyncMock(return_value=7)
    services.complete_run = AsyncMock()
    services.fail_run = AsyncMock()
    services.scraper = AsyncMock()
    services.scraper_factory.return_value.__aenter__.return_value = services.scraper

    for name in ("load_products", "create_run", "complete_run", "fail_run"):
        monkeypatch.setattr(handlers, name, getattr(services, name))
    monkeypatch.setattr(handlers, "PriceScraper", services.scraper_factory)
    return services


@pytest.mark.parametrize("failed_method", ["get_file", "download_file"])
async def test_upload_failure_reports_error_and_cleans_up(
    tmp_path: Path,
    message: MagicMock,
    state: AsyncMock,
    failed_method: str,
) -> None:
    """Report retrieval or download errors and remove the temporary workbook."""
    getattr(message.bot, failed_method).side_effect = RuntimeError("Telegram unavailable")

    await handlers.excel_upload_handler(message, state)

    message.answer.assert_awaited_once_with(
        "An unexpected error occurred while processing your file.\n\nPlease try again.",
        reply_markup=upload_keyboard,
    )
    if failed_method == "get_file":
        message.bot.download_file.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []
    state.clear.assert_not_awaited()


@pytest.mark.parametrize(
    ("file_name", "file_size", "expected_message"),
    [
        ("products.csv", 1024, "Only .xlsx files are supported."),
        (None, 1024, "Please send an .xlsx file."),
        (
            "products.xlsx",
            handlers.MAX_FILE_SIZE + 1,
            "The file is too large. Maximum allowed size is 5 MB.",
        ),
    ],
)
async def test_invalid_upload_is_rejected_before_download(
    message: MagicMock,
    state: AsyncMock,
    file_name: str | None,
    file_size: int,
    expected_message: str,
) -> None:
    """Reject unsupported, unnamed or oversized uploads without downloading."""
    message.document.file_name = file_name
    message.document.file_size = file_size

    await handlers.excel_upload_handler(message, state)

    message.answer.assert_awaited_once_with(expected_message)
    message.bot.get_file.assert_not_awaited()
    message.bot.download_file.assert_not_awaited()
    state.set_state.assert_not_awaited()


@pytest.mark.parametrize("file_size", [1024, handlers.MAX_FILE_SIZE, None])
async def test_invalid_workbook_allows_another_upload(
    tmp_path: Path,
    message: MagicMock,
    state: AsyncMock,
    services: MagicMock,
    file_size: int | None,
) -> None:
    """Report invalid workbooks for allowed sizes and keep waiting for a file.

    Include files at the size limit and files whose size was not reported.
    """
    message.document.file_size = file_size
    services.load_products.side_effect = ValueError("Missing required columns: url")

    await handlers.excel_upload_handler(message, state)

    message.bot.download_file.assert_awaited_once()
    message.answer.assert_awaited_once_with(
        "Invalid Excel file: Missing required columns: url",
    )
    services.create_run.assert_not_awaited()
    services.scraper_factory.assert_not_called()
    assert await state.get_state() == UploadExcel.waiting_for_file.state
    assert list(tmp_path.iterdir()) == []


async def test_successful_upload_saves_results_and_sends_summary(
    tmp_path: Path,
    message: MagicMock,
    state: AsyncMock,
    services: MagicMock,
) -> None:
    """Persist mixed outcomes and display grouped amounts for successful prices."""
    products = services.load_products.return_value
    results = [
        (products[0], PriceResult(ScrapeStatus.SUCCESS, price=Decimal("24990"))),
        (products[1], PriceResult(ScrapeStatus.SUCCESS, price=Decimal("32840"))),
        (products[2], PriceResult(ScrapeStatus.NOT_FOUND)),
    ]
    services.scraper.scrape_many.return_value = results

    await handlers.excel_upload_handler(message, state)

    services.create_run.assert_awaited_once_with(123)
    services.scraper.scrape_many.assert_awaited_once_with(products)
    services.complete_run.assert_awaited_once_with(7, results)
    services.fail_run.assert_not_awaited()
    message.answer.assert_any_await(
        "Price collection finished.\nSuccessful: 2/3\nFailed: 1",
        reply_markup=upload_keyboard,
    )
    message.answer.assert_any_await(
        "Test Product\nSources: 2\nAverage: 28 915.00 у. е.\n"
        "Min: 24 990.00 у. е.\nMax: 32 840.00 у. е.",
    )
    state.set_state.assert_awaited_once_with(UploadExcel.processing)
    state.clear.assert_awaited_once()
    assert await state.get_state() is None
    assert list(tmp_path.iterdir()) == []


async def test_upload_without_prices_saves_results_and_reports_no_prices(
    tmp_path: Path,
    message: MagicMock,
    state: AsyncMock,
    services: MagicMock,
) -> None:
    """Keep unsuccessful results and explain when no summary can be built."""
    results = [
        (product, PriceResult(ScrapeStatus.NOT_FOUND))
        for product in services.load_products.return_value
    ]
    services.scraper.scrape_many.return_value = results

    await handlers.excel_upload_handler(message, state)

    services.complete_run.assert_awaited_once_with(7, results)
    services.fail_run.assert_not_awaited()
    message.answer.assert_any_await(
        "Price collection finished.\nSuccessful: 0/3\nFailed: 3",
        reply_markup=upload_keyboard,
    )
    message.answer.assert_any_await("No prices could be collected from the provided URLs.")
    assert await state.get_state() is None
    assert list(tmp_path.iterdir()) == []


async def test_scraping_failure_marks_run_failed_and_restores_state(
    tmp_path: Path,
    message: MagicMock,
    state: AsyncMock,
    services: MagicMock,
) -> None:
    """Mark a failed scrape run and let the user start another upload."""
    services.scraper.scrape_many.side_effect = RuntimeError("Browser unavailable")

    await handlers.excel_upload_handler(message, state)

    services.fail_run.assert_awaited_once_with(7)
    services.complete_run.assert_not_awaited()
    message.answer.assert_any_await(
        "An unexpected error occurred while processing your file.\n\nPlease try again.",
        reply_markup=upload_keyboard,
    )
    services.scraper_factory.return_value.__aexit__.assert_awaited_once()
    state.clear.assert_awaited_once()
    assert await state.get_state() is None
    assert list(tmp_path.iterdir()) == []
