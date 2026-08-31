import pytest
from datetime import datetime, timezone

from db.database import Database
from services.arbitrage_service import ArbitrageService, CostModel
from services.liquidity import DatabaseLiquidityProvider, DepthLevel, LiquiditySnapshot, executable_quantity, slippage_percent, weighted_average_execution_price
from services.market_service import MarketService


class Provider:
    def __init__(self):
        self.rows = {}
    def get(self, server, item_id, city, quality):
        return self.rows.get((server, item_id, city, quality))


def rec(city, sell, buy, at=None, item='T4_BAG', quality=1, server='east'):
    at = at or datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    return {'server': server, 'item_id': item, 'city': city, 'quality': quality,
            'sell_price_min': sell, 'sell_price_min_date': at if sell is not None else None,
            'buy_price_max': buy, 'buy_price_max_date': at if buy is not None else None,
            'recorded_at': at}


def seed(tmp_path):
    db = Database(tmp_path/'liq.db'); s = MarketService(db)
    s.save_snapshot(rec('Caerleon', 12000, 11500), '2026-08-31T06:00:00Z')
    s.save_snapshot(rec('Bridgewatch', 9000, 8500), '2026-08-31T06:00:00Z')
    return db


def test_executable_quantity_limits_by_both_sides():
    assert executable_quantity(100, 80, 50) == 50
    assert executable_quantity(10, 80, 50) == 10
    assert executable_quantity(100, None, 50) is None


def test_depth_weighted_execution_and_slippage():
    levels = [DepthLevel(100, 5), DepthLevel(110, 10)]
    assert weighted_average_execution_price(levels, 10) == 105
    assert slippage_percent(100, 105, 'buy') == 5
    assert slippage_percent(100, 95, 'sell') == 5
    assert weighted_average_execution_price(levels, 20) is None


def test_invalid_liquidity_values():
    with pytest.raises(ValueError): executable_quantity(0, 1, 1)
    with pytest.raises(ValueError): executable_quantity(1, -1, 1)
    with pytest.raises(ValueError): DepthLevel(0, 1)
    with pytest.raises(ValueError): slippage_percent(0, 100, 'buy')


def test_arbitrage_reports_unavailable_liquidity_without_fabrication(tmp_path):
    ops = ArbitrageService(seed(tmp_path)).opportunities('T4_BAG', 1, quantity=100, cost_model=CostModel(configured=True))
    assert ops
    assert ops[0]['liquidity']['executable_quantity'] is None
    assert ops[0]['slippage']['status'] == 'unavailable'
    assert ops[0]['realistic_profit']['status'] == 'unavailable'
    assert ops[0]['data_availability']['liquidity'] == 'unavailable'
    assert ops[0]['confidence'] == 'MEDIUM'


def test_available_liquidity_produces_executable_and_realistic_profit(tmp_path):
    provider = Provider()
    for city, qty in [('Bridgewatch', 50), ('Caerleon', 20)]:
        provider.rows[('east', 'T4_BAG', city, 1)] = LiquiditySnapshot(available_quantity=qty, source='test-depth')
    ops = ArbitrageService(seed(tmp_path), liquidity_provider=provider).opportunities('T4_BAG', 1, quantity=100, cost_model=CostModel(configured=True))
    op = next(o for o in ops if o['buy']['city'] == 'Bridgewatch' and o['sell']['city'] == 'Caerleon')
    assert op['liquidity']['executable_quantity'] == 20
    assert op['realistic_profit']['quantity'] == 20
    assert op['realistic_profit']['net_profit'] == 50000
    assert op['confidence'] == 'MEDIUM'


def test_liquidity_service_endpoint(tmp_path, monkeypatch):
    import api.main as main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, 'database', seed(tmp_path))
    r = TestClient(main.app).get('/api/arbitrage/liquidity', params={'item_id':'T4_BAG','city':'Caerleon','quality':1})
    assert r.status_code == 200
    assert r.json()['liquidity']['status'] == 'unavailable'


def test_depth_aware_realistic_profit_and_slippage(tmp_path):
    provider = Provider()
    provider.rows[('east', 'T4_BAG', 'Bridgewatch', 1)] = LiquiditySnapshot(available_buy_quantity=10, buy_depth=(DepthLevel(9000, 5), DepthLevel(10000, 5)), source='orderbook')
    provider.rows[('east', 'T4_BAG', 'Caerleon', 1)] = LiquiditySnapshot(available_sell_quantity=10, sell_depth=(DepthLevel(11500, 5), DepthLevel(11000, 5)), source='orderbook')
    op = next(o for o in ArbitrageService(seed(tmp_path), liquidity_provider=provider).opportunities('T4_BAG', 1, quantity=10, cost_model=CostModel(configured=True)) if o['buy']['city'] == 'Bridgewatch' and o['sell']['city'] == 'Caerleon')
    assert op['liquidity']['executable_quantity'] == 10
    assert op['slippage']['status'] == 'available'
    assert op['slippage']['buy_percent'] > 0
    assert op['slippage']['sell_percent'] > 0
    assert op['realistic_profit']['buy_execution_price'] == 9500
    assert op['realistic_profit']['sell_execution_price'] == 11250
    assert op['realistic_profit']['net_profit'] == 17500


def test_database_liquidity_excludes_stale_orders(tmp_path):
    db = Database(tmp_path / "stale.db")
    from services.aodp_nats import AODPNatsAdapter
    order = AODPNatsAdapter().normalize({"Orders": [{"Id": 1, "ItemTypeId": "T4_BAG", "LocationId": "Caerleon", "QualityLevel": 1,
        "UnitPriceSilver": 9000, "Amount": 10, "AuctionType": "offer"}]},
        server="east", observed_at="2026-08-31T05:00:00Z")[0]
    db.upsert_liquidity_order(order)
    provider = DatabaseLiquidityProvider(db, max_age_minutes=15, source="aodp-nats")
    assert provider.get("east", "T4_BAG", "Caerleon", 1) is None


def test_liquidity_status_and_summary_endpoints(tmp_path, monkeypatch):
    import api.main as main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, 'database', seed(tmp_path))
    monkeypatch.setattr(main, 'lifecycle_manager', __import__('services.order_lifecycle', fromlist=['OrderLifecycleManager']).OrderLifecycleManager(main.database, stale_minutes=60))
    client = TestClient(main.app)
    status = client.get('/api/liquidity/status', params={'server': 'east'})
    summary = client.get('/api/liquidity/summary', params={'server': 'east'})
    orders = client.get('/api/liquidity/orders', params={'item_id': 'T4_BAG', 'city': 'Caerleon', 'quality': 1, 'server': 'east'})
    assert status.status_code == 200
    assert summary.status_code == 200
    assert orders.status_code == 200
    assert status.json()['enabled'] is False
    assert summary.json()['available'] is False
