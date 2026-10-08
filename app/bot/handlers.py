"""Telegram message handlers for the Excel upload and price comparison flow."""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from app.bot.keyboards import upload_keyboard
from app.bot.states import UploadExcel
from app.scraping.client import PriceScraper
from app.scraping.models import ScrapeStatus
from app.services.pricing import build_price_summaries
from app.services.excel import load_products
from app.database.service import create_run, complete_run, fail_run


logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext) -> None:
    """Handle the /start command and reset the conversation state.

    If a price collection run is already in progress, the user is asked to
    wait and the current state is left untouched.
    """
    current_state = await state.get_state()

    if current_state == UploadExcel.processing.state:
        await message.answer("Price collection is already in progress.\n\nPlease wait until it finishes.")
        return

    await state.clear()

    await message.answer(
        "Upload an Excel file to compare product prices across multiple stores.",
        reply_markup=upload_keyboard,
    )


@router.message(StateFilter(None, UploadExcel.waiting_for_file), F.text == "Upload Excel")
async def upload_request_handler(message: Message, state: FSMContext) -> None:
    """Switch to the waiting state and prompt the user for an Excel file."""
    await state.set_state(UploadExcel.waiting_for_file)

    await message.answer("Send an .xlsx file with the columns: title, url, selector.")


@router.message(UploadExcel.waiting_for_file, F.document)
async def excel_upload_handler(message: Message, state: FSMContext) -> None:
    """Process an uploaded Excel file and report collected prices.

    Validate the workbook, scrape product prices, and persist the results.
    Handle processing errors and restore the Telegram workflow state.
    """
    document = message.document

    if document is None or not document.file_name:
        await message.answer("Please send an .xlsx file.")
        return

    if not document.file_name.lower().endswith(".xlsx"):
        await message.answer("Only .xlsx files are supported.")
        return

    file = await message.bot.get_file(document.file_id)

    with NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        await message.bot.download_file(file.file_path, destination=temp_path)

        try:
            products = load_products(temp_path)
        except ValueError as exc:
            await message.answer(f"Invalid Excel file: {exc}")
            return

        telegram_user = message.from_user

        if telegram_user is None:
            raise RuntimeError("Telegram user information is unavailable.")

        await state.set_state(UploadExcel.processing)

        await message.answer(
            f"File accepted. Loaded {len(products)} product rows.\n\nCollecting prices...",
            reply_markup=ReplyKeyboardRemove(),
        )

        run_id = await create_run(telegram_user.id)

        try:
            async with PriceScraper(headless=True) as scraper:
                results = await scraper.scrape_many(products)

            await complete_run(run_id, results)

        except Exception:
            try:
                await fail_run(run_id)
            except Exception:  # noqa
                logger.exception(
                    "Failed to mark scrape run %s as failed",
                    run_id,
                )
            raise

        summaries = build_price_summaries(results)

        successful = sum(
            1
            for _, result in results
            if result.status is ScrapeStatus.SUCCESS
        )

        failed = len(results) - successful

        await message.answer(
            f"Price collection finished.\n"
            f"Successful: {successful}/{len(results)}\n"
            f"Failed: {failed}",
            reply_markup=upload_keyboard,
        )

        summary_lines = []

        for summary in summaries:
            summary_lines.append(
                f"{summary.title}\n"
                f"Sources: {summary.sources_count}\n"
                f"Average: {summary.average_price:.2f} RUB\n"
                f"Min: {summary.min_price:.2f} RUB\n"
                f"Max: {summary.max_price:.2f} RUB"
            )

        if summary_lines:
            await message.answer("\n\n".join(summary_lines))
        else:
            await message.answer("No prices could be collected from the provided URLs.")

        await state.clear()

    except Exception:  # noqa
        logger.exception("Excel processing failed")
        await message.answer(
            "An unexpected error occurred while processing your file.\n\nPlease try again.",
            reply_markup=upload_keyboard,
        )

    finally:
        temp_path.unlink(missing_ok=True)

        current_state = await state.get_state()
        if current_state == UploadExcel.processing.state:
            await state.clear()


@router.message(UploadExcel.processing)
async def processing_handler(message: Message) -> None:
    """Notify the user that a price collection run is already in progress."""
    await message.answer("Price collection is already in progress. Please wait until it finishes.")


@router.message(UploadExcel.waiting_for_file)
async def invalid_upload_handler(message: Message) -> None:
    """Ask the user for an .xlsx file when the message is not a document."""
    await message.answer("Please send an .xlsx file.")
