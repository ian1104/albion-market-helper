from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db.database import Database
from services.albion_api import (
    AODPConnectionError, AODPDNSError, AODPHTTPError, AODPInvalidResponseError,
    AODPTimeoutError, AlbionApiService,
)
from services.collector import Collector
from services.market_service import MarketService
from services.scheduler import CollectorScheduler
from services.aodp_nats import AODPNatsAdapter, AODPNatsConsumer
from services.order_lifecycle import OrderLifecycleManager
from services.analysis_service import AnalysisService, RANGES
from services.arbitrage_service import ArbitrageService, CostModel
from services.business_strategy import default_strategy_registry
from services.strategy_engine import StrategyEngine
from config import (
    ALBION_SERVER, AODP_NATS_ENABLED, AODP_NATS_HOST, AODP_NATS_PORTS, AODP_NATS_SUBJECT,
    AODP_NATS_SERVERS, AODP_NATS_STALE_MINUTES, SERVER_DISPLAY_NAMES, SUPPORTED_SERVERS,
)


database = Database()
market_service = MarketService(database)
albion_api = AlbionApiService()
collector = Collector(albion_api, market_service)
scheduler = CollectorScheduler(collector)
lifecycle_manager = OrderLifecycleManager(database, stale_minutes=AODP_NATS_STALE_MINUTES)
nats_consumers: dict[str, AODPNatsConsumer] = {}
nats_tasks: dict[str, Any] = {}


def _nats_url(server: str) -> str:
    return f"nats://public:thenewalbiondata@{AODP_NATS_HOST}:{AODP_NATS_PORTS[server]}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if AODP_NATS_ENABLED:
        for server_name in AODP_NATS_SERVERS:
            consumer = AODPNatsConsumer(
                AODPNatsAdapter(), database, server=server_name,
                nats_url=_nats_url(server_name), subject=AODP_NATS_SUBJECT,
            )
            nats_consumers[server_name] = consumer
            nats_tasks[server_name] = asyncio.create_task(consumer.start(), name=f"aodp-nats-{server_name}")
    yield
    for consumer in nats_consumers.values():
        await consumer.stop()
    for task in nats_tasks.values():
        task.cancel()
    if nats_tasks:
        await asyncio.gather(*nats_tasks.values(), return_exceptions=True)
    nats_tasks.clear()
    nats_consumers.clear()
    scheduler.stop()


app = FastAPI(title="Albion Market Helper", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"]
)


class FetchRequest(BaseModel):
    item_id: str = Field(min_length=1)
    cities: list[str] = Field(min_length=1)
    quality: int = Field(ge=1)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, AODPTimeoutError):
        return HTTPException(504, "AODP request timed out")
    if isinstance(exc, AODPDNSError):
        return HTTPException(503, "AODP DNS resolution failed")
    if isinstance(exc, AODPConnectionError):
        return HTTPException(503, "AODP connection failed")
    if isinstance(exc, AODPHTTPError):
        return HTTPException(502, f"AODP HTTP error: {exc.status_code}")
    if isinstance(exc, AODPInvalidResponseError):
        return HTTPException(502, "AODP returned an invalid response")
    return HTTPException(500, "Market pipeline error")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "Albion Market Helper"}


@app.get("/api/market/prices")
def prices(item_id: str | None = None, city: str | None = None,
           quality: int | None = Query(None, ge=1), server: str = ALBION_SERVER) -> list[dict[str, Any]]:
    return database.current_prices(item_id, city, quality, server=server)


@app.get("/api/market/history")
def history(item_id: str | None = None, city: str | None = None,
            quality: int | None = Query(None, ge=1), start: str | None = None,
            end: str | None = None, server: str = ALBION_SERVER) -> list[dict[str, Any]]:
    if start and end:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(400, "start and end must be valid ISO-8601 timestamps") from exc
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        if start_dt > end_dt:
            raise HTTPException(400, "start must not be later than end")
    return database.history(item_id, city, quality, start, end, server=server)


@app.post("/api/market/fetch")
def fetch(request: FetchRequest) -> dict[str, Any]:
    try:
        records = albion_api.fetch_prices([request.item_id], request.cities, [request.quality])
        count = market_service.save_snapshot_batch(records)
        return {"saved": count, "records": records}
    except Exception as exc:
        raise _error(exc)


@app.post("/api/collector/run")
def run_collector() -> dict[str, Any]:
    try:
        return collector.run()
    except Exception as exc:
        raise _error(exc)


@app.get("/api/collector/status")
def collector_status() -> dict[str, Any]:
    return {"server": collector.server, "running": collector._lock.locked(), "last_collection": database.latest_collection_run(collector.server)}


def _analysis_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, "Analysis error")


def _validate_server(server: str):
    if server not in SUPPORTED_SERVERS:
        raise HTTPException(400, "server must be one of: east, west, europe")


def _validate_range(range_name: str):
    if range_name not in RANGES:
        raise HTTPException(400, "range must be one of: 12h, 24h, 7d, 30d, all")


@app.get("/api/market/stats")
def market_stats(item_id: str = Query(..., min_length=1), city: str = Query(..., min_length=1),
                 quality: int = Query(..., ge=1), range: str = Query("24h"),
                 start: str | None = None, end: str | None = None, server: str = ALBION_SERVER):
    _validate_server(server)
    _validate_range(range)
    try:
        return AnalysisService(database, server).statistics(item_id, city, quality, range, start, end)
    except Exception as exc:
        raise _analysis_error(exc)


@app.get("/api/market/quality")
def market_quality(range: str = Query("all"), start: str | None = None, end: str | None = None,
                   server: str = ALBION_SERVER):
    _validate_server(server)
    _validate_range(range)
    try:
        return AnalysisService(database, server).quality(range, start, end)
    except Exception as exc:
        raise _analysis_error(exc)


@app.get("/api/market/analysis")
def market_analysis(item_id: str = Query(..., min_length=1), city: str = Query(..., min_length=1),
                    quality: int = Query(..., ge=1), range: str = Query("24h"),
                    start: str | None = None, end: str | None = None, server: str = ALBION_SERVER):
    _validate_server(server)
    _validate_range(range)
    try:
        service = AnalysisService(database, server)
        result = service.statistics(item_id, city, quality, range, start, end)
        trend = service.trend(item_id, city, quality, range, start=start, end=end)
        result["trend"] = {"statistics": trend["statistics"], "series": trend["series"]}
        return result
    except Exception as exc:
        raise _analysis_error(exc)


@app.get("/api/market/trend")
def market_trend(item_id: str = Query(..., min_length=1), city: str = Query(..., min_length=1),
                quality: int = Query(..., ge=1), range: str = Query("24h"),
                start: str | None = None, end: str | None = None, server: str = ALBION_SERVER):
    _validate_server(server)
    _validate_range(range)
    try:
        return AnalysisService(database, server).trend(item_id, city, quality, range, start=start, end=end)
    except Exception as exc:
        raise _analysis_error(exc)


@app.get("/api/market/spread")
def market_spread(item_id: str = Query(..., min_length=1), quality: int = Query(..., ge=1),
                 range: str = Query("24h"), start: str | None = None, end: str | None = None,
                 server: str = ALBION_SERVER):
    _validate_server(server)
    _validate_range(range)
    try:
        service = AnalysisService(database, server)
        result = service.spread(item_id, quality, range, start, end)
        result["stability"] = service.spread_stability(item_id, quality, range, start, end)
        return result
    except Exception as exc:
        raise _analysis_error(exc)


def _cost_model(purchase_fee: float, selling_fee: float, transaction_tax: float, transport_cost: float, safety_buffer: float, configured: bool) -> CostModel:
    return CostModel(purchase_fee=purchase_fee, selling_fee=selling_fee, transaction_tax=transaction_tax, transport_cost=transport_cost, safety_buffer=safety_buffer, configured=configured)


@app.get("/api/sources")
def sources(server: str = ALBION_SERVER) -> dict[str, Any]:
    if server not in SUPPORTED_SERVERS:
        raise HTTPException(400, f"unsupported server: {server}")
    return {
        "server": server,
        "server_name": SERVER_DISPLAY_NAMES[server],
        "sources": {
            "price": {"name": "aodp-http", "available": True},
            "liquidity": {
                "name": "aodp-nats",
                "available": AODP_NATS_ENABLED,
                "host": AODP_NATS_HOST,
                "port": AODP_NATS_PORTS[server],
                "subject": AODP_NATS_SUBJECT,
                "enabled_for_server": AODP_NATS_ENABLED and server in AODP_NATS_SERVERS,
                "connected": bool(nats_consumers.get(server) and nats_consumers[server]._client is not None and not nats_consumers[server]._client.is_closed),
                "policy": "unavailable_when_no_recent_order_data",
            },
        },
    }


@app.get("/api/liquidity/status")
def liquidity_status(server: str = ALBION_SERVER) -> dict[str, Any]:
    _validate_server(server)
    counts = lifecycle_manager.refresh(server=server)
    consumer = nats_consumers.get(server)
    return {
        "server": server,
        "source": "aodp-nats",
        "enabled": AODP_NATS_ENABLED and server in AODP_NATS_SERVERS,
        "connected": bool(consumer and consumer._client is not None and not consumer._client.is_closed),
        "messages_received": consumer.messages_received if consumer else 0,
        "orders_saved": consumer.orders_saved if consumer else 0,
        "invalid_messages": consumer.invalid_messages if consumer else 0,
        "connection_attempts": consumer.connection_attempts if consumer else 0,
        "order_counts": counts,
        "stale_minutes": AODP_NATS_STALE_MINUTES,
    }


@app.get("/api/liquidity/orders")
def liquidity_orders(
    item_id: str = Query(..., min_length=1), city: str = Query(..., min_length=1),
    quality: int = Query(1, ge=1), side: str | None = None, server: str = ALBION_SERVER,
    include_inactive: bool = False,
) -> dict[str, Any]:
    _validate_server(server)
    if side is not None and side not in {"buy", "sell"}:
        raise HTTPException(400, "side must be buy or sell")
    rows = database.liquidity_orders(
        server=server, item_id=item_id, city=city, quality=quality, side=side,
        include_inactive=include_inactive, stale_minutes=AODP_NATS_STALE_MINUTES,
    )
    return {"server": server, "item_id": item_id, "city": city, "quality": quality, "orders": rows}


@app.get("/api/liquidity/summary")
def liquidity_summary(server: str = ALBION_SERVER) -> dict[str, Any]:
    _validate_server(server)
    counts = lifecycle_manager.refresh(server=server)
    return {"server": server, "source": "aodp-nats", "counts": counts, "available": counts.get("ACTIVE", 0) > 0}


@app.get("/api/arbitrage")
def arbitrage(
    item_id: str | None = Query(None, min_length=1), quality: int = Query(1, ge=1),
    server: str = ALBION_SERVER, quantity: int = Query(1, ge=1),
    min_spread_percent: float | None = Query(None, ge=0), min_roi: float | None = Query(None, ge=0),
    min_profit: float | None = Query(None, ge=0), sort: str = "roi", limit: int = Query(20, ge=1, le=100),
    configured: bool = False, selling_fee: float = Query(0.0, ge=0), transaction_tax: float = Query(0.0, ge=0),
    transport_cost: float = Query(0.0, ge=0), purchase_fee: float = Query(0.0, ge=0), safety_buffer: float = Query(0.0, ge=0),
    freshness_max_age_minutes: float = Query(30.0, ge=0),
):
    _validate_server(server)
    try:
        return {"server": server, "quality": quality, "quantity": quantity, "opportunities": ArbitrageService(database, server).opportunities(
            item_id=item_id, quality=quality, quantity=quantity, min_spread_percent=min_spread_percent,
            min_roi=min_roi, min_profit=min_profit, sort=sort, limit=limit,
            cost_model=_cost_model(purchase_fee, selling_fee, transaction_tax, transport_cost, safety_buffer, configured),
            freshness_max_age_minutes=freshness_max_age_minutes,
        )}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/arbitrage/opportunities")
def arbitrage_opportunities(
    item_id: str | None = Query(None, min_length=1), quality: int = Query(1, ge=1),
    server: str = ALBION_SERVER, quantity: int = Query(1, ge=1),
    min_spread_percent: float | None = Query(None, ge=0), min_roi: float | None = Query(None, ge=0),
    min_profit: float | None = Query(None, ge=0), sort: str = "roi", limit: int = Query(20, ge=1, le=100),
    configured: bool = False, selling_fee: float = Query(0.0, ge=0), transaction_tax: float = Query(0.0, ge=0),
    transport_cost: float = Query(0.0, ge=0), purchase_fee: float = Query(0.0, ge=0), safety_buffer: float = Query(0.0, ge=0),
    freshness_max_age_minutes: float = Query(30.0, ge=0),
):
    return arbitrage(item_id=item_id, quality=quality, server=server, quantity=quantity,
                     min_spread_percent=min_spread_percent, min_roi=min_roi, min_profit=min_profit,
                     sort=sort, limit=limit, configured=configured, selling_fee=selling_fee,
                     transaction_tax=transaction_tax, transport_cost=transport_cost, purchase_fee=purchase_fee,
                     safety_buffer=safety_buffer, freshness_max_age_minutes=freshness_max_age_minutes)


@app.get("/api/arbitrage/liquidity")
def arbitrage_liquidity(
    item_id: str = Query(..., min_length=1), city: str = Query(..., min_length=1),
    quality: int = Query(1, ge=1), server: str = ALBION_SERVER,
):
    _validate_server(server)
    try:
        return ArbitrageService(database, server).liquidity(item_id, city, quality)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/arbitrage/calculate")
def arbitrage_calculate(
    buy_price: float = Query(..., gt=0), sell_price: float = Query(..., gt=0), quantity: int = Query(1, ge=1),
    server: str = ALBION_SERVER, configured: bool = False, selling_fee: float = Query(0.0, ge=0),
    transaction_tax: float = Query(0.0, ge=0), transport_cost: float = Query(0.0, ge=0), purchase_fee: float = Query(0.0, ge=0), safety_buffer: float = Query(0.0, ge=0),
):
    _validate_server(server)
    try:
        return ArbitrageService(database, server).calculate(
            buy_price, sell_price, quantity,
            _cost_model(purchase_fee, selling_fee, transaction_tax, transport_cost, safety_buffer, configured),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


strategy_registry = default_strategy_registry(ArbitrageService(database, ALBION_SERVER))
strategy_engine = StrategyEngine(strategy_registry)


@app.get("/api/strategies")
def strategies() -> dict[str, Any]:
    return {"strategies": strategy_engine.definitions()}


@app.get("/api/strategies/{strategy_id}")
def strategy(strategy_id: str) -> dict[str, Any]:
    definition = strategy_registry.get_definition(strategy_id)
    if definition is None:
        raise HTTPException(404, f"unknown strategy: {strategy_id}")
    return {"strategy": definition.to_dict(), "executable": strategy_registry.get(strategy_id) is not None}


@app.get("/api/opportunities")
def opportunities(
    strategy: str | None = None,
    server: str = ALBION_SERVER,
    capital: float | None = Query(None, gt=0),
    risk: str | None = None,
    sort: str = "profit",
    limit: int = Query(20, ge=1, le=100),
    item_id: str | None = Query(None, min_length=1),
    quality: int = Query(1, ge=1),
    quantity: int = Query(1, ge=1),
    configured: bool = False,
    selling_fee: float = Query(0.0, ge=0),
    transaction_tax: float = Query(0.0, ge=0),
    transport_cost: float = Query(0.0, ge=0),
    purchase_fee: float = Query(0.0, ge=0),
    safety_buffer: float = Query(0.0, ge=0),
    freshness_max_age_minutes: float = Query(30.0, ge=0),
) -> dict[str, Any]:
    _validate_server(server)
    cost_model = _cost_model(purchase_fee, selling_fee, transaction_tax, transport_cost, safety_buffer, configured)
    try:
        result = strategy_engine.evaluate(
            strategy_id=strategy,
            capital=capital,
            risk=risk,
            sort=sort,
            limit=limit,
            server=server,
            item_id=item_id,
            quality=quality,
            quantity=quantity,
            cost_model=cost_model,
            freshness_max_age_minutes=freshness_max_age_minutes,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"server": server, "capital": capital, "strategy": strategy, "sort": sort, "opportunities": [item.to_dict() for item in result]}
