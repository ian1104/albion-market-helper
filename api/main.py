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
           quality: int | None = Query(None, ge=1)) -> list[dict[str, Any]]:
    return database.current_prices(item_id, city, quality)


@app.get("/api/market/history")
def history(item_id: str | None = None, city: str | None = None,
            quality: int | None = Query(None, ge=1), start: str | None = None,
            end: str | None = None) -> list[dict[str, Any]]:
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
    return database.history(item_id, city, quality, start, end)


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
    return {"running": collector._lock.locked(), "last_collection": database.latest_collection_run()}
