"""Test SQLite persistence, transactions and per-user isolation."""

import sqlite3
from decimal import Decimal

import pytest

from app.database.connection import get_connection, init_database
from app.database.repository import (
    create_scrape_run,
    finish_scrape_run,
    get_run_results,
    get_user_runs,
    save_price_results,
)
from app.models import ProductInput
from app.scraping.models import PriceResult, PriceSource, ScrapeStatus


@pytest.fixture
def connection(tmp_path):
    """Provide an initialized temporary SQLite connection and close it afterward."""
    db_path = tmp_path / "test_prices.db"
    init_database(db_path)

    conn = get_connection(db_path)

    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def sample_results():
    """Provide successful and blocked results for persistence tests."""
    return [
        (
            ProductInput(
                title="Test Product",
                url="https://example.com/1",
            ),
            PriceResult(
                status=ScrapeStatus.SUCCESS,
                price=Decimal("965.33"),
                currency="RUB",
                source=PriceSource.JSON_LD,
            ),
        ),
        (
            ProductInput(
                title="Test Product",
                url="https://example.com/2",
            ),
            PriceResult(
                status=ScrapeStatus.BLOCKED,
                error="HTTP 403",
            ),
        ),
    ]


def test_create_scrape_run(connection) -> None:
    """Store a new running scrape run with its owner and start timestamp."""
    run_id = create_scrape_run(connection, telegram_user_id=123)

    row = connection.execute(
        "SELECT * FROM scrape_runs WHERE id = ?",
        (run_id,),
    ).fetchone()

    assert run_id > 0
    assert row["telegram_user_id"] == 123
    assert row["status"] == "running"
    assert row["started_at"] is not None
    assert row["finished_at"] is None


def test_save_price_results(connection, sample_results) -> None:
    """Store successful prices and unsuccessful results with their metadata."""
    run_id = create_scrape_run(connection, telegram_user_id=123)

    save_price_results(connection, run_id, sample_results)

    rows = connection.execute(
        "SELECT * FROM price_results WHERE run_id = ? ORDER BY id",
        (run_id,),
    ).fetchall()

    assert len(rows) == 2

    assert rows[0]["title"] == "Test Product"
    assert rows[0]["url"] == "https://example.com/1"
    assert rows[0]["price"] == "965.33"
    assert rows[0]["currency"] == "RUB"
    assert rows[0]["source"] == "json_ld"
    assert rows[0]["status"] == "success"
    assert rows[0]["checked_at"] is not None

    assert rows[1]["price"] is None
    assert rows[1]["status"] == "blocked"
    assert rows[1]["error"] == "HTTP 403"


def test_finish_scrape_run(connection) -> None:
    """Mark a run completed and record its completion timestamp."""
    run_id = create_scrape_run(connection, telegram_user_id=123)

    finish_scrape_run(connection, run_id)

    row = connection.execute(
        "SELECT status, finished_at FROM scrape_runs WHERE id = ?",
        (run_id,),
    ).fetchone()

    assert row["status"] == "completed"
    assert row["finished_at"] is not None


def test_finish_scrape_run_as_failed(connection) -> None:
    """Allow a run to finish with a failed status."""
    run_id = create_scrape_run(connection, telegram_user_id=123)

    finish_scrape_run(connection, run_id, status="failed")

    row = connection.execute(
        "SELECT status FROM scrape_runs WHERE id = ?",
        (run_id,),
    ).fetchone()

    assert row["status"] == "failed"


def test_finish_scrape_run_rejects_invalid_status(connection) -> None:
    """Reject unsupported final run statuses."""
    run_id = create_scrape_run(connection, telegram_user_id=123)

    with pytest.raises(ValueError, match="Invalid scrape run status"):
        finish_scrape_run(connection, run_id, status="unknown")


def test_get_user_runs_returns_only_own_runs(connection) -> None:
    """Return only the requested user's runs in newest-first order."""
    first_run = create_scrape_run(connection, telegram_user_id=123)
    second_run = create_scrape_run(connection, telegram_user_id=123)
    create_scrape_run(connection, telegram_user_id=999)

    runs = get_user_runs(connection, telegram_user_id=123)

    assert [row["id"] for row in runs] == [second_run, first_run]


def test_get_user_runs_respects_limit(connection) -> None:
    """Limit the number of returned runs while preserving newest-first order."""
    for _ in range(5):
        create_scrape_run(connection, telegram_user_id=123)

    runs = get_user_runs(connection, telegram_user_id=123, limit=2)

    assert len(runs) == 2
    assert runs[0]["id"] > runs[1]["id"]


def test_get_run_results(connection, sample_results) -> None:
    """Read the owner's stored results with decimal amounts preserved as text."""
    run_id = create_scrape_run(connection, telegram_user_id=123)
    save_price_results(connection, run_id, sample_results)

    rows = get_run_results(connection, run_id, telegram_user_id=123)

    assert len(rows) == 2
    assert rows[0]["price"] == "965.33"
    assert Decimal(rows[0]["price"]) == Decimal("965.33")
    assert rows[1]["status"] == "blocked"


def test_get_run_results_rejects_other_user(connection, sample_results) -> None:
    """Hide results when the requested user does not own the run."""
    run_id = create_scrape_run(connection, telegram_user_id=123)
    save_price_results(connection, run_id, sample_results)

    rows = get_run_results(connection, run_id, telegram_user_id=999)

    assert rows == []


def test_foreign_key_rejects_unknown_run(connection, sample_results) -> None:
    """Reject results whose parent run does not exist."""
    with pytest.raises(sqlite3.IntegrityError):
        save_price_results(connection, run_id=999, results=sample_results)


def test_deleting_run_cascades_to_results(connection, sample_results) -> None:
    """Delete associated price results when their parent run is deleted."""
    run_id = create_scrape_run(connection, telegram_user_id=123)
    save_price_results(connection, run_id, sample_results)

    with connection:
        connection.execute(
            "DELETE FROM scrape_runs WHERE id = ?",
            (run_id,),
        )

    count = connection.execute(
        "SELECT COUNT(*) FROM price_results WHERE run_id = ?",
        (run_id,),
    ).fetchone()[0]

    assert count == 0
