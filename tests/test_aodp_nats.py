import pytest

from db.database import Database
from services.aodp_nats import AODPNatsAdapter
from services.liquidity import DatabaseLiquidityProvider
from services.market_data import NormalizedMarketOrder


OBSERVED = "2026-08-31T06:00:00Z"


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
