from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import SUPPORTED_SERVERS
from db.database import Database
from services.business_strategy import BusinessOpportunity, BusinessStrategy, RiskLevel, StrategyDefinition


@dataclass(frozen=True)
class CraftingMaterial:
    item_id: str
    quantity: float


class CraftingStrategy:
    """Generic market-backed crafting calculator.

    Recipe data is supplied by the caller; no item, recipe, city, or price is
    embedded in the strategy. Missing market inputs produce no fabricated
    opportunity.
    """

    definition = StrategyDefinition(
        strategy_id="crafting",
        name="Crafting",
        description="Evaluate a caller-supplied crafting recipe against live market prices and configurable return/fee inputs.",
        required_data=("market_prices", "recipe", "return_rate", "crafting_fee", "time_required"),
        input_parameters=("server", "city", "output_item_id", "materials", "batch_size", "return_rate", "crafting_fee", "selling_fee", "transaction_tax", "time_minutes", "capital"),
        calculator_key="crafting_strategy",
        risk_level=RiskLevel.MEDIUM,
        liquidity_requirement="output_buy_order_or_market_price",
        time_horizon="short",
    )

    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _price(rows: list[dict[str, Any]], item_id: str, side: str) -> float | None:
        matches = [row for row in rows if row.get("item_id") == item_id]
        if not matches:
            return None
        key = "sell_price_min" if side == "buy" else "buy_price_max"
        values = [row.get(key) for row in matches if row.get(key) is not None]
        return float(values[0]) if values else None

    def evaluate(self, **inputs: Any) -> list[BusinessOpportunity]:
        server = inputs.get("server")
        city = inputs.get("city")
        output_item_id = inputs.get("output_item_id")
        materials_input = inputs.get("materials")
        batch_size = inputs.get("batch_size", 1)
        return_rate = inputs.get("return_rate")
        crafting_fee = inputs.get("crafting_fee", 0.0)
        selling_fee = inputs.get("selling_fee", 0.0)
        transaction_tax = inputs.get("transaction_tax", 0.0)
        time_minutes = inputs.get("time_minutes")
        capital = inputs.get("capital")

        if server not in SUPPORTED_SERVERS or not city or not output_item_id:
            return []
        if not isinstance(materials_input, (list, tuple)) or not materials_input:
            return []
        if batch_size <= 0 or return_rate is None or not 0 <= return_rate < 1:
            return []
        if any(value < 0 for value in (crafting_fee, selling_fee, transaction_tax)):
            return []
        if time_minutes is not None and time_minutes <= 0:
            return []

        materials: list[CraftingMaterial] = []
        for raw in materials_input:
            if isinstance(raw, CraftingMaterial):
                material = raw
            elif isinstance(raw, dict):
                try:
                    material = CraftingMaterial(str(raw["item_id"]), float(raw["quantity"]))
                except (KeyError, TypeError, ValueError):
                    return []
            else:
                return []
            if not material.item_id.strip() or material.quantity <= 0:
                return []
            materials.append(material)

        item_ids = [material.item_id for material in materials] + [output_item_id]
        rows = [row for row in self.database.current_prices(server=server) if row.get("city") == city and row.get("item_id") in item_ids]
        material_cost = 0.0
        for material in materials:
            price = self._price(rows, material.item_id, "buy")
            if price is None or price <= 0:
                return []
            material_cost += price * material.quantity * batch_size

        output_price = self._price(rows, output_item_id, "sell")
        if output_price is None or output_price < 0:
            return []

        upfront_cost = material_cost + crafting_fee * batch_size
        returned_material_value = material_cost * return_rate
        effective_material_cost = material_cost - returned_material_value
        market_fees = (selling_fee + transaction_tax) * output_price * batch_size
        expected_revenue = output_price * batch_size
        expected_cost = effective_material_cost + crafting_fee * batch_size + market_fees
        expected_profit = expected_revenue - expected_cost
        roi = expected_profit / upfront_cost * 100.0 if upfront_cost > 0 else None
        profit_per_hour = expected_profit / (time_minutes / 60.0) if time_minutes else None
        utilization = None if capital is None or capital <= 0 else upfront_cost / capital * 100.0

        confidence = "HIGH"
        if time_minutes is None:
            confidence = "MEDIUM"
        freshness = "unknown"
        timestamps = [row.get("sell_price_min_date") for row in rows] + [row.get("buy_price_max_date") for row in rows]
        timestamps = [value for value in timestamps if value]
        if timestamps:
            freshness = "recent"

        opportunity = BusinessOpportunity(
            strategy_id="crafting",
            title=f"Craft {output_item_id} in {city}",
            server=server,
            location=city,
            required_capital=upfront_cost,
            available_capital=capital,
            capital_utilization_percent=utilization,
            required_quantity=batch_size,
            executable_quantity=batch_size,
            expected_revenue=expected_revenue,
            expected_cost=expected_cost,
            expected_profit=expected_profit,
            roi_percent=roi,
            risk=self.definition.risk_level,
            liquidity="available" if output_price is not None else "unavailable",
            confidence=confidence,
            freshness=freshness,
            time_required=f"{time_minutes} minutes" if time_minutes else None,
            explanation=(
                "Market-backed recipe calculation. Material return rate, station fees, selling costs, "
                "taxes, and time are caller-supplied; no recipe or price is hardcoded."
            ),
        )
        # Profit/hour is not currently a field in the common contract, so keep it
        # available to API consumers without changing the strategy-neutral model.
        result = opportunity.to_dict()
        result["profit_per_hour"] = profit_per_hour
        result["data_sufficient"] = True
        return [result]  # type: ignore[return-value]
