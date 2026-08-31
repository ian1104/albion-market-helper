from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable
import time
from urllib.parse import urlencode

import httpx

from config import (
    AODP_HOST,
    AODP_RETRY_BACKOFF_SECONDS,
    AODP_RETRY_COUNT,
    AODP_TIMEOUT_SECONDS,
    AODP_URL_MAX_LENGTH,
)


class AODPError(Exception):
    """Base class for AODP failures."""


class AODPTimeoutError(AODPError):
    pass


class AODPDNSError(AODPError):
    pass


class AODPConnectionError(AODPError):
    pass


class AODPHTTPError(AODPError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class AODPInvalidResponseError(AODPError):
    pass


def normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AODPInvalidResponseError("invalid timestamp")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AODPInvalidResponseError(f"invalid timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _price(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise AODPInvalidResponseError(f"{field} must be an integer price or null")
    if value < 0:
        raise AODPInvalidResponseError(f"{field} cannot be negative")
    return int(value)


def parse_response(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise AODPInvalidResponseError("AODP response must be a JSON array")
    records: list[dict[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise AODPInvalidResponseError(f"record {index} is not an object")
        item_id = row.get("item_id")
        city = row.get("city", row.get("location"))
        quality = row.get("quality")
        if not isinstance(item_id, str) or not item_id.strip():
            raise AODPInvalidResponseError(f"record {index}: invalid item_id")
        if not isinstance(city, str) or not city.strip():
            raise AODPInvalidResponseError(f"record {index}: invalid city/location")
        if isinstance(quality, bool) or not isinstance(quality, int) or quality < 1:
            raise AODPInvalidResponseError(f"record {index}: invalid quality")
        sell = _price(row.get("sell_price_min"), "sell_price_min")
        buy = _price(row.get("buy_price_max"), "buy_price_max")
        sell_date = normalize_timestamp(row.get("sell_price_min_date"))
        buy_date = normalize_timestamp(row.get("buy_price_max_date"))
        if sell is not None and sell_date is None:
            raise AODPInvalidResponseError(f"record {index}: sell price has no timestamp")
        if buy is not None and buy_date is None:
            raise AODPInvalidResponseError(f"record {index}: buy price has no timestamp")
        records.append(
            {
                "item_id": item_id.strip(),
                "city": city.strip(),
                "quality": quality,
                "sell_price_min": sell,
                "sell_price_min_date": sell_date,
                "buy_price_max": buy,
                "buy_price_max_date": buy_date,
            }
        )
    return records


def split_item_batches(
    item_ids: Iterable[str],
    locations: Iterable[str] | None = None,
    qualities: Iterable[int] | None = None,
    max_url_length: int = AODP_URL_MAX_LENGTH,
    host: str = AODP_HOST,
) -> list[list[str]]:
    items = [item.strip() for item in item_ids if isinstance(item, str) and item.strip()]
    if not items:
        raise ValueError("item_ids must contain at least one non-empty item id")
    locs = [x for x in (locations or []) if x]
    quals = [str(x) for x in (qualities or [])]
    query = urlencode({"locations": ",".join(locs), "qualities": ",".join(quals)}) if locs or quals else ""
    suffix = f"?{query}" if query else ""
    prefix = f"https://{host}/api/v2/stats/prices/"
    batches: list[list[str]] = []
    current: list[str] = []
    for item in items:
        candidate = current + [item]
        url = prefix + ",".join(candidate) + ".json" + suffix
        if len(url) <= max_url_length:
            current = candidate
            continue
        if not current:
            raise ValueError(f"item id cannot fit within AODP URL budget: {item}")
        batches.append(current)
        current = [item]
        if len(prefix + item + ".json" + suffix) > max_url_length:
            raise ValueError(f"item id cannot fit within AODP URL budget: {item}")
    if current:
        batches.append(current)
    return batches


class AlbionApiService:
    def __init__(
        self,
        host: str = AODP_HOST,
        timeout: float = AODP_TIMEOUT_SECONDS,
        retry_count: int = AODP_RETRY_COUNT,
        retry_backoff: float = AODP_RETRY_BACKOFF_SECONDS,
        client: Any = httpx,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.host = host
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_backoff = retry_backoff
        self.client = client
        self.sleeper = sleeper

    def _request(self, url: str, params: dict[str, str]) -> Any:
        for attempt in range(self.retry_count + 1):
            try:
                response = self.client.get(url, params=params, timeout=self.timeout)
            except httpx.TimeoutException as exc:
                if attempt < self.retry_count:
                    self.sleeper(self.retry_backoff * (2**attempt))
                    continue
                raise AODPTimeoutError("AODP request timed out") from exc
            except httpx.ConnectError as exc:
                message = str(exc).lower()
                if "name or service not known" in message or "nodename" in message or "getaddrinfo" in message or "temporary failure in name resolution" in message or "failed to resolve" in message:
                    raise AODPDNSError("AODP DNS resolution failed") from exc
                if attempt < self.retry_count:
                    self.sleeper(self.retry_backoff * (2**attempt))
                    continue
                raise AODPConnectionError("AODP connection failed") from exc
            except httpx.RequestError as exc:
                if attempt < self.retry_count:
                    self.sleeper(self.retry_backoff * (2**attempt))
                    continue
                raise AODPConnectionError("AODP request failed") from exc
            if 500 <= response.status_code < 600 and attempt < self.retry_count:
                self.sleeper(self.retry_backoff * (2**attempt))
                continue
            if not 200 <= response.status_code < 300:
                raise AODPHTTPError(response.status_code, f"AODP returned HTTP {response.status_code}")
            return response
        raise AODPConnectionError("AODP request failed")

    def fetch_prices(
        self,
        item_ids: Iterable[str] | str,
        locations: Iterable[str] | None = None,
        qualities: Iterable[int] | None = None,
    ) -> list[dict[str, Any]]:
        if isinstance(item_ids, str):
            item_ids = [item_ids]
        items = list(item_ids)
        batches = split_item_batches(items, locations, qualities, host=self.host)
        params: dict[str, str] = {}
        if locations:
            params["locations"] = ",".join(locations)
        if qualities:
            params["qualities"] = ",".join(map(str, qualities))
        records: list[dict[str, Any]] = []
        for batch in batches:
            path = "/api/v2/stats/prices/" + ",".join(batch) + ".json"
            response = self._request(f"https://{self.host}{path}", params)
            try:
                payload = response.json()
            except ValueError as exc:
                raise AODPInvalidResponseError("AODP returned invalid JSON") from exc
            records.extend(parse_response(payload))
        return records
