import asyncio
import json
from types import SimpleNamespace

from db.database import Database
from services.aodp_nats import AODPNatsAdapter, AODPNatsConsumer


def payload():
    return {
        "Orders": [{
            "Id": 101,
            "ItemTypeId": "T4_BAG",
            "LocationId": 3004,
            "QualityLevel": 1,
            "UnitPriceSilver": 9000,
            "Amount": 4,
            "AuctionType": "offer",
        }]
    }


def test_phase19_consumer_records_persistence_and_observability(tmp_path):
    db = Database(tmp_path / "collector.db")
    consumer = AODPNatsConsumer(AODPNatsAdapter(), db, server="east", nats_url="nats://invalid")

    async def run():
        await consumer._handle_message(SimpleNamespace(data=json.dumps(payload()).encode()))
        await consumer._on_disconnected()
        await consumer._on_reconnected()

    asyncio.run(run())

    assert consumer.messages_received == 1
    assert consumer.orders_parsed == 1
    assert consumer.orders_saved == 1
    assert consumer.last_message_at is not None
    assert consumer.last_successful_persistence is not None
    assert consumer.reconnect_count == 1
    assert consumer.subscription_active is True

    rows = db.liquidity_orders(
        server="east", item_id="T4_BAG", city="Martlock", quality=1, stale_minutes=60
    )
    assert len(rows) == 1


def test_phase19_invalid_payload_does_not_stop_consumer(tmp_path):
    db = Database(tmp_path / "invalid.db")
    consumer = AODPNatsConsumer(AODPNatsAdapter(), db, server="east", nats_url="nats://invalid")

    async def run():
        await consumer._handle_message(SimpleNamespace(data=b'{"invalid": true}'))
        await consumer._handle_message(SimpleNamespace(data=json.dumps(payload()).encode()))

    asyncio.run(run())

    assert consumer.messages_received == 2
    assert consumer.invalid_messages == 1
    assert consumer.orders_saved == 1
