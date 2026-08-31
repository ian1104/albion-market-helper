import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from db.database import Database
from services.aodp_nats import AODPNatsAdapter, AODPNatsConsumer
from services.liquidity import DatabaseLiquidityProvider
from services.market_data import NormalizedMarketOrder


def recent(minutes_ago: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")


OBSERVED = recent()


def payload():
    return {
        "Orders": [
            {"Id": 1, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1, "UnitPriceSilver": 9000, "Amount": 10, "AuctionType": "offer"},
            {"Id": 2, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1, "UnitPriceSilver": 9100, "Amount": 20, "AuctionType": "offer"},
            {"Id": 3, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1, "UnitPriceSilver": 8800, "Amount": 5, "AuctionType": "request"},
        ]
    }


def test_aodp_nats_adapter_normalizes_real_quantity_and_sides():
    orders = AODPNatsAdapter().normalize(payload(), server="east", observed_at=OBSERVED)
    assert len(orders) == 3
    assert orders[0].side == "sell"
    assert orders[0].quantity == 10
    assert orders[2].side == "buy"
    assert orders[2].price == 8800


def test_aodp_nats_adapter_normalizes_observed_single_market_order():
    order = {
        "Id": 42,
        "ItemTypeId": "T4_BAG",
        "LocationId": "Bridgewatch",
        "QualityLevel": 1,
        "UnitPriceSilver": 9500,
        "Amount": 4,
        "AuctionType": "offer",
    }
    normalized = AODPNatsAdapter().normalize(order, server="east", observed_at=OBSERVED)
    assert len(normalized) == 1
    assert normalized[0].order_id == "42"
    assert normalized[0].city == "Bridgewatch"
    assert normalized[0].side == "sell"
    assert normalized[0].price == 9500
    assert normalized[0].quantity == 4


def test_aodp_numeric_location_id_is_normalized_to_market_city():
    order = {
        "Id": 43,
        "ItemTypeId": "T5_SHOES_PLATE_SET1@2",
        "LocationId": 3010,
        "QualityLevel": 4,
        "UnitPriceSilver": 50000,
        "Amount": 2,
        "AuctionType": "offer",
    }
    normalized = AODPNatsAdapter().normalize(order, server="east", observed_at=OBSERVED)
    assert normalized[0].city == "Martlock"


def test_unknown_numeric_location_id_is_not_guessed():
    order = {
        "Id": 44,
        "ItemTypeId": "T4_BAG",
        "LocationId": 999999,
        "QualityLevel": 1,
        "UnitPriceSilver": 5000,
        "Amount": 1,
        "AuctionType": "offer",
    }
    normalized = AODPNatsAdapter().normalize(order, server="east", observed_at=OBSERVED)
    assert normalized[0].city == "999999"


def test_adapter_rejects_malformed_payload():
    with pytest.raises(ValueError):
        AODPNatsAdapter().normalize({"not_orders": []}, server="east", observed_at=OBSERVED)


def test_adapter_drops_missing_or_invalid_order_fields():
    p = {"Orders": [
        {"Id": 1, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1, "UnitPriceSilver": 9000, "Amount": 0, "AuctionType": "offer"},
        {"Id": 2, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1, "UnitPriceSilver": 9000, "Amount": 2, "AuctionType": "unknown"},
    ]}
    assert AODPNatsAdapter().normalize(p, server="east", observed_at=OBSERVED) == []


def test_database_provider_builds_executable_depth(tmp_path):
    db = Database(tmp_path / "market.db")
    db.initialize()
    orders = AODPNatsAdapter().normalize(payload(), server="east", observed_at=OBSERVED)
    for order in orders:
        db.upsert_liquidity_order(order)
    provider = DatabaseLiquidityProvider(db, max_age_minutes=60, source="aodp-nats")
    snapshot = provider.get("east", "T4_BAG", "Caerleon", 1)
    assert snapshot is not None
    assert snapshot.available_buy_quantity == 30
    assert snapshot.available_sell_quantity == 5
    assert [x.price for x in snapshot.buy_depth] == [9000, 9100]
    assert [x.price for x in snapshot.sell_depth] == [8800]


def test_normalized_order_requires_parseable_timestamp():
    with pytest.raises(ValueError):
        NormalizedMarketOrder("aodp-nats", "east", "T4_BAG", "Caerleon", 1, "sell", 1, 1, "1", None, "bad")


def test_duplicate_order_upsert_preserves_one_current_row_and_records_observations(tmp_path):
    db = Database(tmp_path / "orders.db")
    first_seen = recent(2)
    second_seen = recent(1)
    order = AODPNatsAdapter().normalize(
        {"Orders": [{"Id": 99, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1,
                     "UnitPriceSilver": 9000, "Amount": 10, "AuctionType": "offer"}]},
        server="east", observed_at=first_seen
    )[0]
    db.upsert_liquidity_order(order)
    updated = AODPNatsAdapter().normalize(
        {"Orders": [{"Id": 99, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1,
                     "UnitPriceSilver": 9100, "Amount": 7, "AuctionType": "offer"}]},
        server="east", observed_at=second_seen
    )[0]
    db.upsert_liquidity_order(updated)
    rows = db.liquidity_orders(server="east", item_id="T4_BAG", city="Caerleon", quality=1, stale_minutes=60)
    assert len(rows) == 1
    assert rows[0]["price"] == 9100
    assert rows[0]["quantity"] == 7
    assert rows[0]["first_seen"] == first_seen
    assert rows[0]["last_seen"] == second_seen
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM market_liquidity_order_observations").fetchone()[0] == 2


def test_order_lifecycle_expiry_and_stale_exclusion(tmp_path):
    db = Database(tmp_path / "lifecycle.db")
    adapter = AODPNatsAdapter()
    active = adapter.normalize({"Orders": [{"Id": 1, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1,
        "UnitPriceSilver": 9000, "Amount": 10, "AuctionType": "offer", "Expires": "2026-08-31T07:01:00Z"}]},
        server="east", observed_at="2026-08-31T06:55:00Z")[0]
    stale = adapter.normalize({"Orders": [{"Id": 2, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1,
        "UnitPriceSilver": 9100, "Amount": 10, "AuctionType": "offer", "Expires": "2026-09-01T07:00:00Z"}]},
        server="east", observed_at="2026-08-31T06:00:00Z")[0]
    expired = adapter.normalize({"Orders": [{"Id": 3, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1,
        "UnitPriceSilver": 9200, "Amount": 10, "AuctionType": "offer", "Expires": "2026-08-31T06:59:00Z"}]},
        server="east", observed_at="2026-08-31T06:55:00Z")[0]
    for order in (active, stale, expired):
        db.upsert_liquidity_order(order)
    counts = db.refresh_liquidity_order_status(server="east", now="2026-08-31T07:00:00Z", stale_minutes=30)
    assert counts["ACTIVE"] == 1
    assert counts["EXPIRED"] == 1
    assert counts["STALE"] == 1
    rows = db.liquidity_orders(server="east", item_id="T4_BAG", city="Caerleon", quality=1, stale_minutes=30, now="2026-08-31T07:00:00Z")
    assert [row["order_id"] for row in rows] == ["1"]


def test_servers_are_isolated_for_same_order_id(tmp_path):
    db = Database(tmp_path / "servers.db")
    adapter = AODPNatsAdapter()
    for server, price in (("east", 9000), ("west", 10000)):
        order = adapter.normalize({"Orders": [{"Id": 7, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1,
            "UnitPriceSilver": price, "Amount": 1, "AuctionType": "offer"}]},
            server=server, observed_at=recent())[0]
        db.upsert_liquidity_order(order)
    east = db.liquidity_orders(server="east", item_id="T4_BAG", city="Caerleon", quality=1, stale_minutes=60)
    west = db.liquidity_orders(server="west", item_id="T4_BAG", city="Caerleon", quality=1, stale_minutes=60)
    assert east[0]["price"] == 9000
    assert west[0]["price"] == 10000


def test_consumer_isolates_malformed_message_and_continues(tmp_path):
    db = Database(tmp_path / "consumer.db")
    consumer = AODPNatsConsumer(AODPNatsAdapter(), db, server="east", nats_url="nats://invalid")

    async def run():
        await consumer._handle_message(SimpleNamespace(data=b'{"bad": []}'))
        await consumer._handle_message(SimpleNamespace(data=json.dumps(payload()).encode()))

    asyncio.run(run())
    assert consumer.messages_received == 2
    assert consumer.invalid_messages == 1
    assert consumer.orders_saved == 3
    assert consumer.last_message_at is not None
