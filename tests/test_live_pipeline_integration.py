import asyncio
import json
from types import SimpleNamespace

from db.database import Database
from services.aodp_nats import AODPNatsAdapter, AODPNatsConsumer
from services.arbitrage_service import ArbitrageService, CostModel
from services.market_service import MarketService


def test_nats_persistence_liquidity_to_arbitrage_integration(tmp_path):
    """Fixture-only integration test for the live pipeline contract.

    The order payload is explicitly test data. It must never be presented as
    live AODP data; live reception is validated separately by CI/runtime checks.
    """
    db = Database(tmp_path / "integration.db")
    market = MarketService(db, server="east")
    recorded_at = "2026-08-31T12:00:00Z"

    for city, sell_price, buy_price in (
        ("Bridgewatch", 9000, 8800),
        ("Caerleon", 13000, 12000),
    ):
        market.save_snapshot(
            {
                "server": "east",
                "item_id": "T4_BAG",
                "city": city,
                "quality": 1,
                "sell_price_min": sell_price,
                "sell_price_min_date": recorded_at,
                "buy_price_max": buy_price,
                "buy_price_max_date": recorded_at,
                "recorded_at": recorded_at,
            },
            recorded_at,
        )

    # FIXTURE / TEST DATA: mirrors the public AODP MarketUpload shape.
    payload = {
        "Orders": [
            {
                "Id": 1001,
                "ItemTypeId": "T4_BAG",
                "LocationId": "Bridgewatch",
                "QualityLevel": 1,
                "UnitPriceSilver": 9000,
                "Amount": 10,
                "AuctionType": "offer",
            },
            {
                "Id": 1002,
                "ItemTypeId": "Caerleon",
                "LocationId": "Caerleon",
                "QualityLevel": 1,
                "UnitPriceSilver": 12000,
                "Amount": 10,
                "AuctionType": "request",
            },
        ]
    }
    # Correct the fixture item identifier explicitly; keeping this local avoids
    # hiding identifier mismatches in the integration assertions.
    payload["Orders"][1]["ItemTypeId"] = "T4_BAG"

    consumer = AODPNatsConsumer(
        AODPNatsAdapter(), db, server="east", nats_url="nats://fixture", subject="marketorders.deduped"
    )

    async def ingest_fixture():
        await consumer._handle_message(SimpleNamespace(data=json.dumps(payload).encode()))

    asyncio.run(ingest_fixture())

    assert consumer.messages_received == 1
    assert consumer.orders_saved == 2
    assert consumer.last_message_at is not None

    opportunities = ArbitrageService(db, server="east").opportunities(
        item_id="T4_BAG",
        quality=1,
        quantity=10,
        sort="spread",
        cost_model=CostModel(configured=True),
        freshness_max_age_minutes=60,
    )

    bridge_to_caerleon = [
        opportunity
        for opportunity in opportunities
        if opportunity["buy"]["city"] == "Bridgewatch" and opportunity["sell"]["city"] == "Caerleon"
    ]
    assert bridge_to_caerleon
    opportunity = bridge_to_caerleon[0]
    assert opportunity["liquidity"]["executable_quantity"] == 10
    assert opportunity["realistic_profit"]["status"] == "available"
    assert opportunity["realistic_profit"]["net_profit"] == 30000
