from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class DepthLevel:
    price: float
    quantity: float

    def __post_init__(self) -> None:
        if self.price <= 0 or self.quantity <= 0:
            raise ValueError("depth price and quantity must be greater than zero")


@dataclass(frozen=True)
class LiquiditySnapshot:
    """Normalized liquidity/depth data from a source that actually provides it.

    ``available_quantity`` is retained as a compatibility shorthand and, when
    supplied, applies to both sides. Real order-book sources should provide
    side-specific quantities/depth instead.
    """

    available_quantity: float | None = None
    available_buy_quantity: float | None = None
    available_sell_quantity: float | None = None
    buy_depth: tuple[DepthLevel, ...] = ()
    sell_depth: tuple[DepthLevel, ...] = ()
    source: str = "unknown"

    def __post_init__(self) -> None:
        for value in (self.available_quantity, self.available_buy_quantity, self.available_sell_quantity):
            if value is not None and value < 0:
                raise ValueError("available quantities must be non-negative")

    @property
    def buy_quantity(self) -> float | None:
        return self.available_buy_quantity if self.available_buy_quantity is not None else self.available_quantity

    @property
    def sell_quantity(self) -> float | None:
        return self.available_sell_quantity if self.available_sell_quantity is not None else self.available_quantity

    @property
    def available(self) -> bool:
        return self.buy_quantity is not None or self.sell_quantity is not None or bool(self.buy_depth) or bool(self.sell_depth)


class LiquidityProvider(Protocol):
    def get(self, server: str, item_id: str, city: str, quality: int) -> LiquiditySnapshot | None:
        ...


class UnavailableLiquidityProvider:
    """Explicit provider used when the current market source has no liquidity data."""

    def get(self, server: str, item_id: str, city: str, quality: int) -> None:
        return None


def executable_quantity(
    requested_quantity: int,
    available_buy_quantity: float | None,
    available_sell_quantity: float | None,
) -> float | None:
    if isinstance(requested_quantity, bool) or requested_quantity <= 0:
        raise ValueError("requested_quantity must be greater than zero")
    if available_buy_quantity is None or available_sell_quantity is None:
        return None
    if available_buy_quantity < 0 or available_sell_quantity < 0:
        raise ValueError("available quantities must be non-negative")
    return min(float(requested_quantity), float(available_buy_quantity), float(available_sell_quantity))


def weighted_average_execution_price(levels: Iterable[DepthLevel], requested_quantity: float) -> float | None:
    if requested_quantity <= 0:
        raise ValueError("requested_quantity must be greater than zero")
    remaining = requested_quantity
    spent = 0.0
    filled = 0.0
    for level in levels:
        take = min(remaining, level.quantity)
        spent += take * level.price
        filled += take
        remaining -= take
        if remaining <= 0:
            break
    if filled < requested_quantity:
        return None
    return spent / filled


def slippage_percent(reference_price: float, execution_price: float, side: str) -> float:
    if reference_price <= 0 or execution_price <= 0:
        raise ValueError("prices must be greater than zero")
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    # Buy slippage is execution above the quoted buy-side reference.
    # Sell slippage is execution below the quoted sell-side reference.
    if side == "buy":
        return (execution_price - reference_price) / reference_price * 100.0
    return (reference_price - execution_price) / reference_price * 100.0


class DatabaseLiquidityProvider:
    """Liquidity provider backed by normalized external market-order data.

    ``buy_depth`` represents the sell offers consumed when buying in the
    requested city; ``sell_depth`` represents buy requests consumed when
    selling. This preserves the Phase 5 execution API while keeping the
    underlying order-book side explicit in storage.
    """

    def __init__(self, database, *, max_age_minutes: float = 15.0, source: str | None = None):
        if max_age_minutes < 0:
            raise ValueError("max_age_minutes must be >= 0")
        self.database = database
        self.max_age_minutes = max_age_minutes
        self.source = source

    def get(self, server: str, item_id: str, city: str, quality: int) -> LiquiditySnapshot | None:
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.max_age_minutes)
        rows = self.database.liquidity_orders(server=server, item_id=item_id, city=city, quality=quality, observed_after=cutoff.isoformat().replace("+00:00", "Z"))
        if self.source is not None:
            rows = [row for row in rows if row["source"] == self.source]
        if not rows:
            return None
        buy_orders = [row for row in rows if row["side"] == "buy"]
        sell_orders = [row for row in rows if row["side"] == "sell"]
        buy_depth = tuple(DepthLevel(float(row["price"]), float(row["quantity"])) for row in sorted(sell_orders, key=lambda r: (r["price"], r["id"])))
        sell_depth = tuple(DepthLevel(float(row["price"]), float(row["quantity"])) for row in sorted(buy_orders, key=lambda r: (-r["price"], r["id"])))
        return LiquiditySnapshot(
            available_buy_quantity=sum(level.quantity for level in buy_depth) if buy_depth else None,
            available_sell_quantity=sum(level.quantity for level in sell_depth) if sell_depth else None,
            buy_depth=buy_depth,
            sell_depth=sell_depth,
            source=self.source or rows[0]["source"],
        )
