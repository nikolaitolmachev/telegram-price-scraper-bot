from decimal import Decimal
from unittest.mock import patch

import pytest

from app.database import service
from app.database.connection import get_connection, init_database
from app.models import ProductInput
from app.scraping.models import PriceResult, PriceSource, ScrapeStatus


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_prices.db"
    init_database(db_path)

    original_get_connection = get_connection

    def test_connection():
        return original_get_connection(db_path)

    monkeypatch.setattr(service, "get_connection", test_connection)
    monkeypatch.setattr(service, "init_database", lambda: init_database(db_path))

    return db_path


@pytest.fixture
def sample_results():
    return [
        (
            ProductInput(
                title="Test Product",
                url="https://example.com/product",
            ),
            PriceResult(
                status=ScrapeStatus.SUCCESS,
                price=Decimal("965.33"),
                currency="RUB",
                source=PriceSource.JSON_LD,
            ),
        ),
    ]


@pytest.mark.asyncio
async def test_create_run(test_db) -> None:
    run_id = await service.create_run(telegram_user_id=123)

    with get_connection(test_db) as connection:
        row = connection.execute(
            "SELECT telegram_user_id, status FROM scrape_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

    assert run_id > 0
    assert row["telegram_user_id"] == 123
    assert row["status"] == "running"


@pytest.mark.asyncio
async def test_complete_run(test_db, sample_results) -> None:
    run_id = await service.create_run(telegram_user_id=123)

    await service.complete_run(run_id, sample_results)

    with get_connection(test_db) as connection:
        run = connection.execute(
            "SELECT status, finished_at FROM scrape_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

        results = connection.execute(
            "SELECT price, status FROM price_results WHERE run_id = ?",
            (run_id,),
        ).fetchall()

    assert run["status"] == "completed"
    assert run["finished_at"] is not None
    assert len(results) == 1
    assert results[0]["price"] == "965.33"
    assert results[0]["status"] == "success"


@pytest.mark.asyncio
async def test_fail_run(test_db) -> None:
    run_id = await service.create_run(telegram_user_id=123)

    await service.fail_run(run_id)

    with get_connection(test_db) as connection:
        row = connection.execute(
            "SELECT status, finished_at FROM scrape_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

    assert row["status"] == "failed"
    assert row["finished_at"] is not None


@pytest.mark.asyncio
async def test_complete_run_rolls_back_on_error(test_db, sample_results) -> None:
    run_id = await service.create_run(telegram_user_id=123)

    with patch.object(
        service,
        "finish_scrape_run",
        side_effect=RuntimeError("Database update failed"),
    ):
        with pytest.raises(RuntimeError, match="Database update failed"):
            await service.complete_run(run_id, sample_results)

    with get_connection(test_db) as connection:
        run = connection.execute(
            "SELECT status FROM scrape_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

        count = connection.execute(
            "SELECT COUNT(*) FROM price_results WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]

    assert run["status"] == "running"
    assert count == 0
