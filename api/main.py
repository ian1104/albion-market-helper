from __future__ import annotations

from contextlib import asynccontextmanager
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
from services.analysis_service import AnalysisService, RANGES
from services.arbitrage_service import ArbitrageService, CostModel
from config import ALBION_SERVER, SUPPORTED_SERVERS


database = Database()
market_service = MarketService(database)
albion_api = AlbionApiService()
collector = Collector(albion_api, market_service)
scheduler = CollectorScheduler(collector)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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
