from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from typing import Any

from config import ALBION_SERVER, FRESH_DATA_MAX_AGE_MINUTES, SUPPORTED_SERVERS
from db.database import Database
from services.liquidity import DatabaseLiquidityProvider, LiquidityProvider, executable_quantity


@dataclass(frozen=True)
class CostModel:
    purchase_fee: float = 0.0
    selling_fee: float = 0.0
    transaction_tax: float = 0.0
    transport_cost: float = 0.0
    safety_buffer: float = 0.0
    configured: bool = False

    def __post_init__(self) -> None:
        for name in ("purchase_fee", "selling_fee", "transaction_tax", "transport_cost", "safety_buffer"):
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be >= 0")

    @property
    def total_fixed_cost(self) -> float:
        return self.purchase_fee + self.selling_fee + self.transaction_tax + self.transport_cost + self.safety_buffer

    def validate(self) -> None:
        self.__post_init__()


@dataclass(frozen=True)
class ProfitCalculator:
    cost_model: CostModel

    def calculate(self, buy_price: float, sell_price: float, quantity: int) -> dict[str, float | int | None]:
        if buy_price <= 0 or sell_price < 0:
            raise ValueError("prices must be non-negative and buy_price must be greater than zero")
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        gross_revenue = sell_price * quantity
        purchase_cost = buy_price * quantity
        gross_profit = (sell_price - buy_price) * quantity
        if not self.cost_model.configured:
            return {
                "quantity": quantity, "buy_price": buy_price, "sell_price": sell_price,
                "gross_revenue": gross_revenue, "purchase_cost": purchase_cost, "gross_profit": gross_profit,
                "fees": None, "transport_cost": None, "estimated_net_profit": None,
                "profit_per_unit": None, "gross_roi_percent": gross_profit / purchase_cost * 100.0,
                "roi_percent": None, "cost_model_configured": False,
            }
        fees = (self.cost_model.purchase_fee + self.cost_model.selling_fee + self.cost_model.transaction_tax) * quantity
        transport = self.cost_model.transport_cost
        safety = self.cost_model.safety_buffer
        net = gross_profit - fees - transport - safety
        return {
            "quantity": quantity, "buy_price": buy_price, "sell_price": sell_price,
            "gross_revenue": gross_revenue, "purchase_cost": purchase_cost, "gross_profit": gross_profit,
            "fees": fees, "transport_cost": transport, "estimated_net_profit": net,
            "profit_per_unit": net / quantity, "gross_roi_percent": gross_profit / purchase_cost * 100.0,
            "roi_percent": net / purchase_cost * 100.0, "cost_model_configured": True,
        }


class ArbitrageService:
    def __init__(self, database: Database, server: str = ALBION_SERVER, liquidity_provider: LiquidityProvider | None = None):
        if server not in SUPPORTED_SERVERS:
            raise ValueError(f"unsupported server: {server}")
        self.database = database
        self.server = server
        self.liquidity_provider = liquidity_provider or DatabaseLiquidityProvider(database)
        database.initialize()

    @staticmethod
    def _parse_ts(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None

    def _freshness(self, *timestamps: str | None, max_age_minutes: float = FRESH_DATA_MAX_AGE_MINUTES) -> dict[str, Any]:
        parsed = [self._parse_ts(x) for x in timestamps]
        parsed = [x for x in parsed if x is not None]
        if len(parsed) != len([x for x in timestamps if x is not None]) or not parsed:
            return {"status": "unknown", "age_minutes": None}
        age = max(0.0, (datetime.now(timezone.utc) - min(parsed)).total_seconds() / 60.0)
        return {"status": "fresh" if age <= max_age_minutes else "stale", "age_minutes": age}

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("quantity must be greater than zero")

    def _current_rows(self, item_id: str | None, quality: int) -> list[dict[str, Any]]:
        return self.database.current_prices(item_id=item_id, quality=quality, server=self.server)

    @staticmethod
    def _confidence(freshness: dict[str, Any], historical: dict[str, Any], buy_liquidity: dict[str, Any], sell_liquidity: dict[str, Any]) -> str:
        if freshness["status"] in {"stale", "unknown"}:
            return "LOW"
        if not historical["data_sufficient"] or buy_liquidity["status"] != "available" or sell_liquidity["status"] != "available":
            return "MEDIUM"
        return "HIGH"

    def _historical_pair(self, item_id: str, quality: int, buy_city: str, sell_city: str, range_start: str | None = None, range_end: str | None = None) -> dict[str, Any]:
        rows = self.database.history(item_id, None, quality, range_start, range_end, server=self.server)
        by_time: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            by_time.setdefault(row["recorded_at"], {})[row["city"]] = row
        spreads: list[float] = []
        for snapshot in by_time.values():
            buy = snapshot.get(buy_city)
            sell = snapshot.get(sell_city)
            if not buy or not sell:
                continue
            buy_price = buy.get("sell_price_min")
            sell_price = sell.get("buy_price_max")
            if buy_price is None or sell_price is None or buy_price <= 0 or sell_price < 0:
                continue
            spreads.append(float(sell_price - buy_price))
        if len(spreads) < 2:
            return {"data_sufficient": False, "observations": len(spreads), "average_spread": None, "minimum_spread": None, "maximum_spread": None, "spread_volatility": None, "positive_spread_ratio": None}
        mean = sum(spreads) / len(spreads)
        volatility = sqrt(sum((x - mean) ** 2 for x in spreads) / len(spreads))
        return {"data_sufficient": True, "observations": len(spreads), "average_spread": mean, "minimum_spread": min(spreads), "maximum_spread": max(spreads), "spread_volatility": volatility, "positive_spread_ratio": sum(x > 0 for x in spreads) / len(spreads) * 100.0}

    def _liquidity(self, item_id: str, city: str, quality: int) -> dict[str, Any]:
        snapshot = self.liquidity_provider.get(self.server, item_id, city, quality)
        if snapshot is None or not snapshot.available:
            return {"status": "unavailable", "available_buy_quantity": None, "available_sell_quantity": None, "buy_depth": (), "sell_depth": (), "source": None}
        return {"status": "available", "available_buy_quantity": snapshot.buy_quantity, "available_sell_quantity": snapshot.sell_quantity, "buy_depth": snapshot.buy_depth, "sell_depth": snapshot.sell_depth, "source": snapshot.source}

    def opportunities(self, item_id: str | None = None, quality: int = 1, quantity: int = 1, min_spread_percent: float | None = None, min_roi: float | None = None, min_profit: float | None = None, sort: str = "roi", limit: int = 20, cost_model: CostModel | None = None, freshness_max_age_minutes: float = FRESH_DATA_MAX_AGE_MINUTES, historical_range_start: str | None = None, historical_range_end: str | None = None) -> list[dict[str, Any]]:
        self._validate_quantity(quantity)
        if quality < 1 or limit < 1:
            raise ValueError("quality and limit must be positive")
        for name, value in (("min_spread_percent", min_spread_percent), ("min_roi", min_roi), ("min_profit", min_profit)):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0")
        if freshness_max_age_minutes < 0:
            raise ValueError("freshness_max_age_minutes must be >= 0")
        if sort not in {"profit", "roi", "spread", "stability", "freshness", "confidence"}:
            raise ValueError("sort must be one of: profit, roi, spread, stability, freshness, confidence")
        cost_model = cost_model or CostModel()
        rows = self._current_rows(item_id, quality)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["item_id"], []).append(row)
        result: list[dict[str, Any]] = []
        for current_item, item_rows in grouped.items():
            usable_buy = [r for r in item_rows if r.get("sell_price_min") is not None and r["sell_price_min"] > 0]
            usable_sell = [r for r in item_rows if r.get("buy_price_max") is not None and r["buy_price_max"] >= 0]
            for buy, sell in ((a, b) for a in usable_buy for b in usable_sell if a["city"] != b["city"]):
                buy_price = float(buy["sell_price_min"]); sell_price = float(sell["buy_price_max"])
                if sell_price <= buy_price: continue
                spread = sell_price - buy_price; spread_pct = spread / buy_price * 100.0
                profit = ProfitCalculator(cost_model).calculate(buy_price, sell_price, quantity)
                net_profit = profit["estimated_net_profit"]; roi = profit["roi_percent"]
                if min_spread_percent is not None and spread_pct < min_spread_percent: continue
                roi_for_filter = roi if roi is not None else profit["gross_roi_percent"]
                if min_roi is not None and roi_for_filter < min_roi: continue
                if min_profit is not None and (net_profit if net_profit is not None else float("-inf")) < min_profit: continue
                freshness = self._freshness(buy.get("sell_price_min_date"), sell.get("buy_price_max_date"), max_age_minutes=freshness_max_age_minutes)
                historical = self._historical_pair(current_item, quality, buy["city"], sell["city"], historical_range_start, historical_range_end)
                buy_liquidity = self._liquidity(current_item, buy["city"], quality); sell_liquidity = self._liquidity(current_item, sell["city"], quality)
                executable = executable_quantity(quantity, buy_liquidity["available_buy_quantity"], sell_liquidity["available_sell_quantity"])
                confidence = self._confidence(freshness, historical, buy_liquidity, sell_liquidity)
                realistic = {"status": "unavailable", "quantity": None, "buy_execution_price": None, "sell_execution_price": None, "net_profit": None, "roi_percent": None}
                slippage = {"status": "unavailable", "buy_percent": None, "sell_percent": None, "total_percent": None}
                if executable is not None and executable > 0:
                    buy_execution = buy_price; sell_execution = sell_price
                    buy_depth = buy_liquidity.get("buy_depth") or (); sell_depth = sell_liquidity.get("sell_depth") or ()
                    if buy_depth and sell_depth:
                        from services.liquidity import slippage_percent, weighted_average_execution_price
                        weighted_buy = weighted_average_execution_price(buy_depth, executable); weighted_sell = weighted_average_execution_price(sell_depth, executable)
                        if weighted_buy is not None and weighted_sell is not None:
                            buy_execution = weighted_buy; sell_execution = weighted_sell
                            buy_slip = slippage_percent(buy_price, buy_execution, "buy"); sell_slip = slippage_percent(sell_price, sell_execution, "sell")
                            slippage = {"status": "available", "buy_percent": buy_slip, "sell_percent": sell_slip, "total_percent": buy_slip + sell_slip}
                    realistic_profit = ProfitCalculator(cost_model).calculate(buy_execution, sell_execution, int(executable))
                    realistic = {"status": "available", "quantity": executable, "buy_execution_price": buy_execution, "sell_execution_price": sell_execution, "net_profit": realistic_profit["estimated_net_profit"], "roi_percent": realistic_profit["roi_percent"]}
                result.append({
                    "status": "stale_data" if freshness["status"] == "stale" else ("cost_model_missing" if not cost_model.configured else "valid"),
                    "server": self.server, "item_id": current_item, "quality": quality,
                    "buy": {"city": buy["city"], "price": buy_price, "price_source": "sell_price_min"},
                    "sell": {"city": sell["city"], "price": sell_price, "price_source": "buy_price_max"},
                    "spread": {"absolute": spread, "percent": spread_pct}, "profit": profit, "historical": historical,
                    "data": {"price_timestamp": {"buy": buy.get("sell_price_min_date"), "sell": sell.get("buy_price_max_date")}, "freshness": freshness["status"], "data_age_minutes": freshness["age_minutes"]},
                    "liquidity": {"buy": buy_liquidity, "sell": sell_liquidity, "requested_quantity": quantity, "executable_quantity": executable},
                    "slippage": slippage, "realistic_profit": realistic, "confidence": confidence,
                    "data_availability": {"liquidity": "available" if executable is not None else "unavailable", "historical": "available" if historical["data_sufficient"] else "insufficient_historical_data", "overall": "partial" if executable is None else "available"},
                    "market_type": "city",
                })
        def key(o: dict[str, Any]):
            hist = o["historical"]; profit = o["profit"]
            if sort == "profit": return float(profit["estimated_net_profit"] if profit["estimated_net_profit"] is not None else profit["gross_profit"])
            if sort == "spread": return o["spread"]["percent"]
            if sort == "stability": return hist["positive_spread_ratio"] if hist["positive_spread_ratio"] is not None else -1
            if sort == "freshness": return -(o["data"]["data_age_minutes"] if o["data"]["data_age_minutes"] is not None else float("inf"))
            if sort == "confidence": return {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNAVAILABLE": 0}.get(o["confidence"], 0)
            return float(profit["roi_percent"] if profit["roi_percent"] is not None else profit["gross_roi_percent"])
        result.sort(key=key, reverse=True)
        for rank, opportunity in enumerate(result[:limit], 1): opportunity["rank"] = rank
        return result[:limit]

    def liquidity(self, item_id: str, city: str, quality: int = 1) -> dict[str, Any]:
        if quality < 1: raise ValueError("quality must be positive")
        return {"server": self.server, "item_id": item_id, "city": city, "quality": quality, "liquidity": self._liquidity(item_id, city, quality)}

    def calculate(self, buy_price: float, sell_price: float, quantity: int, cost_model: CostModel | None = None) -> dict[str, Any]:
        if buy_price <= 0 or sell_price < 0: raise ValueError("prices must be non-negative and buy_price must be greater than zero")
        if sell_price <= buy_price: raise ValueError("sell_price must be greater than buy_price")
        self._validate_quantity(quantity); cost_model = cost_model or CostModel()
        profit = ProfitCalculator(cost_model).calculate(buy_price, sell_price, quantity)
        return {"buy_price": buy_price, "sell_price": sell_price, "spread": {"absolute": sell_price - buy_price, "percent": (sell_price - buy_price) / buy_price * 100.0}, "profit": profit, "status": "valid" if cost_model.configured else "cost_model_missing", "server": self.server}
