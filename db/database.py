from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from config import ALBION_SERVER, DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_prices (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 server TEXT NOT NULL DEFAULT 'east',
 item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL,
 sell_price_min INTEGER, sell_price_min_date TEXT,
 buy_price_max INTEGER, buy_price_max_date TEXT,
 updated_at TEXT NOT NULL,
 UNIQUE(server, item_id, city, quality)
);
CREATE TABLE IF NOT EXISTS market_price_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 server TEXT NOT NULL DEFAULT 'east',
 item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL,
 sell_price_min INTEGER, sell_price_min_date TEXT,
buy_price_max INTEGER, buy_price_max_date TEXT,
 recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_price_history_lookup
ON market_price_history(server, item_id, city, quality, recorded_at);
CREATE TABLE IF NOT EXISTS market_liquidity_orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source TEXT NOT NULL,
 server TEXT NOT NULL,
 order_id TEXT,
 item_id TEXT NOT NULL,
 city TEXT NOT NULL,
 quality INTEGER NOT NULL,
 side TEXT NOT NULL,
 price REAL NOT NULL,
 quantity REAL NOT NULL,
 expires_at TEXT,
 observed_at TEXT NOT NULL,
 source_timestamp TEXT,
 first_seen TEXT,
 last_seen TEXT,
 status TEXT NOT NULL DEFAULT 'ACTIVE',
 UNIQUE(source, server, order_id)
);
CREATE INDEX IF NOT EXISTS idx_market_liquidity_lookup
ON market_liquidity_orders(server, item_id, city, quality, side, status, last_seen, expires_at, price);
CREATE TABLE IF NOT EXISTS market_liquidity_order_observations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source TEXT NOT NULL,
 server TEXT NOT NULL,
 order_id TEXT,
 item_id TEXT NOT NULL,
 city TEXT NOT NULL,
 quality INTEGER NOT NULL,
 side TEXT NOT NULL,
 price REAL NOT NULL,
 quantity REAL NOT NULL,
 expires_at TEXT,
 observed_at TEXT NOT NULL,
 source_timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_liquidity_observations_lookup
ON market_liquidity_order_observations(server, item_id, city, quality, side, observed_at);
CREATE TABLE IF NOT EXISTS collection_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 server TEXT NOT NULL DEFAULT 'east',
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
            self._migrate(connection)
            connection.executescript(SCHEMA)

    @staticmethod
    def _columns(connection, table: str) -> set[str]:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}

    def _migrate(self, connection):
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "market_prices" in tables and "server" not in self._columns(connection, "market_prices"):
            connection.execute("ALTER TABLE market_prices RENAME TO market_prices_legacy")
            connection.executescript("""
                CREATE TABLE market_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server TEXT NOT NULL DEFAULT 'east',
                    item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL,
                    sell_price_min INTEGER, sell_price_min_date TEXT,
                    buy_price_max INTEGER, buy_price_max_date TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(server, item_id, city, quality)
                );
            """)
            connection.execute("""INSERT INTO market_prices
                (id,server,item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,updated_at)
                SELECT id, ?, item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,updated_at
                FROM market_prices_legacy""", (ALBION_SERVER,))
            connection.execute("DROP TABLE market_prices_legacy")
        if "market_price_history" in tables and "server" not in self._columns(connection, "market_price_history"):
            connection.execute(f"ALTER TABLE market_price_history ADD COLUMN server TEXT NOT NULL DEFAULT '{ALBION_SERVER}'")
        if "collection_runs" in tables and "server" not in self._columns(connection, "collection_runs"):
            connection.execute(f"ALTER TABLE collection_runs ADD COLUMN server TEXT NOT NULL DEFAULT '{ALBION_SERVER}'")
        if "market_price_history" in tables:
            connection.execute("DROP INDEX IF EXISTS idx_market_price_history_lookup")
            connection.execute("CREATE INDEX idx_market_price_history_lookup ON market_price_history(server, item_id, city, quality, recorded_at)")
        if "market_liquidity_orders" in tables:
            columns = self._columns(connection, "market_liquidity_orders")
            if "first_seen" not in columns:
                connection.execute("ALTER TABLE market_liquidity_orders ADD COLUMN first_seen TEXT")
            if "last_seen" not in columns:
                connection.execute("ALTER TABLE market_liquidity_orders ADD COLUMN last_seen TEXT")
            if "status" not in columns:
                connection.execute("ALTER TABLE market_liquidity_orders ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'")
            connection.execute("UPDATE market_liquidity_orders SET first_seen=COALESCE(first_seen, observed_at), last_seen=COALESCE(last_seen, observed_at), status=COALESCE(status, 'ACTIVE')")
            connection.execute("DROP INDEX IF EXISTS idx_market_liquidity_lookup")
            connection.execute("CREATE INDEX idx_market_liquidity_lookup ON market_liquidity_orders(server, item_id, city, quality, side, status, last_seen, expires_at, price)")
        connection.execute("""CREATE TABLE IF NOT EXISTS market_liquidity_order_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, server TEXT NOT NULL, order_id TEXT,
            item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL, side TEXT NOT NULL,
            price REAL NOT NULL, quantity REAL NOT NULL, expires_at TEXT, observed_at TEXT NOT NULL, source_timestamp TEXT
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_liquidity_observations_lookup ON market_liquidity_order_observations(server, item_id, city, quality, side, observed_at)")

    def upsert_liquidity_order(self, order):
        self.initialize()
        with self.connect() as connection:
            values = (order.source, order.server, order.order_id, order.item_id, order.city, order.quality, order.side, order.price, order.quantity, order.expires_at, order.observed_at, order.source_timestamp)
            connection.execute("""INSERT INTO market_liquidity_order_observations
                (source,server,order_id,item_id,city,quality,side,price,quantity,expires_at,observed_at,source_timestamp)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", values)
            if order.order_id is not None:
                connection.execute("""INSERT INTO market_liquidity_orders
                    (source,server,order_id,item_id,city,quality,side,price,quantity,expires_at,observed_at,first_seen,last_seen,status,source_timestamp)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source,server,order_id) DO UPDATE SET
                    item_id=excluded.item_id, city=excluded.city, quality=excluded.quality, side=excluded.side,
                    price=excluded.price, quantity=excluded.quantity, expires_at=excluded.expires_at,
                    observed_at=CASE WHEN excluded.observed_at > market_liquidity_orders.observed_at THEN excluded.observed_at ELSE market_liquidity_orders.observed_at END,
                    last_seen=CASE WHEN excluded.last_seen > market_liquidity_orders.last_seen THEN excluded.last_seen ELSE market_liquidity_orders.last_seen END,
                    first_seen=CASE WHEN market_liquidity_orders.first_seen IS NULL OR excluded.first_seen < market_liquidity_orders.first_seen THEN excluded.first_seen ELSE market_liquidity_orders.first_seen END,
                    status='ACTIVE',
                    source_timestamp=excluded.source_timestamp""",
                    (*values[:11], order.observed_at, order.observed_at, 'ACTIVE', order.source_timestamp))
            else:
                connection.execute("""INSERT INTO market_liquidity_orders
                    (source,server,order_id,item_id,city,quality,side,price,quantity,expires_at,observed_at,first_seen,last_seen,status,source_timestamp)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (*values[:11], order.observed_at, order.observed_at, 'ACTIVE', order.source_timestamp))

    def refresh_liquidity_order_status(self, *, server: str | None = None, now: str | None = None, stale_minutes: float = 15.0) -> dict[str, int]:
        from datetime import datetime, timedelta, timezone
        if stale_minutes < 0:
            raise ValueError("stale_minutes must be >= 0")
        current = datetime.fromisoformat((now or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")).astimezone(timezone.utc)
        current_s = current.isoformat().replace("+00:00", "Z")
        cutoff_s = (current - timedelta(minutes=stale_minutes)).isoformat().replace("+00:00", "Z")
        self.initialize()
        clauses = ["1=1"]
        params: list[Any] = []
        if server is not None:
            clauses.append("server=?"); params.append(server)
        with self.connect() as connection:
            rows = connection.execute(f"SELECT id, expires_at, last_seen, status FROM market_liquidity_orders WHERE {' AND '.join(clauses)}", params).fetchall()
            counts = {"ACTIVE": 0, "EXPIRED": 0, "STALE": 0, "UNKNOWN": 0}
            for row in rows:
                status = "UNKNOWN"
                try:
                    expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")).astimezone(timezone.utc) if row["expires_at"] else None
                    last_seen = datetime.fromisoformat(row["last_seen"].replace("Z", "+00:00")).astimezone(timezone.utc) if row["last_seen"] else None
                    if expires is not None and expires <= current:
                        status = "EXPIRED"
                    elif last_seen is None:
                        status = "UNKNOWN"
                    elif last_seen.isoformat().replace("+00:00", "Z") < cutoff_s:
                        status = "STALE"
                    else:
                        status = "ACTIVE"
                except (TypeError, ValueError):
                    status = "UNKNOWN"
                connection.execute("UPDATE market_liquidity_orders SET status=?, observed_at=CASE WHEN ?='ACTIVE' THEN last_seen ELSE observed_at END WHERE id=?", (status, status, row["id"]))
                counts[status] += 1
            return counts

    def liquidity_orders(self, *, server, item_id, city, quality, side=None, observed_after=None, include_inactive: bool = False, stale_minutes: float = 15.0, now: str | None = None):
        self.refresh_liquidity_order_status(server=server, now=now, stale_minutes=stale_minutes)
        self.initialize()
        clauses=["server=?", "item_id=?", "city=?", "quality=?"]
        params=[server,item_id,city,quality]
        if side is not None:
            clauses.append("side=?"); params.append(side)
        if observed_after is not None:
            clauses.append("last_seen>=?"); params.append(observed_after)
        if not include_inactive:
            clauses.append("status='ACTIVE'")
        with self.connect() as connection:
            rows=connection.execute(f"SELECT * FROM market_liquidity_orders WHERE {' AND '.join(clauses)} ORDER BY price", params).fetchall()
            return [dict(row) for row in rows]

    def liquidity_order_counts(self, *, server: str | None = None, stale_minutes: float = 15.0) -> dict[str, int]:
        return self.refresh_liquidity_order_status(server=server, stale_minutes=stale_minutes)

    def upsert_current(self, record: dict[str, Any]):
        self.initialize()
        with self.connect() as connection:
            connection.execute("""INSERT INTO market_prices
                (server,item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(server,item_id,city,quality) DO UPDATE SET
                sell_price_min=excluded.sell_price_min,
                sell_price_min_date=excluded.sell_price_min_date,
                buy_price_max=excluded.buy_price_max,
                buy_price_max_date=excluded.buy_price_max_date,
                updated_at=excluded.updated_at""", self._values(record, "updated_at"))

    def insert_history(self, record: dict[str, Any]):
        self.initialize()
        with self.connect() as connection:
            connection.execute("""INSERT INTO market_price_history
                (server,item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,recorded_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", self._values(record, "recorded_at"))

    @staticmethod
    def _values(record: dict[str, Any], timestamp_field: str):
        return (record.get("server", ALBION_SERVER), record["item_id"], record["city"], record["quality"],
                record.get("sell_price_min"), record.get("sell_price_min_date"),
                record.get("buy_price_max"), record.get("buy_price_max_date"), record[timestamp_field])

    def current_prices(self, item_id=None, city=None, quality=None, server=ALBION_SERVER):
        return self._query("market_prices", item_id, city, quality, server)

    def history(self, item_id=None, city=None, quality=None, start=None, end=None, server=ALBION_SERVER):
        self.initialize()
        clauses, params = ["server = ?"], [server]
        for column, value in (("item_id", item_id), ("city", city), ("quality", quality)):
            if value is not None: clauses.append(f"{column} = ?"); params.append(value)
        if start is not None: clauses.append("recorded_at >= ?"); params.append(start)
        if end is not None: clauses.append("recorded_at <= ?"); params.append(end)
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(f"SELECT * FROM market_price_history WHERE {' AND '.join(clauses)} ORDER BY recorded_at,id", params)]

    def _query(self, table, item_id, city, quality, server=ALBION_SERVER):
        self.initialize()
        clauses, params = ["server = ?"], [server]
        for column, value in (("item_id", item_id), ("city", city), ("quality", quality)):
            if value is not None: clauses.append(f"{column} = ?"); params.append(value)
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} ORDER BY item_id,city,quality", params)]

    def start_collection_run(self, started_at: str, server: str = ALBION_SERVER) -> int:
        self.initialize()
        with self.connect() as connection:
            return int(connection.execute("INSERT INTO collection_runs(server,started_at) VALUES(?,?)", (server, started_at)).lastrowid)

    def finish_collection_run(self, run_id: int, *, finished_at: str, success: bool, records_received: int, records_saved: int, error: str | None, duration_seconds: float):
        self.initialize()
        with self.connect() as connection:
            connection.execute("UPDATE collection_runs SET finished_at=?,success=?,records_received=?,records_saved=?,error=?,duration_seconds=? WHERE id=?", (finished_at,int(success),records_received,records_saved,error,duration_seconds,run_id))

    def latest_collection_run(self, server: str = ALBION_SERVER):
        self.initialize()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM collection_runs WHERE server=? ORDER BY id DESC LIMIT 1", (server,)).fetchone()
            return dict(row) if row else None

    def collection_runs(self, server=ALBION_SERVER, start=None, end=None):
        self.initialize()
        clauses, params = ["server = ?"], [server]
        if start is not None: clauses.append("started_at >= ?"); params.append(start)
        if end is not None: clauses.append("started_at <= ?"); params.append(end)
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(f"SELECT * FROM collection_runs WHERE {' AND '.join(clauses)} ORDER BY started_at,id", params)]
