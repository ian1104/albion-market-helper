from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

from config import AODP_LOCATION_NAMES, AODP_NATS_RECONNECT_MAX_SECONDS, AODP_NATS_RECONNECT_SECONDS
from services.market_data import MarketDataAdapter, NormalizedMarketOrder, utc_now

logger = logging.getLogger(__name__)


class AODPNatsAdapter(MarketDataAdapter):
    """Normalize AODP public NATS market-order messages."""

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
        if isinstance(raw_orders, list):
            candidates = raw_orders
        elif "ItemTypeId" in data:
            candidates = [data]
        else:
            raise ValueError("AODP NATS payload is neither MarketUpload nor MarketOrder")

        normalized: list[NormalizedMarketOrder] = []
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            try:
                order = self._normalize_order(raw, server=server, observed_at=observed)
            except (TypeError, ValueError, KeyError):
                continue
            if order is not None:
                normalized.append(order)
        return normalized

    def _normalize_order(self, raw: dict[str, Any], *, server: str, observed_at: str) -> NormalizedMarketOrder | None:
        item_id = raw.get("ItemTypeId")
        location_id = raw.get("LocationId")
        city = AODP_LOCATION_NAMES.get(str(location_id), str(location_id)) if location_id is not None else None
        quality = raw.get("QualityLevel")
        price = raw.get("UnitPriceSilver")
        quantity = raw.get("Amount")
        auction_type = str(raw.get("AuctionType", "")).lower()
        if not item_id or not city or quality is None or price is None or quantity is None or raw.get("Id") is None:
            return None
        if auction_type in {"offer", "sell", "sellorder", "sell_order"}:
            side = "sell"
        elif auction_type in {"request", "buy", "buyorder", "buy_order"}:
            side = "buy"
        else:
            return None
        quality_i = int(quality)
        price_f = float(price)
        quantity_f = float(quantity)
        if quality_i < 1 or price_f <= 0 or quantity_f <= 0:
            return None
        expires = raw.get("Expires")
        expires_s = str(expires) if expires else None
        return NormalizedMarketOrder(
            source=self.source_name,
            server=server,
            item_id=str(item_id),
            city=city,
            quality=quality_i,
            side=side,
            price=price_f,
            quantity=quantity_f,
            order_id=str(raw["Id"]),
            expires_at=expires_s,
            observed_at=observed_at,
            source_timestamp=None,
        )


class AODPNatsConsumer:
    """Long-lived NATS subscriber with reconnect/backoff and graceful shutdown."""

    def __init__(
        self,
        adapter: AODPNatsAdapter,
        database,
        *,
        server: str,
        nats_url: str,
        subject: str = "marketorders.deduped",
        reconnect_base_seconds: float = AODP_NATS_RECONNECT_SECONDS,
        reconnect_max_seconds: float = AODP_NATS_RECONNECT_MAX_SECONDS,
        on_message_error: Callable[[Exception], Awaitable[None] | None] | None = None,
    ):
        if not server or not nats_url or not subject:
            raise ValueError("server, nats_url and subject are required")
        if reconnect_base_seconds <= 0 or reconnect_max_seconds < reconnect_base_seconds:
            raise ValueError("invalid reconnect backoff configuration")
        self.adapter = adapter
        self.database = database
        self.server = server
        self.nats_url = nats_url
        self.subject = subject
        self.reconnect_base_seconds = reconnect_base_seconds
        self.reconnect_max_seconds = reconnect_max_seconds
        self.on_message_error = on_message_error
        self._stop = asyncio.Event()
        self._client = None
        self._subscription = None
        self._persistence_lock = asyncio.Lock()
        self.messages_received = 0
        self.orders_parsed = 0
        self.orders_saved = 0
        self.invalid_messages = 0
        self.connection_attempts = 0
        self.reconnect_count = 0
        self.subscription_active = False
        self.last_message_at: str | None = None
        self.last_successful_persistence: str | None = None
        self.last_error: str | None = None
        self.last_persistence_duration_ms: float | None = None
        self.max_persistence_duration_ms: float = 0.0
        self.persistence_failures = 0

    def _persist_orders_sync(self, orders: list[NormalizedMarketOrder]) -> int:
        saved = 0
        for order in orders:
            self.database.upsert_liquidity_order(order)
            saved += 1
        return saved

    async def _handle_message(self, message) -> None:
        self.messages_received += 1
        self.last_message_at = utc_now()
        try:
            orders = self.adapter.normalize(message.data, server=self.server)
            self.orders_parsed += len(orders)
            if not orders:
                return
            started = time.perf_counter()
            async with self._persistence_lock:
                saved = await asyncio.to_thread(self._persist_orders_sync, orders)
            duration_ms = (time.perf_counter() - started) * 1000.0
            self.last_persistence_duration_ms = duration_ms
            self.max_persistence_duration_ms = max(self.max_persistence_duration_ms, duration_ms)
            self.orders_saved += saved
            if saved:
                self.last_successful_persistence = utc_now()
        except Exception as exc:
            self.persistence_failures += 1
            self.invalid_messages += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("AODP NATS message failed for %s: %s", self.server, exc)
            if self.on_message_error is not None:
                result = self.on_message_error(exc)
                if asyncio.iscoroutine(result):
                    await result

    async def _on_reconnected(self, *_args) -> None:
        self.reconnect_count += 1
        self.subscription_active = True
        logger.info("AODP NATS reconnected for %s", self.server)

    async def _on_disconnected(self, *_args) -> None:
        self.subscription_active = False
        logger.warning("AODP NATS disconnected for %s", self.server)

    async def _on_error(self, error) -> None:
        self.last_error = f"{type(error).__name__}: {error}"
        logger.warning("AODP NATS error for %s: %s", self.server, error)

    async def _connect_once(self) -> None:
        try:
            import nats
        except ImportError as exc:
            raise RuntimeError("nats-py is required to consume AODP NATS data") from exc
        self.connection_attempts += 1
        self._client = await nats.connect(
            servers=[self.nats_url],
            reconnect_time_wait=1,
            max_reconnect_attempts=-1,
            reconnected_cb=self._on_reconnected,
            disconnected_cb=self._on_disconnected,
            error_cb=self._on_error,
        )
        self._subscription = await self._client.subscribe(self.subject, cb=self._handle_message)
        await self._client.flush()
        self.subscription_active = True
        self.last_error = None

    async def _wait_before_retry(self, delay: float) -> None:
        """Wait for backoff or stop immediately when shutdown is requested."""
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            return

    async def run_forever(self) -> None:
        delay = self.reconnect_base_seconds
        while not self._stop.is_set():
            try:
                await self._connect_once()
                delay = self.reconnect_base_seconds
                while not self._stop.is_set() and self._client is not None and not self._client.is_closed:
                    await asyncio.sleep(0.5)
                if self._stop.is_set():
                    break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("AODP NATS connection failed for %s: %s", self.server, exc)
            finally:
                await self._disconnect()
            if not self._stop.is_set():
                await self._wait_before_retry(delay)
                delay = min(self.reconnect_max_seconds, delay * 2)

    async def start(self) -> None:
        self._stop.clear()
        await self.run_forever()

    async def stop(self) -> None:
        self._stop.set()
        await self._disconnect()

    async def _disconnect(self) -> None:
        self.subscription_active = False
        if self._subscription is not None:
            try:
                await self._subscription.unsubscribe()
            except Exception:
                pass
            self._subscription = None
        if self._client is not None:
            try:
                await self._client.drain()
            except Exception:
                try:
                    await self._client.close()
                except Exception:
                    pass
            self._client = None
