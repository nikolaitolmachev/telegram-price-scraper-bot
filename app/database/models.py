SCHEMA = """
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed'))
);

CREATE TABLE IF NOT EXISTS price_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    price TEXT,
    currency TEXT,
    source TEXT,
    status TEXT NOT NULL,
    error TEXT,
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES scrape_runs(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scrape_runs_user
    ON scrape_runs(telegram_user_id);

CREATE INDEX IF NOT EXISTS idx_price_results_run
    ON price_results(run_id);
"""
