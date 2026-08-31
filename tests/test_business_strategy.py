from services.business_strategy import BusinessOpportunity, RiskLevel, StrategyDefinition, StrategyRegistry, default_strategy_registry


def test_strategy_definition_is_serializable():
    definition = StrategyDefinition(
        strategy_id="test",
        name="Test Strategy",
        description="test",
        required_data=("prices",),
        input_parameters=("capital",),
        risk_level=RiskLevel.LOW,
        capital_requirement=100.0,
    )
    data = definition.to_dict()
    assert data["strategy_id"] == "test"
    assert data["risk_level"] == "low"
    assert data["required_data"] == ("prices",)


def test_registry_rejects_conflicting_definition():
    registry = StrategyRegistry()
    registry.register_definition(StrategyDefinition("x", "X", "one"))
    try:
        registry.register_definition(StrategyDefinition("x", "X", "two"))
    except ValueError as exc:
        assert "strategy already registered" in str(exc)
    else:
        raise AssertionError("conflicting strategy definition was accepted")


def test_default_registry_exposes_arbitrage_without_duplicating_calculation():
    registry = default_strategy_registry()
    definition = registry.get_definition("arbitrage")
    assert definition is not None
    assert definition.calculator_key == "arbitrage_service"
    assert "liquidity" in definition.required_data


def test_business_opportunity_is_strategy_neutral():
    opportunity = BusinessOpportunity(
        strategy_id="crafting",
        title="Example",
        server="east",
        expected_profit=1000,
        roi_percent=10,
        risk=RiskLevel.HIGH,
    )
    data = opportunity.to_dict()
    assert data["strategy_id"] == "crafting"
    assert data["risk"] == "high"
    assert data["expected_profit"] == 1000
