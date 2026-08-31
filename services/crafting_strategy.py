from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from config import SUPPORTED_SERVERS
from db.database import Database
from services.business_strategy import BusinessOpportunity, RiskLevel, StrategyDefinition
from services.production_rules import ProductionRuleProvider
from services.recipe_data import Recipe, RecipeRepository


@dataclass(frozen=True)
class CraftingMaterial:
    item_id: str
    quantity: float


class CraftingStrategy:
    """Market-backed crafting strategy with normalized recipe storage and scanning."""

    definition = StrategyDefinition(
        strategy_id="crafting",
        name="Crafting",
        description="Scan normalized game recipes against market prices and data-driven production rules.",
        required_data=("recipe_database", "market_prices", "production_rules", "station_fee"),
        input_parameters=("server", "city", "recipe_id", "output_item_id", "batch_size", "capital", "use_focus", "station_fee", "daily_bonus"),
        calculator_key="crafting_strategy",
        risk_level=RiskLevel.MEDIUM,
        liquidity_requirement="recent_market_price",
        time_horizon="short",
    )

    def __init__(
        self,
        database: Database,
        recipe_repository: RecipeRepository | None = None,
        production_rules: ProductionRuleProvider | None = None,
    ):
        self.database = database
        # Legacy callers/tests may provide a lightweight database-like object that
        # has current_prices() but no filesystem path. Recipe-backed scanning is
        # unavailable in that case, while caller-supplied recipe evaluation remains
        # fully compatible.
        if recipe_repository is not None:
            self.recipes = recipe_repository
        elif hasattr(database, "path"):
            self.recipes = RecipeRepository(database)
        else:
            self.recipes = None
        self.production_rules = production_rules or ProductionRuleProvider(
            Path(__file__).resolve().parent.parent / "data" / "production_rules.json"
        )

    @staticmethod
    def _price(rows: list[dict[str, Any]], item_id: str, side: str) -> float | None:
        matches = [r for r in rows if r.get("item_id") == item_id]
        if not matches:
            return None
        key = "sell_price_min" if side == "buy" else "buy_price_max"
        values = [r.get(key) for r in matches if r.get(key) is not None]
        return float(values[0]) if values else None

    @staticmethod
    def _freshness(rows: list[dict[str, Any]]) -> str:
        return "recent" if any(r.get("sell_price_min_date") or r.get("buy_price_max_date") for r in rows) else "unknown"

    def _evaluate_recipe(
        self,
        recipe: Recipe,
        *,
        server: str,
        city: str,
        batch_size: int,
        capital: float | None,
        use_focus: bool,
        station_fee: float | None,
        selling_fee: float,
        transaction_tax: float,
        daily_bonus: float | None,
    ) -> BusinessOpportunity | None:
        if station_fee is None or batch_size <= 0 or self.recipes is None:
            return None
        rule = self.production_rules.find(server=server, city=city, category=recipe.category, tier=recipe.tier)
        if rule is None:
            return None
        if recipe.specialty_city != city:
            rule = replace(rule, specialty_production_bonus=0.0)
        return_rate = rule.return_rate(use_focus=use_focus, daily_bonus=daily_bonus)
        if return_rate is None:
            return None

        ids = [m.item_id for m in recipe.materials] + [recipe.output_item_id]
        rows = [
            r for r in self.database.current_prices(server=server)
            if r.get("city") == city and r.get("item_id") in ids
        ]
        material_cost = 0.0
        for material in recipe.materials:
            price = self._price(rows, material.item_id, "buy")
            if price is None or price <= 0:
                return None
            effective_quantity = material.quantity - (material.quantity * return_rate if material.returnable else 0)
            material_cost += effective_quantity * price * batch_size

        output_price = self._price(rows, recipe.output_item_id, "sell")
        if output_price is None or output_price <= 0:
            return None
        produced = recipe.output_quantity * batch_size
        revenue = produced * output_price
        craft_fee = station_fee * produced
        market_fee = (selling_fee + transaction_tax) * revenue
        expected_cost = material_cost + craft_fee + market_fee
        profit = revenue - expected_cost
        upfront = sum((self._price(rows, m.item_id, "buy") or 0) * m.quantity for m in recipe.materials) * batch_size + craft_fee
        roi = profit / upfront * 100 if upfront > 0 else None
        minutes = recipe.crafting_time_minutes
        profit_hour = profit / (minutes * batch_size / 60) if minutes and minutes > 0 else None
        utilization = None if capital is None or capital <= 0 else upfront / capital * 100
        focus = recipe.focus_cost * batch_size if use_focus and recipe.focus_cost is not None else (0.0 if not use_focus else None)
        confidence = "HIGH" if focus is not None and minutes is not None else "MEDIUM"
        return BusinessOpportunity(
            strategy_id="crafting",
            title=f"Craft {recipe.output_item_id} in {city}",
            server=server,
            location=city,
            required_capital=upfront,
            available_capital=capital,
            capital_utilization_percent=utilization,
            required_quantity=batch_size,
            executable_quantity=produced,
            expected_revenue=revenue,
            expected_cost=expected_cost,
            expected_profit=profit,
            roi_percent=roi,
            profit_per_hour=profit_hour,
            risk=self.definition.risk_level,
            liquidity="available",
            confidence=confidence,
            freshness=self._freshness(rows),
            time_required=f"{minutes * batch_size:.2f} minutes" if minutes else None,
            explanation="Normalized recipe + market calculation; station fee is an explicit analysis input."
            + (f" Focus required: {focus:.0f}." if focus is not None else " Focus cost unavailable."),
        )

    def _legacy_evaluate(self, **inputs: Any) -> list[BusinessOpportunity]:
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
        if server not in SUPPORTED_SERVERS or not city or not output_item_id or not isinstance(materials_input, (list, tuple)) or not materials_input:
            return []
        if isinstance(batch_size, bool) or batch_size <= 0 or return_rate is None or not 0 <= return_rate < 1:
            return []
        materials = []
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
        ids = [m.item_id for m in materials] + [output_item_id]
        rows = [r for r in self.database.current_prices(server=server) if r.get("city") == city and r.get("item_id") in ids]
        material_cost = 0
        for material in materials:
            price = self._price(rows, material.item_id, "buy")
            if price is None or price <= 0:
                return []
            material_cost += price * material.quantity * batch_size
        output_price = self._price(rows, output_item_id, "sell")
        if output_price is None or output_price < 0:
            return []
        upfront = material_cost + crafting_fee * batch_size
        effective = material_cost * (1 - return_rate)
        fees = (selling_fee + transaction_tax) * output_price * batch_size
        revenue = output_price * batch_size
        cost = effective + crafting_fee * batch_size + fees
        profit = revenue - cost
        roi = profit / upfront * 100 if upfront > 0 else None
        profit_hour = profit / (time_minutes / 60) if time_minutes else None
        utilization = None if capital is None or capital <= 0 else upfront / capital * 100
        return [BusinessOpportunity(
            strategy_id="crafting",
            title=f"Craft {output_item_id} in {city}",
            server=server,
            location=city,
            required_capital=upfront,
            available_capital=capital,
            capital_utilization_percent=utilization,
            required_quantity=batch_size,
            executable_quantity=batch_size,
            expected_revenue=revenue,
            expected_cost=cost,
            expected_profit=profit,
            roi_percent=roi,
            profit_per_hour=profit_hour,
            risk=self.definition.risk_level,
            liquidity="available",
            confidence="MEDIUM",
            freshness=self._freshness(rows),
            time_required=f"{time_minutes} minutes" if time_minutes else None,
            explanation="Legacy caller-supplied recipe calculation retained for compatibility.",
        )]

    def evaluate(self, **inputs: Any) -> list[BusinessOpportunity]:
        if inputs.get("materials") is not None:
            return self._legacy_evaluate(**inputs)
        server = inputs.get("server")
        city = inputs.get("city")
        capital = inputs.get("capital")
        if server not in SUPPORTED_SERVERS or not city or self.recipes is None:
            return []
        batch_size = int(inputs.get("batch_size", 1))
        use_focus = bool(inputs.get("use_focus", False))
        station_fee = inputs.get("station_fee", inputs.get("crafting_fee"))
        selling_fee = float(inputs.get("selling_fee", 0))
        transaction_tax = float(inputs.get("transaction_tax", 0))
        daily_bonus = inputs.get("daily_bonus")
        recipe_id = inputs.get("recipe_id") or inputs.get("output_item_id")
        if recipe_id:
            recipe = self.recipes.get(str(recipe_id))
            if recipe is None:
                return []
            item = self._evaluate_recipe(
                recipe, server=server, city=city, batch_size=batch_size, capital=capital,
                use_focus=use_focus, station_fee=station_fee, selling_fee=selling_fee,
                transaction_tax=transaction_tax, daily_bonus=daily_bonus,
            )
            return [item] if item else []
        recipes = self.recipes.list(tier=inputs.get("tier"), category=inputs.get("category"), limit=inputs.get("scan_limit"))
        opportunities = []
        for recipe in recipes:
            cities = [recipe.specialty_city] if recipe.specialty_city else [city]
            for craft_city in cities:
                if craft_city != city and not inputs.get("scan_all_cities"):
                    continue
                opportunity = self._evaluate_recipe(
                    recipe, server=server, city=craft_city, batch_size=batch_size, capital=capital,
                    use_focus=use_focus, station_fee=station_fee, selling_fee=selling_fee,
                    transaction_tax=transaction_tax, daily_bonus=daily_bonus,
                )
                if opportunity is None:
                    continue
                if inputs.get("min_profit") is not None and (opportunity.expected_profit or 0) < inputs["min_profit"]:
                    continue
                if inputs.get("min_roi") is not None and (opportunity.roi_percent or 0) < inputs["min_roi"]:
                    continue
                if capital is not None and opportunity.required_capital is not None and opportunity.required_capital > capital:
                    continue
                opportunities.append(opportunity)
        return opportunities
