"""SQLite data access for scrape runs and their price results.

Every function operates on a caller-provided connection. Only
create_scrape_run commits on its own; the remaining writers leave
transaction control to the caller.
"""

import sqlite3
from collections.abc import Sequence

from app.models import ProductInput
from app.scraping.models import PriceResult

SCRAPE_STATUSES = {"completed", "failed"}


def create_scrape_run(connection: sqlite3.Connection, telegram_user_id: int) -> int:
    """Insert a new scrape run in the running status and commit it.

    Returns:
        The id of the created run.

    Raises:
        RuntimeError: If the generated row id is unavailable.
    """
    cursor = connection.execute(
        """
        INSERT INTO scrape_runs (telegram_user_id)
        VALUES (?)
        """,
        (telegram_user_id,),
    )
    connection.commit()

    if cursor.lastrowid is None:
        raise RuntimeError("Failed to create scrape run.")

    return cursor.lastrowid


def save_price_results(
    connection: sqlite3.Connection,
    run_id: int,
    results: Sequence[tuple[ProductInput, PriceResult]],
) -> None:
    """Insert one row per scrape result for the given run.

    Store decimal prices as text and include unsuccessful results with
    their statuses and optional errors. Leave transaction control to the
    caller; this function does not commit.
    """
    rows = [
        (
            run_id,
            product.title,
            product.url,
            str(result.price) if result.price is not None else None,
            result.currency,
            result.source.value if result.source is not None else None,
            result.status.value,
            result.error,
        )
        for product, result in results
    ]

    connection.executemany(
        """
        INSERT INTO price_results (
            run_id,
            title,
            url,
            price,
            currency,
            source,
            status,
            error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def finish_scrape_run(
    connection: sqlite3.Connection,
    run_id: int,
    *,
    status: str = "completed",
) -> None:
    """Set a run's final status and completion timestamp.

    The transaction is left open for the caller to commit.

    Raises:
        ValueError: If the status is not completed or failed.
    """
    if status not in SCRAPE_STATUSES:
        raise ValueError("Invalid scrape run status.")

    connection.execute(
        """
        UPDATE scrape_runs
        SET status = ?,
            finished_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, run_id),
    )


def get_user_runs(
    connection: sqlite3.Connection,
    telegram_user_id: int,
    *,
    limit: int = 10,
) -> list[sqlite3.Row]:
    """Return a user's most recent runs, newest first.

    Returns:
        Up to limit rows containing the id, timestamps and status.
    """
    cursor = connection.execute(
        """
        SELECT id, started_at, finished_at, status
        FROM scrape_runs
        WHERE telegram_user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (telegram_user_id, limit),
    )

    return cursor.fetchall()


def get_run_results(
    connection: sqlite3.Connection,
    run_id: int,
    telegram_user_id: int,
) -> list[sqlite3.Row]:
    """Return the price results of a run owned by the given user.

    A missing run or a run owned by another user yields no rows.

    Returns:
        The run's price result rows in insertion order.
    """
    cursor = connection.execute(
        """
        SELECT
            pr.title,
            pr.url,
            pr.price,
            pr.currency,
            pr.source,
            pr.status,
            pr.error,
            pr.checked_at
        FROM price_results AS pr
        JOIN scrape_runs AS sr ON sr.id = pr.run_id
        WHERE sr.id = ?
          AND sr.telegram_user_id = ?
        ORDER BY pr.id
        """,
        (run_id, telegram_user_id),
    )

    return cursor.fetchall()
