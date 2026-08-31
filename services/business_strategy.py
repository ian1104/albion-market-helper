from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StrategyDefinition:
    """Metadata contract for an independently executable business strategy."""

    strategy_id: str
    name: str
    description: str
    required_data: tuple[str, ...] = ()
    input_parameters: tuple[str, ...] = ()
    calculator_key: str | None = None
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    capital_requirement: float | None = None
    liquidity_requirement: str | None = None
    time_horizon: str | None = None
    server_scope: tuple[str, ...] = ()
    location_scope: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id is required")
        if not self.name.strip():
            raise ValueError("name is required")
        if self.capital_requirement is not None and self.capital_requirement < 0:
            raise ValueError("capital_requirement must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["risk_level"] = self.risk_level.value
        return result


@dataclass(frozen=True)
class BusinessOpportunity:
    """Strategy-neutral result contract used by the dashboard/application layer."""

    strategy_id: str
    title: str
    server: str
    location: str | None = None
    required_capital: float | None = None
    available_capital: float | None = None
    capital_utilization_percent: float | None = None
    required_quantity: float | None = None
    executable_quantity: float | None = None
    expected_revenue: float | None = None
    expected_cost: float | None = None
    expected_profit: float | None = None
    roi_percent: float | None = None
    risk: RiskLevel = RiskLevel.UNKNOWN
    liquidity: str | None = None
    confidence: str = "UNAVAILABLE"
    freshness: str = "unknown"
    time_required: str | None = None
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["risk"] = self.risk.value
        return result


class BusinessStrategy(Protocol):
    @property
    def definition(self) -> StrategyDefinition:
        ...

    def evaluate(self, **inputs: Any) -> list[BusinessOpportunity]:
        ...


@dataclass
class StrategyRegistry:
    """Registry for independently addable strategy implementations."""

    _definitions: dict[str, StrategyDefinition] = field(default_factory=dict)
    _strategies: dict[str, BusinessStrategy] = field(default_factory=dict)

    def register_definition(self, definition: StrategyDefinition) -> None:
        existing = self._definitions.get(definition.strategy_id)
        if existing is not None and existing != definition:
            raise ValueError(f"strategy already registered: {definition.strategy_id}")
        self._definitions[definition.strategy_id] = definition

    def register(self, strategy: BusinessStrategy) -> None:
        self.register_definition(strategy.definition)
        existing = self._strategies.get(strategy.definition.strategy_id)
        if existing is not None and existing is not strategy:
            raise ValueError(f"strategy already registered: {strategy.definition.strategy_id}")
        self._strategies[strategy.definition.strategy_id] = strategy

    def get_definition(self, strategy_id: str) -> StrategyDefinition | None:
        return self._definitions.get(strategy_id)

    def get(self, strategy_id: str) -> BusinessStrategy | None:
        return self._strategies.get(strategy_id)

    def definitions(self) -> tuple[StrategyDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def strategies(self) -> tuple[BusinessStrategy, ...]:
        return tuple(self._strategies[key] for key in sorted(self._strategies))

    def to_dicts(self) -> list[dict[str, Any]]:
        return [definition.to_dict() for definition in self.definitions()]


class ArbitrageStrategy:
    """Strategy adapter that delegates all arbitrage calculations to ArbitrageService."""

    definition = StrategyDefinition(
        strategy_id="arbitrage",
        name="City Arbitrage",
        description="Compare city prices and estimate executable cross-city trading opportunities.",
        required_data=("market_prices", "historical_analysis", "liquidity"),
        input_parameters=("server", "item_id", "quality", "quantity", "cost_model", "capital"),
        calculator_key="arbitrage_service",
        risk_level=RiskLevel.MEDIUM,
        liquidity_requirement="recent_order_data",
        time_horizon="short",
    )

    def __init__(self, arbitrage_service: Any):
        self._service = arbitrage_service

    def evaluate(self, **inputs: Any) -> list[BusinessOpportunity]:
        service = self._service
        requested_server = inputs.get("server")
        if requested_server and getattr(service, "server", None) != requested_server:
            provider = getattr(service, "liquidity_provider", None)
            service = type(service)(service.database, requested_server, provider)
        opportunities = service.opportunities(
            item_id=inputs.get("item_id"),
            quality=inputs.get("quality", 1),
            quantity=inputs.get("quantity", 1),
            min_spread_percent=inputs.get("min_spread_percent"),
            min_roi=inputs.get("min_roi"),
            min_profit=inputs.get("min_profit"),
            sort=inputs.get("source_sort", "roi"),
            limit=inputs.get("source_limit", 100),
            cost_model=inputs.get("cost_model"),
            freshness_max_age_minutes=inputs.get("freshness_max_age_minutes", 30.0),
            historical_range_start=inputs.get("historical_range_start"),
            historical_range_end=inputs.get("historical_range_end"),
        )
        capital = inputs.get("capital")
        result: list[BusinessOpportunity] = []
        for opportunity in opportunities:
            buy = opportunity["buy"]
            sell = opportunity["sell"]
            realistic = opportunity["realistic_profit"]
            executable = opportunity["liquidity"].get("executable_quantity")
            quantity = opportunity["liquidity"].get("requested_quantity")
            execution_price = realistic.get("buy_execution_price")
            required_capital = (execution_price if execution_price is not None else buy["price"]) * (executable if executable is not None else quantity)
            profit = realistic.get("net_profit") if realistic.get("status") == "available" else opportunity["profit"].get("estimated_net_profit")
            revenue = None
            cost = None
            if realistic.get("status") == "available":
                qty = realistic.get("quantity")
                revenue = realistic.get("sell_execution_price") * qty
                cost = realistic.get("buy_execution_price") * qty
            elif opportunity["profit"].get("estimated_net_profit") is not None:
                qty = quantity
                revenue = sell["price"] * qty
                cost = buy["price"] * qty
            utilization = None if capital is None or capital <= 0 else required_capital / capital * 100.0
            liquidity_status = "available" if opportunity["liquidity"]["buy"]["status"] == "available" and opportunity["liquidity"]["sell"]["status"] == "available" else "unavailable"
            result.append(BusinessOpportunity(
                strategy_id="arbitrage",
                title=f"{opportunity['item_id']}: {buy['city']} → {sell['city']}",
                server=opportunity["server"],
                location=f"{buy['city']} → {sell['city']}",
                required_capital=required_capital,
                available_capital=capital,
                capital_utilization_percent=utilization,
                required_quantity=quantity,
                executable_quantity=executable,
                expected_revenue=revenue,
                expected_cost=cost,
                expected_profit=profit,
                roi_percent=realistic.get("roi_percent") if realistic.get("status") == "available" else opportunity["profit"].get("roi_percent"),
                risk=self.definition.risk_level,
                liquidity=liquidity_status,
                confidence=opportunity.get("confidence", "UNAVAILABLE"),
                freshness=opportunity.get("data", {}).get("freshness", "unknown"),
                time_required=self.definition.time_horizon,
                explanation="Existing ArbitrageService result adapted to the strategy-neutral opportunity contract.",
            ))
        return result


def default_strategy_registry(arbitrage_service: Any | None = None) -> StrategyRegistry:
    """Build the registry; when a service is supplied, arbitrage is executable."""

    registry = StrategyRegistry()
    if arbitrage_service is not None:
        registry.register(ArbitrageStrategy(arbitrage_service))
    else:
        registry.register_definition(ArbitrageStrategy.definition)
    return registry
