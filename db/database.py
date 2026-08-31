from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_prices (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL,
 sell_price_min INTEGER, sell_price_min_date TEXT,
 buy_price_max INTEGER, buy_price_max_date TEXT,
 updated_at TEXT NOT NULL,
 UNIQUE(item_id, city, quality)
);
CREATE TABLE IF NOT EXISTS market_price_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL,
 sell_price_min INTEGER, sell_price_min_date TEXT,
 buy_price_max INTEGER, buy_price_max_date TEXT,
 recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_price_history_lookup
ON market_price_history(item_id, city, quality, recorded_at);
CREATE TABLE IF NOT EXISTS collection_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 started_at TEXT NOT NULL,
 finished_at TEXT,
 success INTEGER NOT NULL DEFAULT 0,
 records_received INTEGER NOT NULL DEFAULT 0,
 records_saved INTEGER NOT NULL DEFAULT 0,
 error TEXT,
 duration_seconds REAL
);
"""


class Database:
    def __init__(self, path: str | Path = DATABASE_PATH):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def upsert_current(self, record: dict[str, Any]):
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO market_prices(item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(item_id,city,quality) DO UPDATE SET
                sell_price_min=excluded.sell_price_min,
                sell_price_min_date=excluded.sell_price_min_date,
                buy_price_max=excluded.buy_price_max,
                buy_price_max_date=excluded.buy_price_max_date,
                updated_at=excluded.updated_at""",
                self._values(record, "updated_at"),
            )

    def insert_history(self, record: dict[str, Any]):
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO market_price_history(item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,recorded_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                self._values(record, "recorded_at"),
            )

    @staticmethod
    def _values(record: dict[str, Any], timestamp_field: str):
        return (
            record["item_id"], record["city"], record["quality"],
            record.get("sell_price_min"), record.get("sell_price_min_date"),
            record.get("buy_price_max"), record.get("buy_price_max_date"),
            record[timestamp_field],
        )

    def current_prices(self, item_id=None, city=None, quality=None):
        return self._query("market_prices", item_id, city, quality)

    def history(self, item_id=None, city=None, quality=None, start=None, end=None):
        self.initialize()
        clauses, params = [], []
        for column, value in (("item_id", item_id), ("city", city), ("quality", quality)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if start is not None:
            clauses.append("recorded_at >= ?")
            params.append(start)
        if end is not None:
            clauses.append("recorded_at <= ?")
            params.append(end)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(
                f"SELECT * FROM market_price_history{where} ORDER BY recorded_at,id", params
            )]

    def _query(self, table, item_id, city, quality):
        self.initialize()
        clauses, params = [], []
        for column, value in (("item_id", item_id), ("city", city), ("quality", quality)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(
                f"SELECT * FROM {table}{where} ORDER BY item_id,city,quality", params
            )]

    def start_collection_run(self, started_at: str) -> int:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO collection_runs(started_at) VALUES(?)", (started_at,)
            )
            return int(cursor.lastrowid)

    def finish_collection_run(self, run_id: int, *, finished_at: str, success: bool,
                              records_received: int, records_saved: int, error: str | None,
                              duration_seconds: float):
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """UPDATE collection_runs SET finished_at=?, success=?, records_received=?, records_saved=?, error=?, duration_seconds=? WHERE id=?""",
                (finished_at, int(success), records_received, records_saved, error, duration_seconds, run_id),
            )

    def latest_collection_run(self):
        self.initialize()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM collection_runs ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row) if row else None
