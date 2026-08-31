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
    """Metadata contract for a business strategy.

    Definitions describe what a strategy needs and what it produces. They do
    not contain market-source-specific code. A calculator can be attached by
    a registry key and implemented independently from the API layer.
    """

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
    """Strategy-neutral output contract for future dashboard comparison."""

    strategy_id: str
    title: str
    server: str
    location: str | None = None
    required_capital: float | None = None
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
    """Registry for independently addable strategy definitions/calculators."""

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

    def to_dicts(self) -> list[dict[str, Any]]:
        return [definition.to_dict() for definition in self.definitions()]


def default_strategy_registry() -> StrategyRegistry:
    """Create the metadata registry without coupling strategies to FastAPI.

    Arbitrage is registered as an existing capability. Its calculation remains
    in ArbitrageService; this registry only provides a strategy-neutral
    discovery boundary for future crafting, refining, transport, and trading
    modules.
    """

    registry = StrategyRegistry()
    registry.register_definition(
        StrategyDefinition(
            strategy_id="arbitrage",
            name="City Arbitrage",
            description="Compare city prices and estimate executable cross-city trading opportunities.",
            required_data=("market_prices", "historical_analysis", "liquidity"),
            input_parameters=("server", "item_id", "quality", "quantity", "cost_model"),
            calculator_key="arbitrage_service",
            risk_level=RiskLevel.MEDIUM,
            liquidity_requirement="recent_order_data",
            time_horizon="short",
        )
    )
    return registry
