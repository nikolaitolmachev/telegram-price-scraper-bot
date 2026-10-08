import asyncio
from contextlib import closing

from app.database.connection import get_connection, init_database
from app.database.repository import create_scrape_run, finish_scrape_run, save_price_results
from app.models import ProductInput
from app.scraping.models import PriceResult


def _create_run(telegram_user_id: int) -> int:
    init_database()

    with closing(get_connection()) as connection:
        return create_scrape_run(connection, telegram_user_id)


async def create_run(telegram_user_id: int) -> int:
    return await asyncio.to_thread(_create_run, telegram_user_id)


def _complete_run(
    run_id: int,
    results: list[tuple[ProductInput, PriceResult]],
) -> None:
    with closing(get_connection()) as connection:
        with connection:
            save_price_results(connection, run_id, results)
            finish_scrape_run(connection, run_id)


async def complete_run(
    run_id: int,
    results: list[tuple[ProductInput, PriceResult]],
) -> None:
    await asyncio.to_thread(_complete_run, run_id, results)


def _fail_run(run_id: int) -> None:
    with closing(get_connection()) as connection:
        with connection:
            finish_scrape_run(connection, run_id, status="failed")


async def fail_run(run_id: int) -> None:
    await asyncio.to_thread(_fail_run, run_id)
