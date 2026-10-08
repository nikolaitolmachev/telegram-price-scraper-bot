import sqlite3
from collections.abc import Sequence

from app.models import ProductInput
from app.scraping.models import PriceResult


SCRAPE_STATUSES = {"completed", "failed"}


def create_scrape_run(connection: sqlite3.Connection, telegram_user_id: int) -> int:
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
