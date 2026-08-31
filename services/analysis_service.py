from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import sqrt
from statistics import median
from typing import Any

from config import ALBION_SERVER, CITIES, QUALITIES, SUPPORTED_SERVERS, WATCHLIST
from db.database import Database

RANGES = {"12h": timedelta(hours=12), "24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "all": None}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def range_bounds(range_name: str, now: datetime | None = None) -> tuple[str | None, str | None]:
    if range_name not in RANGES:
        raise ValueError(f"unsupported range: {range_name}")
    if RANGES[range_name] is None:
        return None, None
    end = now or utc_now()
    start = end - RANGES[range_name]
    return start.isoformat(timespec="seconds").replace("+00:00", "Z"), end.isoformat(timespec="seconds").replace("+00:00", "Z")


def _numeric(rows: list[dict[str, Any]], field: str) -> list[float]:
    return [float(row[field]) for row in rows if row.get(field) is not None]


def _stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "max": None, "average": None, "median": None, "latest": None, "first": None, "stddev": None, "p25": None, "p75": None}
    ordered = values
    mean = sum(values) / len(values)
    stddev = sqrt(sum((x - mean) ** 2 for x in values) / len(values)) if len(values) > 1 else 0.0
    ordered_sorted = sorted(values)
    def percentile(p: float) -> float:
        if len(ordered_sorted) == 1:
            return ordered_sorted[0]
        pos = (len(ordered_sorted) - 1) * p
        lo, hi = int(pos), min(int(pos) + 1, len(ordered_sorted) - 1)
        frac = pos - lo
        return ordered_sorted[lo] + (ordered_sorted[hi] - ordered_sorted[lo]) * frac
    return {
        "min": min(values), "max": max(values), "average": mean,
        "median": float(median(values)), "latest": ordered[-1], "first": ordered[0],
        "stddev": stddev, "p25": percentile(0.25), "p75": percentile(0.75),
    }


def _change(first: float | None, latest: float | None) -> dict[str, float | None]:
    if first is None or latest is None:
        return {"absolute": None, "percent": None}
    absolute = latest - first
    return {"absolute": absolute, "percent": (absolute / first * 100.0) if first != 0 else None}


class AnalysisService:
    def __init__(self, database: Database, server: str = ALBION_SERVER):
        if server not in SUPPORTED_SERVERS:
            raise ValueError(f"unsupported server: {server}")
        self.database = database
        self.server = server
        database.initialize()

    def _bounds(self, range_name: str, start: str | None, end: str | None):
        if start or end:
            if start and end and parse_ts(start) > parse_ts(end):
                raise ValueError("start must not be later than end")
            return start, end
        return range_bounds(range_name)

    def history(self, item_id: str, city: str | None, quality: int, range_name="24h", start=None, end=None):
        start, end = self._bounds(range_name, start, end)
        return self.database.history(item_id, city, quality, start, end, server=self.server)

    def statistics(self, item_id: str, city: str, quality: int, range_name="24h", start=None, end=None):
        rows = self.history(item_id, city, quality, range_name, start, end)
        sell = _numeric(rows, "sell_price_min")
        buy = _numeric(rows, "buy_price_max")
        sell_stats, buy_stats = _stats(sell), _stats(buy)
        sufficient = bool(sell or buy)
        return {
            "server": self.server, "item_id": item_id, "city": city, "quality": quality,
            "range": range_name, "data_sufficient": sufficient, "records": len(rows),
            "statistics": {"sell": sell_stats, "buy": buy_stats},
            "change": {"sell": _change(sell_stats["first"], sell_stats["latest"]), "buy": _change(buy_stats["first"], buy_stats["latest"])},
        }

    def trend(self, item_id: str, city: str, quality: int, range_name="24h", ma_windows=(3, 6, 12), start=None, end=None):
        rows = self.history(item_id, city, quality, range_name, start, end)
        series = [{"recorded_at": r["recorded_at"], "sell_price_min": r.get("sell_price_min"), "buy_price_max": r.get("buy_price_max")} for r in rows]
        sell = [x["sell_price_min"] for x in series if x["sell_price_min"] is not None]
        stats = _stats(sell)
        for row in series:
            row["moving_average"] = {}
        sell_points = [x for x in series if x["sell_price_min"] is not None]
        for i, row in enumerate(sell_points):
            for window in ma_windows:
                if i + 1 >= window:
                    vals = [p["sell_price_min"] for p in sell_points[i + 1 - window:i + 1]]
                    row["moving_average"][f"ma{window}"] = sum(vals) / window
        return {
            "server": self.server, "item_id": item_id, "city": city, "quality": quality, "range": range_name,
            "data_sufficient": len(sell) >= 1, "records": len(rows), "statistics": stats,
            "change": _change(stats["first"], stats["latest"]), "series": series,
        }

    def quality(self, range_name="all", start=None, end=None):
        start, end = self._bounds(range_name, start, end)
        where = ["server = ?"]
        params: list[Any] = [self.server]
        if start: where.append("recorded_at >= ?"); params.append(start)
        if end: where.append("recorded_at <= ?"); params.append(end)
        clause = " AND ".join(where)
        with self.database.connect() as c:
            total = c.execute(f"SELECT COUNT(*) FROM market_price_history WHERE {clause}", params).fetchone()[0]
            dims = c.execute(f"SELECT COUNT(DISTINCT item_id), COUNT(DISTINCT city), COUNT(DISTINCT quality), MIN(recorded_at), MAX(recorded_at) FROM market_price_history WHERE {clause}", params).fetchone()
            nulls = c.execute(f"SELECT SUM(CASE WHEN sell_price_min IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN buy_price_max IS NULL THEN 1 ELSE 0 END) FROM market_price_history WHERE {clause}", params).fetchone()
            duplicate = c.execute(f"""SELECT COALESCE(SUM(n - 1), 0) FROM (
                SELECT item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,COUNT(*) n
                FROM market_price_history WHERE {clause}
                GROUP BY item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date
                HAVING COUNT(*) > 1)""", params).fetchone()[0]
            per_item = [dict(r) for r in c.execute(f"SELECT item_id, COUNT(*) records FROM market_price_history WHERE {clause} GROUP BY item_id ORDER BY item_id", params)]
            per_city = [dict(r) for r in c.execute(f"SELECT city, COUNT(*) records FROM market_price_history WHERE {clause} GROUP BY city ORDER BY city", params)]
            per_quality = [dict(r) for r in c.execute(f"SELECT quality, COUNT(*) records FROM market_price_history WHERE {clause} GROUP BY quality ORDER BY quality", params)]
            per_hour = [dict(r) for r in c.execute(f"SELECT substr(recorded_at,1,13) hour, COUNT(*) records FROM market_price_history WHERE {clause} GROUP BY hour ORDER BY hour", params)]
            per_day = [dict(r) for r in c.execute(f"SELECT substr(recorded_at,1,10) day, COUNT(*) records FROM market_price_history WHERE {clause} GROUP BY day ORDER BY day", params)]
        runs = self.database.collection_runs(self.server, start, end)
        successful = [r for r in runs if r["success"]]
        failed = [r for r in runs if not r["success"]]
        expected_per_run = len(WATCHLIST) * len(CITIES) * len(QUALITIES)
        expected = expected_per_run * len(successful)
        coverage = (total / expected * 100.0) if expected else None
        return {
            "server": self.server, "range": range_name, "total_records": total,
            "unique_items": dims[0], "unique_cities": dims[1], "unique_qualities": dims[2],
            "earliest_timestamp": dims[3], "latest_timestamp": dims[4],
            "null_sell_price_count": nulls[0] or 0, "null_buy_price_count": nulls[1] or 0,
            "invalid_ignored_records": 0, "duplicate_payload_count": duplicate,
            "records_per_item": per_item, "records_per_city": per_city, "records_per_quality": per_quality,
            "records_per_hour": per_hour, "records_per_day": per_day,
            "coverage": {"successful_runs": len(successful), "failed_runs": len(failed), "expected_records_per_successful_run": expected_per_run, "actual_records": total, "coverage_percent": coverage},
            "data_sufficient": total > 0,
        }

    def spread(self, item_id: str, quality: int, range_name="24h", start=None, end=None):
        start, end = self._bounds(range_name, start, end)
        rows = self.database.history(item_id, None, quality, start, end, server=self.server)
        latest_by_city: dict[str, dict[str, Any]] = {}
        for row in rows:
            latest_by_city[row["city"]] = row
        usable = [r for r in latest_by_city.values() if r.get("sell_price_min") is not None]
        if len(usable) < 2:
            return {"server": self.server, "item_id": item_id, "quality": quality, "range": range_name, "data_sufficient": False, "reason": "insufficient_historical_data", "cities": [], "spread": None}
        lowest = min(usable, key=lambda r: r["sell_price_min"])
        highest = max(usable, key=lambda r: r["sell_price_min"])
        low, high = float(lowest["sell_price_min"]), float(highest["sell_price_min"])
        absolute = high - low
        pct = absolute / low * 100.0 if low else None
        gross = []
        for buy_city in usable:
            buy_price = buy_city.get("sell_price_min")
            for sell_city in usable:
                sell_price = sell_city.get("buy_price_max")
                if buy_city["city"] == sell_city["city"] or buy_price is None or sell_price is None:
                    continue
                gross.append({"buy_city": buy_city["city"], "sell_city": sell_city["city"], "buy_price": buy_price, "sell_price": sell_price, "gross_spread": sell_price-buy_price, "spread_percent": ((sell_price-buy_price)/buy_price*100.0 if buy_price else None)})
        gross.sort(key=lambda x: x["gross_spread"], reverse=True)
        return {
            "server": self.server, "item_id": item_id, "quality": quality, "range": range_name, "data_sufficient": True,
            "cities": [{"city": r["city"], "sell_price_min": r.get("sell_price_min"), "buy_price_max": r.get("buy_price_max"), "recorded_at": r["recorded_at"]} for r in sorted(usable, key=lambda x: x["city"])],
            "spread": {"highest_city": highest["city"], "lowest_city": lowest["city"], "absolute": absolute, "percent": pct},
            "arbitrage_foundation": gross[:20],
            "note": "Gross spread only; taxes, fees, transport and other costs are not included.",
        }

    def spread_stability(self, item_id: str, quality: int, range_name="24h", start=None, end=None):
        start, end = self._bounds(range_name, start, end)
        rows = self.database.history(item_id, None, quality, start, end, server=self.server)
        by_time: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if row.get("sell_price_min") is not None or row.get("buy_price_max") is not None:
                by_time[row["recorded_at"]].append(row)
        spreads: list[float] = []
        gross: list[float] = []
        for _, snapshot in sorted(by_time.items()):
            sells = [r["sell_price_min"] for r in snapshot if r.get("sell_price_min") is not None]
            if len(sells) >= 2:
                spreads.append(float(max(sells) - min(sells)))
            for buy in snapshot:
                if buy.get("sell_price_min") is None: continue
                for sell in snapshot:
                    if buy["city"] != sell["city"] and sell.get("buy_price_max") is not None:
                        gross.append(float(sell["buy_price_max"] - buy["sell_price_min"]))
        if not spreads:
            return {"server": self.server, "item_id": item_id, "quality": quality, "range": range_name, "data_sufficient": False, "reason": "insufficient_historical_data", "observations": 0}
        positive = [x for x in gross if x > 0]
        mean = sum(spreads) / len(spreads)
        vol = sqrt(sum((x-mean)**2 for x in spreads)/len(spreads)) if len(spreads)>1 else 0.0
        return {"server": self.server, "item_id": item_id, "quality": quality, "range": range_name, "data_sufficient": True, "observations": len(spreads), "average_spread": mean, "minimum_spread": min(spreads), "maximum_spread": max(spreads), "spread_volatility": vol, "positive_spread_ratio": (len(positive)/len(gross)*100.0 if gross else None)}
