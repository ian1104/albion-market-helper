from types import SimpleNamespace

from services.business_strategy import default_strategy_registry
from services.crafting_strategy import CraftingStrategy


class FakeDatabase:
    def __init__(self, rows):
        self.rows = rows

    def current_prices(self, item_id=None, city=None, quality=None, server=None):
        return self.rows


def test_crafting_calculates_from_supplied_recipe_and_market_prices():
    db = FakeDatabase([
        {"item_id": "mat-a", "city": "Bridgewatch", "sell_price_min": 100, "buy_price_max": 90, "sell_price_min_date": "2026-08-31T10:00:00+00:00", "buy_price_max_date": "2026-08-31T10:00:00+00:00"},
        {"item_id": "output-a", "city": "Bridgewatch", "sell_price_min": 200, "buy_price_max": 180, "sell_price_min_date": "2026-08-31T10:00:00+00:00", "buy_price_max_date": "2026-08-31T10:00:00+00:00"},
    ])
    strategy = CraftingStrategy(db)
    result = strategy.evaluate(
        server="east", city="Bridgewatch", output_item_id="output-a",
        materials=[{"item_id": "mat-a", "quantity": 2}], batch_size=10,
        return_rate=0.25, crafting_fee=10, selling_fee=0.01, transaction_tax=0.02,
        time_minutes=30, capital=5000,
    )
    assert len(result) == 1
    opportunity = result[0]
    assert opportunity.expected_revenue == 1800
    assert opportunity.required_capital == 2010
    assert opportunity.expected_profit == 126.0
    assert opportunity.roi_percent is not None
    assert opportunity.profit_per_hour == 252.0
    assert opportunity.server == "east"


def test_crafting_returns_no_opportunity_when_market_input_is_missing():
    strategy = CraftingStrategy(FakeDatabase([]))
    result = strategy.evaluate(
        server="east", city="Bridgewatch", output_item_id="output-a",
        materials=[{"item_id": "mat-a", "quantity": 2}], batch_size=10, return_rate=0.25,
        crafting_fee=10, selling_fee=0, transaction_tax=0, time_minutes=30,
    )
    assert result == []


def test_default_registry_infers_database_from_arbitrage_service():
    database = object()
    service = SimpleNamespace(database=database)
    registry = default_strategy_registry(service)
    assert registry.get_definition("crafting") is not None
    assert registry.get("crafting") is not None
