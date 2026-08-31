from __future__ import annotations

from typing import Any

from services.business_strategy import BusinessOpportunity, RiskLevel, StrategyRegistry


class StrategyEngine:
    """Application service for discovering, evaluating, filtering and ranking strategies."""

    SORT_KEYS = {"profit", "roi", "capital_efficiency", "capital", "risk", "confidence", "freshness"}
    RISK_ORDER = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3, RiskLevel.UNKNOWN: 99}
    CONFIDENCE_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNAVAILABLE": 0}

    def __init__(self, registry: StrategyRegistry):
        self.registry = registry

    def definitions(self) -> list[dict[str, Any]]:
        return self.registry.to_dicts()

    def evaluate(
        self,
        strategy_id: str | None = None,
        capital: float | None = None,
        risk: str | None = None,
        sort: str = "profit",
        limit: int = 20,
        **inputs: Any,
    ) -> list[BusinessOpportunity]:
        if capital is not None and capital <= 0:
            raise ValueError("capital must be greater than zero")
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if sort not in self.SORT_KEYS:
            raise ValueError("sort must be one of: profit, roi, capital_efficiency, capital, risk, confidence, freshness")
        if risk is not None:
            try:
                risk_level = RiskLevel(risk.lower())
            except ValueError as exc:
                raise ValueError("risk must be one of: low, medium, high, unknown") from exc
        else:
            risk_level = None

        strategies = [self.registry.get(strategy_id)] if strategy_id else list(self.registry.strategies())
        if strategy_id and strategies[0] is None:
            raise KeyError(f"unknown strategy: {strategy_id}")
        opportunities: list[BusinessOpportunity] = []
        for strategy in strategies:
            opportunities.extend(strategy.evaluate(capital=capital, **inputs))

        filtered: list[BusinessOpportunity] = []
        for opportunity in opportunities:
            if capital is not None and opportunity.required_capital is not None and opportunity.required_capital > capital:
                continue
            if risk_level is not None and opportunity.risk != risk_level:
                continue
            filtered.append(opportunity)

        def score(item: BusinessOpportunity) -> float:
            if sort == "profit":
                return item.expected_profit if item.expected_profit is not None else float("-inf")
            if sort == "roi":
                return item.roi_percent if item.roi_percent is not None else float("-inf")
            if sort == "capital":
                return -(item.required_capital if item.required_capital is not None else float("inf"))
            if sort == "capital_efficiency":
                if item.expected_profit is None or not item.required_capital:
                    return float("-inf")
                return item.expected_profit / item.required_capital
            if sort == "risk":
                return -self.RISK_ORDER[item.risk]
            if sort == "confidence":
                return self.CONFIDENCE_ORDER.get(item.confidence.upper(), 0)
            if sort == "freshness":
                value = item.freshness.lower()
                return {"fresh": 3, "recent": 2, "stale": 1, "unknown": 0, "unavailable": 0}.get(value, 0)
            return float("-inf")

        filtered.sort(key=score, reverse=True)
        return filtered[:limit]
