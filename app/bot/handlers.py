from pathlib import Path
from tempfile import NamedTemporaryFile

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import upload_keyboard
from app.bot.states import UploadExcel
from app.services.excel import load_products
from app.scraping.client import PriceScraper
from app.services.pricing import build_price_summaries


router = Router()


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()

    await message.answer(
        "Upload an Excel file to compare product prices across multiple stores.",
        reply_markup=upload_keyboard,
    )


@router.message(F.text == "Upload Excel")
async def upload_request_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(UploadExcel.waiting_for_file)

    await message.answer("Send an .xlsx file with the columns: title, url, selector.")


@router.message(UploadExcel.waiting_for_file, F.document)
async def excel_upload_handler(message: Message, state: FSMContext) -> None:
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
        await message.bot.download_file(
            file.file_path,
            destination=temp_path,
        )

        products = load_products(temp_path)

        await message.answer(f"File accepted. Loaded {len(products)} product rows.\nCollecting prices...")

        results = []

        async with PriceScraper(headless=True) as scraper:
            for product in products:
                result = await scraper.scrape(product)
                results.append((product, result))

        summaries = build_price_summaries(results)

        for summary in summaries:
            await message.answer(
                f"{summary.title}\n\n"
                f"Sources: {summary.sources_count}\n"
                f"Average: {summary.average_price:.2f} RUB\n"
                f"Min: {summary.min_price:.2f} RUB\n"
                f"Max: {summary.max_price:.2f} RUB"
            )

        await state.clear()

    except ValueError as exc:
        await message.answer(f"Invalid Excel file: {exc}")

    finally:
        temp_path.unlink(missing_ok=True)


@router.message(UploadExcel.waiting_for_file)
async def invalid_upload_handler(message: Message) -> None:
    await message.answer("Please send an .xlsx file.")
