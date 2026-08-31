from __future__ import annotations

import json
from typing import Any

from services.market_data import MarketDataAdapter, NormalizedMarketOrder, utc_now


class AODPNatsAdapter(MarketDataAdapter):
    """Normalize AODP public NATS market-order messages.

    AODP exposes individual active market orders through the marketorders
    stream. The adapter never invents quantity/depth when the message does
    not contain them.
    """

    source_name = "aodp-nats"

    def normalize(self, payload: object, *, server: str, observed_at: str | None = None) -> list[NormalizedMarketOrder]:
        observed = observed_at or utc_now()
        data: Any = payload
        if isinstance(data, (bytes, bytearray)):
            data = json.loads(data.decode("utf-8"))
        elif isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            raise ValueError("AODP NATS payload must be a JSON object")

        raw_orders = data.get("Orders")
        if not isinstance(raw_orders, list):
            raise ValueError("AODP NATS payload is missing Orders")

        normalized: list[NormalizedMarketOrder] = []
        for raw in raw_orders:
            if not isinstance(raw, dict):
                continue
            order = self._normalize_order(raw, server=server, observed_at=observed)
            if order is not None:
                normalized.append(order)
        return normalized

    def _normalize_order(self, raw: dict[str, Any], *, server: str, observed_at: str) -> NormalizedMarketOrder | None:
        item_id = raw.get("ItemTypeId")
        city = raw.get("LocationId")
        quality = raw.get("QualityLevel")
        price = raw.get("UnitPriceSilver")
        quantity = raw.get("Amount")
        auction_type = str(raw.get("AuctionType", "")).lower()
        if not item_id or not city or quality is None or price is None or quantity is None:
            return None
        if auction_type in {"offer", "sell", "sellorder", "sell_order"}:
            side = "sell"
        elif auction_type in {"request", "buy", "buyorder", "buy_order"}:
            side = "buy"
        else:
            return None
        try:
            quality_i = int(quality)
            price_f = float(price)
            quantity_f = float(quantity)
            order_id = str(raw["Id"]) if raw.get("Id") is not None else None
        except (TypeError, ValueError):
            return None
        if quality_i < 1 or price_f <= 0 or quantity_f <= 0:
            return None
        expires = raw.get("Expires")
        expires_s = str(expires) if expires else None
        return NormalizedMarketOrder(
            source=self.source_name,
            server=server,
            item_id=str(item_id),
            city=str(city),
            quality=quality_i,
            side=side,
            price=price_f,
            quantity=quantity_f,
            order_id=order_id,
            expires_at=expires_s,
            observed_at=observed_at,
            source_timestamp=None,
        )


class AODPNatsConsumer:
    """Optional async consumer for the public AODP market-order stream.

    The network dependency is kept out of the normalization layer so tests can
    exercise parsing without DNS, NATS, or live game traffic.
    """

    def __init__(self, adapter: AODPNatsAdapter, database, *, server: str, nats_url: str, subject: str = "marketorders.deduped"):
        self.adapter = adapter
        self.database = database
        self.server = server
        self.nats_url = nats_url
        self.subject = subject
        self._subscription = None
        self._client = None

    async def start(self) -> None:
        try:
            import nats
        except ImportError as exc:
            raise RuntimeError("nats-py is required to consume AODP NATS data") from exc
        self._client = await nats.connect(self.nats_url)
        self._subscription = await self._client.subscribe(self.subject, cb=self._handle_message)

    async def _handle_message(self, message) -> int:
        orders = self.adapter.normalize(message.data, server=self.server)
        for order in orders:
            self.database.upsert_liquidity_order(order)
        return len(orders)

    async def stop(self) -> None:
        if self._subscription is not None:
            await self._subscription.unsubscribe()
            self._subscription = None
        if self._client is not None:
            await self._client.drain()
            self._client = None
