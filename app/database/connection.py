"""SQLite connection setup and schema initialization."""

import sqlite3
from contextlib import closing
from pathlib import Path

from app.database.models import SCHEMA


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "prices.db"


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with named rows and foreign keys enabled.

    Create the parent directory when missing. The caller is responsible for
    closing the connection; this function does not initialize the schema.

    Args:
        db_path: SQLite file path, defaulting to data/prices.db in the project.

    Returns:
        An open connection supporting row access by column name.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite schema if it does not already exist."""
    with closing(get_connection(db_path)) as connection:
        with connection:
            connection.executescript(SCHEMA)
