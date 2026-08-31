import pytest
from fastapi.testclient import TestClient

from api.main import app
from db.database import Database
from services.arbitrage_service import ArbitrageService, CostModel, ProfitCalculator
from services.market_service import MarketService


def rec(city, sell, buy, at='2026-08-30T12:00:00Z', item='T4_BAG', quality=1, server='east'):
    return {'server': server, 'item_id': item, 'city': city, 'quality': quality,
            'sell_price_min': sell, 'sell_price_min_date': at if sell is not None else None,
            'buy_price_max': buy, 'buy_price_max_date': at if buy is not None else None,
            'recorded_at': at}


def seed(tmp_path):
    db = Database(tmp_path/'arb.db')
    service = MarketService(db)
    snapshots = [
        ('2026-08-30T10:00:00Z', {'Caerleon': (120,110), 'Bridgewatch': (90,80), 'Martlock': (100,95)}),
        ('2026-08-30T11:00:00Z', {'Caerleon': (130,115), 'Bridgewatch': (95,85), 'Martlock': (105,100)}),
        ('2026-08-30T12:00:00Z', {'Caerleon': (140,120), 'Bridgewatch': (100,90), 'Martlock': (110,105)}),
    ]
    for at, cities in snapshots:
        for city, (sell, buy) in cities.items():
            service.save_snapshot(rec(city, sell, buy, at), at)
    return db


def test_profit_calculator_zero_and_configured_costs():
    gross = ProfitCalculator(CostModel()).calculate(900, 1200, 10)
    assert gross['gross_profit'] == 3000
    assert gross['estimated_net_profit'] is None
    net = ProfitCalculator(CostModel(purchase_fee=2, selling_fee=10, transaction_tax=5, transport_cost=100, configured=True)).calculate(900, 1200, 10)
    assert net['estimated_net_profit'] == 2730
    assert net['roi_percent'] == 30.333333333333336


def test_cost_and_profit_validation():
    with pytest.raises(ValueError): CostModel(transport_cost=-1)
    with pytest.raises(ValueError): ProfitCalculator(CostModel()).calculate(0, 100, 1)
    with pytest.raises(ValueError): ProfitCalculator(CostModel()).calculate(100, 120, 0)


def test_arbitrage_lowest_to_highest_and_history(tmp_path):
    ops = ArbitrageService(seed(tmp_path)).opportunities('T4_BAG', 1, quantity=10, cost_model=CostModel(configured=True), sort='spread', limit=20)
    assert ops[0]['buy']['city'] == 'Bridgewatch'
    assert ops[0]['sell']['city'] == 'Caerleon'
    assert ops[0]['profit']['quantity'] == 10
    assert ops[0]['historical']['data_sufficient']
    assert ops[0]['historical']['observations'] == 3


def test_arbitrage_same_city_null_and_invalid_exclusion(tmp_path):
    db = Database(tmp_path/'invalid.db'); s = MarketService(db)
    s.save_snapshot(rec('Caerleon', None, None), '2026-08-30T12:00:00Z')
    s.save_snapshot(rec('Bridgewatch', 100, None), '2026-08-30T12:00:00Z')
    s.save_snapshot(rec('Martlock', -1, None), '2026-08-30T12:00:00Z')
    assert ArbitrageService(db).opportunities('T4_BAG', 1, cost_model=CostModel(configured=True)) == []


def test_cross_server_isolation(tmp_path):
    db = Database(tmp_path/'servers.db'); east = MarketService(db); west = MarketService(db, 'west')
    east.save_snapshot(rec('Caerleon', 100, 90), '2026-08-30T12:00:00Z')
    east.save_snapshot(rec('Bridgewatch', 80, 70), '2026-08-30T12:00:00Z')
    west.save_snapshot(rec('Caerleon', 500, 490, server='west'), '2026-08-30T12:00:00Z')
    west.save_snapshot(rec('Bridgewatch', 100, 90, server='west'), '2026-08-30T12:00:00Z')
    assert all(o['server'] == 'east' for o in ArbitrageService(db, 'east').opportunities('T4_BAG', 1, cost_model=CostModel(configured=True)))


def test_arbitrage_sort_threshold_limit(tmp_path):
    ops = ArbitrageService(seed(tmp_path)).opportunities('T4_BAG', 1, cost_model=CostModel(configured=True), sort='profit', limit=3, min_spread_percent=20)
    assert len(ops) <= 3 and all(o['spread']['percent'] >= 20 for o in ops)
    assert [o['rank'] for o in ops] == list(range(1, len(ops)+1))


def test_freshness_and_missing_cost_model(tmp_path):
    db = Database(tmp_path/'fresh.db'); s = MarketService(db); old = '2026-01-01T00:00:00Z'
    s.save_snapshot(rec('Caerleon', 120, 110, old), old)
    s.save_snapshot(rec('Bridgewatch', 80, 70, old), old)
    ops = ArbitrageService(db).opportunities('T4_BAG', 1, cost_model=CostModel(), freshness_max_age_minutes=0)
    assert ops and ops[0]['status'] == 'stale_data'
    assert ops[0]['data']['freshness'] == 'stale'


def test_arbitrage_calculate_api(tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, 'database', Database(tmp_path/'api.db'))
    client = TestClient(app)
    ok = client.get('/api/arbitrage/calculate', params={'buy_price':9000, 'sell_price':12000, 'quantity':10, 'configured':'true', 'transport_cost':100})
    assert ok.status_code == 200 and ok.json()['profit']['estimated_net_profit'] == 29900
    assert client.get('/api/arbitrage/calculate', params={'buy_price':12000, 'sell_price':9000}).status_code == 400


def test_arbitrage_opportunities_alias_api(tmp_path, monkeypatch):
    import api.main as main
    db = seed(tmp_path); monkeypatch.setattr(main, 'database', db)
    response = TestClient(app).get('/api/arbitrage/opportunities', params={'item_id':'T4_BAG','quality':1,'server':'east'})
    assert response.status_code == 200 and isinstance(response.json()['opportunities'], list)
