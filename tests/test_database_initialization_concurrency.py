from concurrent.futures import ThreadPoolExecutor

from db.database import Database
from services.market_data import NormalizedMarketOrder


def _order(order_id: str) -> NormalizedMarketOrder:
    return NormalizedMarketOrder(
        source="aodp-nats",
        server="east",
        item_id="T4_BAG",
        city="Caerleon",
        quality=1,
        side="sell",
        price=12000,
        quantity=10,
        order_id=order_id,
        expires_at="2026-09-02T00:00:00Z",
        observed_at="2026-09-01T10:00:00Z",
    )


def _assert_integrity(db: Database) -> None:
    with db.connect() as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        indexes = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_market_price_history_lookup'"
        ).fetchall()
        assert [row[0] for row in indexes] == ["idx_market_price_history_lookup"]


def test_concurrent_initialize_is_serialized(tmp_path):
    db_path = tmp_path / "concurrent.db"
    databases = [Database(db_path) for _ in range(8)]

    with ThreadPoolExecutor(max_workers=len(databases)) as executor:
        list(executor.map(lambda database: database.initialize(), databases))

    _assert_integrity(databases[0])


def test_repeated_initialize_is_idempotent(tmp_path):
    db = Database(tmp_path / "repeated.db")

    for _ in range(20):
        db.initialize()

    _assert_integrity(db)


def test_concurrent_persistence_completes_without_schema_race(tmp_path):
    db = Database(tmp_path / "persistence.db")
    db.initialize()
    orders = [_order(str(index)) for index in range(20)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(db.upsert_liquidity_order, orders))

    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM market_liquidity_orders").fetchone()[0] == len(orders)
        assert connection.execute("SELECT COUNT(*) FROM market_liquidity_order_observations").fetchone()[0] == len(orders)
    _assert_integrity(db)
