from services.business_strategy import BusinessOpportunity, RiskLevel, StrategyDefinition, StrategyRegistry
from services.strategy_engine import StrategyEngine


class _TestStrategy:
    definition = StrategyDefinition(
        strategy_id="future_test",
        name="Future Test",
        description="Architecture-only strategy used to verify registry discovery.",
        calculator_key="test",
        risk_level=RiskLevel.LOW,
    )

    def evaluate(self, **inputs):
        capital = inputs.get("capital")
        return [BusinessOpportunity(
            strategy_id="future_test",
            title="Architecture test opportunity",
            server=inputs.get("server", "east"),
            required_capital=100,
            available_capital=capital,
            expected_profit=25,
            roi_percent=25,
            risk=RiskLevel.LOW,
            confidence="HIGH",
            freshness="fresh",
        )]


def test_dashboard_strategy_discovery_and_engine_filtering():
    registry = StrategyRegistry()
    registry.register(_TestStrategy())
    engine = StrategyEngine(registry)

    definitions = engine.definitions()
    assert [item["strategy_id"] for item in definitions] == ["future_test"]

    opportunities = engine.evaluate(server="east", capital=200, sort="profit", limit=10)
    assert len(opportunities) == 1
    assert opportunities[0].strategy_id == "future_test"
    assert opportunities[0].expected_profit == 25


def test_dashboard_capital_filter_excludes_unaffordable_opportunity():
    registry = StrategyRegistry()
    registry.register(_TestStrategy())
    engine = StrategyEngine(registry)

    assert engine.evaluate(server="east", capital=99, sort="profit", limit=10) == []


def test_unknown_profit_is_not_ranked_as_zero():
    class UnknownProfitStrategy(_TestStrategy):
        definition = StrategyDefinition(
            strategy_id="unknown_profit",
            name="Unknown Profit",
            description="Test unknown values.",
            calculator_key="test",
            risk_level=RiskLevel.UNKNOWN,
        )

        def evaluate(self, **inputs):
            return [BusinessOpportunity(
                strategy_id="unknown_profit",
                title="Unknown",
                server="east",
                required_capital=1,
                expected_profit=None,
                roi_percent=None,
                confidence="UNAVAILABLE",
                freshness="unknown",
            )]

    registry = StrategyRegistry()
    registry.register(UnknownProfitStrategy())
    engine = StrategyEngine(registry)
    result = engine.evaluate(server="east", sort="profit", limit=10)
    assert len(result) == 1
    assert result[0].expected_profit is None
