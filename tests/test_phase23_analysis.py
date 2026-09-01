from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.phase23_analysis import nats_candidate_analysis, price_integrity, rest_vs_nats


def _db(tmp_path: Path) -> sqlite3.Connection:
    p = tmp_path / "x.db"
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE market_price_history (id INTEGER PRIMARY KEY, item_id TEXT, server TEXT, city TEXT, quality INTEGER, sell_price_min INTEGER, buy_price_max INTEGER, sell_price_min_date TEXT, buy_price_max_date TEXT, recorded_at TEXT);
      CREATE TABLE market_prices (id INTEGER PRIMARY KEY, item_id TEXT, server TEXT, city TEXT, quality INTEGER, sell_price_min INTEGER, buy_price_max INTEGER);
      CREATE TABLE market_liquidity_orders (id INTEGER PRIMARY KEY, source TEXT, server TEXT, order_id TEXT, item_id TEXT, city TEXT, quality INTEGER, side TEXT, price REAL, quantity REAL, expires_at TEXT, observed_at TEXT, last_seen TEXT, status TEXT);
    """)
    return c


def test_rest_vs_nats_price_mismatch(tmp_path: Path):
    c = _db(tmp_path)
    c.execute("INSERT INTO market_prices VALUES(1,'T4_TEST','east','Bridgewatch',1,100,90)")
    c.execute("INSERT INTO market_liquidity_orders VALUES(1,'aodp-nats','east','o1','T4_TEST','Bridgewatch',1,'sell',120,5,NULL,'2026-09-01T00:00:00Z','2026-09-01T00:00:00Z','ACTIVE')")
    c.commit()
    rows = rest_vs_nats(c, 'east')
    assert rows[0]['rest_sell'] == 100
    assert rows[0]['nats_lowest_sell'] == 120


def test_nats_candidate_requires_real_opposite_sides(tmp_path: Path):
    c = _db(tmp_path)
    now='2099-01-01T00:00:00Z'
    rows=[
      (1,'aodp-nats','east','a','T4_TEST','Bridgewatch',1,'sell',100,10,None,now,now,'ACTIVE'),
      (2,'aodp-nats','east','b','T4_TEST','Caerleon',1,'buy',130,4,None,now,now,'ACTIVE'),
    ]
    c.executemany("INSERT INTO market_liquidity_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows); c.commit()
    result=nats_candidate_analysis(c,'east')
    assert result['positive_gross_pairs'] == 1
    assert result['executable_pairs'] == 1
    assert result['examples'][0]['executable_quantity'] == 4


def test_integrity_detects_invalid_values(tmp_path: Path):
    c=_db(tmp_path)
    c.execute("INSERT INTO market_price_history VALUES(1,'T4_TEST','east','4002',1,-1,0,NULL,NULL,'2026-09-01T00:00:00Z')")
    c.execute("INSERT INTO market_liquidity_orders VALUES(1,'aodp-nats','east','o','T4_TEST','4002',1,'sell',1,-2,NULL,'2026-09-01T00:00:00Z','2026-09-01T00:00:00Z','ACTIVE')")
    c.commit(); result=price_integrity(c)
    assert result['negative_price'] == 1
    assert result['zero_price'] == 1
    assert result['negative_quantity'] == 1
    assert result['numeric_location_rows'] == 1
