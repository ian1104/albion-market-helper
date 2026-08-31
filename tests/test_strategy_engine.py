from services.business_strategy import BusinessOpportunity, RiskLevel, StrategyDefinition, StrategyRegistry
from services.strategy_engine import StrategyEngine


class StubStrategy:
    definition = StrategyDefinition("stub", "Stub", "test", risk_level=RiskLevel.LOW)

    def __init__(self, opportunities):
        self._opportunities = opportunities

    def evaluate(self, **inputs):
        return [
            BusinessOpportunity(
                **{**opportunity.to_dict(), "risk": opportunity.risk}
            ) for opportunity in self._opportunities
        ]


def registry_with(*opportunities):
    registry = StrategyRegistry()
    registry.register(StubStrategy(opportunities))
    return registry


def test_strategy_discovery_and_execution():
    opportunity = BusinessOpportunity("stub", "One", "east", expected_profit=500, roi_percent=10, required_capital=1000)
    engine = StrategyEngine(registry_with(opportunity))
    assert engine.definitions()[0]["strategy_id"] == "stub"
    assert engine.evaluate(strategy_id="stub")[0].expected_profit == 500


def test_capital_filtering_and_utilization_are_preserved():
    affordable = BusinessOpportunity("stub", "Affordable", "east", expected_profit=100, required_capital=500)
    expensive = BusinessOpportunity("stub", "Expensive", "east", expected_profit=900, required_capital=5000)
    engine = StrategyEngine(registry_with(affordable, expensive))
    result = engine.evaluate(capital=1000)
    assert [item.title for item in result] == ["Affordable"]


def test_profit_ranking_does_not_turn_unknown_profit_into_zero():
    known = BusinessOpportunity("stub", "Known", "east", expected_profit=100)
    unknown = BusinessOpportunity("stub", "Unknown", "east", expected_profit=None)
    result = StrategyEngine(registry_with(unknown, known)).evaluate(sort="profit")
    assert [item.title for item in result] == ["Known", "Unknown"]


def test_risk_filtering_and_invalid_inputs():
    low = BusinessOpportunity("stub", "Low", "east", expected_profit=10, risk=RiskLevel.LOW)
    high = BusinessOpportunity("stub", "High", "east", expected_profit=20, risk=RiskLevel.HIGH)
    engine = StrategyEngine(registry_with(low, high))
    assert [item.title for item in engine.evaluate(risk="low")] == ["Low"]
    try:
        engine.evaluate(capital=0)
    except ValueError as exc:
        assert "capital" in str(exc)
    else:
        raise AssertionError("invalid capital was accepted")
