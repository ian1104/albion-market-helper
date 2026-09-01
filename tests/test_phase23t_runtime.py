import asyncio
import json
import time
from types import SimpleNamespace

from services.aodp_nats import AODPNatsAdapter, AODPNatsConsumer


class SlowDatabase:
    def __init__(self, delay=0.05):
        self.delay = delay
        self.saved = []

    def upsert_liquidity_order(self, order):
        time.sleep(self.delay)
        self.saved.append(order)


def _message(order_id=1):
    payload = {
        "Orders": [
            {
                "Id": order_id,
                "ItemTypeId": "T4_BAG",
                "LocationId": "Caerleon",
                "QualityLevel": 1,
                "UnitPriceSilver": 12000,
                "Amount": 10,
                "AuctionType": "offer",
            }
        ]
    }
    return SimpleNamespace(data=json.dumps(payload).encode())


def test_nats_persistence_yields_to_event_loop():
    """Blocking persistence must not monopolize the asyncio event loop."""
    db = SlowDatabase(delay=0.08)
    consumer = AODPNatsConsumer(
        AODPNatsAdapter(), db, server="east", nats_url="nats://fixture"
    )

    async def scenario():
        heartbeat = asyncio.Event()

        async def pulse():
            await asyncio.sleep(0.01)
            heartbeat.set()

        message_task = asyncio.create_task(consumer._handle_message(_message()))
        pulse_task = asyncio.create_task(pulse())
        await asyncio.wait_for(asyncio.gather(message_task, pulse_task), timeout=1)
        assert heartbeat.is_set()

    asyncio.run(scenario())
    assert consumer.messages_received == 1
    assert consumer.orders_saved == 1
    assert consumer.persistence_failures == 0
    assert consumer.last_persistence_duration_ms is not None


def test_nats_persistence_preserves_order_and_records_diagnostics():
    db = SlowDatabase(delay=0.001)
    consumer = AODPNatsConsumer(
        AODPNatsAdapter(), db, server="east", nats_url="nats://fixture"
    )

    async def ingest():
        await asyncio.gather(
            consumer._handle_message(_message(1001)),
            consumer._handle_message(_message(1002)),
            consumer._handle_message(_message(1003)),
        )

    asyncio.run(ingest())

    assert consumer.messages_received == 3
    assert consumer.orders_parsed == 3
    assert consumer.orders_saved == 3
    assert consumer.persistence_failures == 0
    assert consumer.last_persistence_duration_ms is not None
    assert consumer.max_persistence_duration_ms >= consumer.last_persistence_duration_ms
    assert [order.order_id for order in db.saved] == ["1001", "1002", "1003"]
