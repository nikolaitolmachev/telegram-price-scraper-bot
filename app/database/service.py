"""Asynchronous entry points for persisting scrape runs.

Each public coroutine runs blocking SQLite work on a worker thread via
asyncio.to_thread so the event loop stays responsive.
"""

import asyncio
from contextlib import closing

from app.database.connection import get_connection, init_database
from app.database.repository import create_scrape_run, finish_scrape_run, save_price_results
from app.models import ProductInput
from app.scraping.models import PriceResult


def _create_run(telegram_user_id: int) -> int:
    """Initialize the database and insert a new scrape run."""
    init_database()

    with closing(get_connection()) as connection:
        return create_scrape_run(connection, telegram_user_id)


async def create_run(telegram_user_id: int) -> int:
    """Create a scrape run for a user on a worker thread.

    Returns:
        The id of the created run.
    """
    return await asyncio.to_thread(_create_run, telegram_user_id)


def _complete_run(
    run_id: int,
    results: list[tuple[ProductInput, PriceResult]],
) -> None:
    """Persist results and finish the run within one transaction.

    If either write raises, the transaction is rolled back and the run
    keeps its previous state.
    """
    with closing(get_connection()) as connection:
        with connection:
            save_price_results(connection, run_id, results)
            finish_scrape_run(connection, run_id)


async def complete_run(
    run_id: int,
    results: list[tuple[ProductInput, PriceResult]],
) -> None:
    """Persist the scrape results and finish the run on a worker thread."""
    await asyncio.to_thread(_complete_run, run_id, results)


def _fail_run(run_id: int) -> None:
    """Mark a scrape run as failed within a transaction."""
    with closing(get_connection()) as connection:
        with connection:
            finish_scrape_run(connection, run_id, status="failed")


async def fail_run(run_id: int) -> None:
    """Mark a scrape run as failed on a worker thread."""
    await asyncio.to_thread(_fail_run, run_id)
