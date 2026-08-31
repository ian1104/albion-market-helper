from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol


@dataclass(frozen=True)
class NormalizedMarketOrder:
    source: str
    server: str
    item_id: str
    city: str
    quality: int
    side: str
    price: float
    quantity: float
    order_id: str | None
    expires_at: str | None
    observed_at: str
    source_timestamp: str | None = None

    def __post_init__(self) -> None:
        if not self.server or not self.item_id or not self.city:
            raise ValueError("server, item_id and city are required")
        if self.quality < 1:
            raise ValueError("quality must be >= 1")
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if self.price <= 0 or self.quantity <= 0:
            raise ValueError("price and quantity must be greater than zero")
        _validate_timestamp(self.observed_at)
        if self.expires_at is not None:
            _validate_timestamp(self.expires_at)
        if self.source_timestamp is not None:
            _validate_timestamp(self.source_timestamp)


class MarketDataAdapter(Protocol):
    source_name: str

    def normalize(self, payload: object, *, server: str, observed_at: str | None = None) -> list[NormalizedMarketOrder]:
        ...


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_timestamp(value: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid timestamp: {value!r}") from exc


def sort_depth(orders: Iterable[NormalizedMarketOrder], side: str) -> tuple[NormalizedMarketOrder, ...]:
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    filtered = [order for order in orders if order.side == side]
    # To buy from sell orders, consume the cheapest offers first.
    # To sell into buy orders, consume the highest bids first.
    return tuple(sorted(filtered, key=lambda order: order.price, reverse=side == "buy"))
