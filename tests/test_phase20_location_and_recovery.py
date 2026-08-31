import asyncio
import json
from types import SimpleNamespace

from config import AODP_LOCATION_NAMES
from db.database import Database
from services.aodp_nats import AODPNatsAdapter, AODPNatsConsumer


def order_payload(*, order_id=501, location_id=3010, item_id="T4_BAG"):
    return {
        "Id": order_id,
        "ItemTypeId": item_id,
        "LocationId": location_id,
        "QualityLevel": 1,
        "UnitPriceSilver": 10000,
        "Amount": 5,
        "AuctionType": "offer",
    }


def test_phase20_known_market_location_ids_are_canonical():
    assert AODP_LOCATION_NAMES["7"] == "Thetford"
    assert AODP_LOCATION_NAMES["1002"] == "Lymhurst"
    assert AODP_LOCATION_NAMES["2004"] == "Bridgewatch"
    assert AODP_LOCATION_NAMES["3005"] == "Caerleon"
    assert AODP_LOCATION_NAMES["3010"] == "Martlock"
    assert AODP_LOCATION_NAMES["4002"] == "Fort Sterling"


def test_phase20_unknown_location_is_not_guessed():
    normalized = AODPNatsAdapter().normalize(
        order_payload(location_id=3008), server="east", observed_at="2026-09-01T00:00:00Z"
    )
    assert len(normalized) == 1
    assert normalized[0].city == "3008"
    assert "3008" not in AODP_LOCATION_NAMES


def test_phase20_server_isolation_and_location_resolution():
    adapter = AODPNatsAdapter()
    east = adapter.normalize(order_payload(location_id=2004), server="east")
    west = adapter.normalize(order_payload(order_id=502, location_id=4002), server="west")
    assert east[0].server == "east"
    assert east[0].city == "Bridgewatch"
    assert west[0].server == "west"
    assert west[0].city == "Fort Sterling"


def test_phase20_restart_recovery_preserves_db_and_upserts_order(tmp_path):
    db_path = tmp_path / "restart.db"
    adapter = AODPNatsAdapter()
    payload = json.dumps(order_payload()).encode()

    first_db = Database(db_path)
    first = AODPNatsConsumer(adapter, first_db, server="east", nats_url="nats://invalid")

    async def receive(consumer):
        await consumer._handle_message(SimpleNamespace(data=payload))
        await consumer.stop()

    asyncio.run(receive(first))

    second_db = Database(db_path)
    second = AODPNatsConsumer(adapter, second_db, server="east", nats_url="nats://invalid")
    asyncio.run(receive(second))

    rows = second_db.liquidity_orders(
        server="east", item_id="T4_BAG", city="Martlock", quality=1, stale_minutes=60
    )
    assert len(rows) == 1
    assert rows[0]["order_id"] == "501"

    with second_db.connect() as connection:
        current = connection.execute(
            "SELECT COUNT(*) FROM market_liquidity_orders WHERE server=? AND order_id=?",
            ("east", "501"),
        ).fetchone()[0]
        observations = connection.execute(
            "SELECT COUNT(*) FROM market_liquidity_order_observations WHERE server=? AND order_id=?",
            ("east", "501"),
        ).fetchone()[0]
    assert current == 1
    assert observations == 2
