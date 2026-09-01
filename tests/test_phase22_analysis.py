from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.phase22_analysis import _age_minutes, analyze, observation_stats


def _db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
    CREATE TABLE market_price_history (
      id INTEGER PRIMARY KEY, server TEXT, item_id TEXT, city TEXT, quality INTEGER,
      sell_price_min INTEGER, sell_price_min_date TEXT, buy_price_max INTEGER,
      buy_price_max_date TEXT, recorded_at TEXT
    );
    CREATE TABLE market_prices (
      id INTEGER PRIMARY KEY, server TEXT, item_id TEXT, city TEXT, quality INTEGER,
      sell_price_min INTEGER, sell_price_min_date TEXT, buy_price_max INTEGER,
      buy_price_max_date TEXT, updated_at TEXT
    );
    CREATE TABLE market_liquidity_orders (
      id INTEGER PRIMARY KEY, source TEXT, server TEXT, order_id TEXT, item_id TEXT,
      city TEXT, quality INTEGER, side TEXT, price REAL, quantity REAL,
      expires_at TEXT, observed_at TEXT, source_timestamp TEXT, first_seen TEXT,
      last_seen TEXT, status TEXT
    );
    CREATE INDEX idx_liquidity_observations_lookup ON market_liquidity_orders(server, item_id, city, quality, side, status, last_seen, expires_at, price);
    """)
    history = [
        (1,"east","T4_TEST","Bridgewatch",1,100,"2026-09-01T00:00:00Z",90,"2026-09-01T00:00:00Z","2026-09-01T00:00:01Z"),
        (2,"east","T4_TEST","Caerleon",1,150,"2026-09-01T00:00:00Z",140,"2026-09-01T00:00:00Z","2026-09-01T00:00:01Z"),
    ]
    connection.executemany("INSERT INTO market_price_history VALUES(?,?,?,?,?,?,?,?,?,?)", history)
    connection.executemany("INSERT INTO market_prices VALUES(?,?,?,?,?,?,?,?,?,?)", [
        (1,"east","T4_TEST","Bridgewatch",1,100,"2026-09-01T00:00:00Z",90,"2026-09-01T00:00:00Z","2026-09-01T00:00:01Z"),
        (2,"east","T4_TEST","Caerleon",1,150,"2026-09-01T00:00:00Z",140,"2026-09-01T00:00:00Z","2026-09-01T00:00:01Z"),
    ])
    connection.executemany("INSERT INTO market_liquidity_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        (1,"aodp-nats","east","s1","T4_TEST","Bridgewatch",1,"sell",100,10,None,"2026-09-01T00:00:01Z",None,"2026-09-01T00:00:01Z","2026-09-01T00:00:01Z","ACTIVE"),
        (2,"aodp-nats","east","b1","T4_TEST","Caerleon",1,"buy",140,5,None,"2026-09-01T00:00:01Z",None,"2026-09-01T00:00:01Z","2026-09-01T00:00:01Z","ACTIVE"),
    ])
    connection.commit(); connection.close()


def test_age_invalid_is_none() -> None:
    assert _age_minutes("not-a-timestamp") is None


def test_observation_stats_counts_real_rows(tmp_path: Path) -> None:
    path = tmp_path / "market.db"
    _db(path)
    with sqlite3.connect(path) as connection:
        stats = observation_stats(connection)
    assert stats["total_observations"] == 2
    assert stats["unique_items"] == 1
    assert stats["unique_cities"] == 2


def test_analysis_does_not_invent_fee_values(tmp_path: Path) -> None:
    path = tmp_path / "market.db"
    _db(path)
    result = analyze(path, "east")
    assert result["arbitrage"]["cost_model"] == "unconfigured; net fees/ROI unavailable by design"
    assert result["arbitrage"]["profitable_after_fees"] is None


def test_analysis_reports_executable_pair(tmp_path: Path) -> None:
    path = tmp_path / "market.db"
    _db(path)
    result = analyze(path, "east")
    assert result["arbitrage"]["executable_pairs"] >= 1
