import asyncio
import json
from types import SimpleNamespace

from db.database import Database
from services.aodp_nats import AODPNatsAdapter, AODPNatsConsumer


def _payload(order_id=7001, location=3010):
    return json.dumps({
        "Id": order_id,
        "ItemTypeId": "T4_BAG",
        "LocationId": location,
        "QualityLevel": 1,
        "UnitPriceSilver": 10000,
        "Amount": 3,
        "AuctionType": "offer",
    }).encode()


def test_phase21_consumer_stop_interrupts_backoff(monkeypatch, tmp_path):
    import nats

    async def fail_connect(*args, **kwargs):
        raise RuntimeError("simulated connection failure")

    monkeypatch.setattr(nats, "connect", fail_connect)
    db = Database(tmp_path / "stop.db")
    consumer = AODPNatsConsumer(
        AODPNatsAdapter(), db, server="east", nats_url="nats://invalid",
        reconnect_base_seconds=30, reconnect_max_seconds=30,
    )

    async def run():
        task = asyncio.create_task(consumer.run_forever())
        await asyncio.sleep(0.05)
        await consumer.stop()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(run())
    assert consumer.connection_attempts == 1
    assert consumer.subscription_active is False


def test_phase21_application_order_path_preserves_server_and_city(tmp_path):
    db = Database(tmp_path / "orders.db")
    consumer = AODPNatsConsumer(AODPNatsAdapter(), db, server="west", nats_url="nats://invalid")

    async def run():
        await consumer._handle_message(SimpleNamespace(data=_payload(location=2004)))
        await consumer._handle_message(SimpleNamespace(data=_payload(location=2004)))

    asyncio.run(run())

    with db.connect() as con:
        current = con.execute(
            "SELECT COUNT(*) FROM market_liquidity_orders WHERE server='west' AND order_id='7001'"
        ).fetchone()[0]
        observations = con.execute(
            "SELECT COUNT(*) FROM market_liquidity_order_observations WHERE server='west' AND order_id='7001'"
        ).fetchone()[0]
        city = con.execute(
            "SELECT city FROM market_liquidity_orders WHERE server='west' AND order_id='7001'"
        ).fetchone()[0]

    assert current == 1
    assert observations == 2
    assert city == "Bridgewatch"
