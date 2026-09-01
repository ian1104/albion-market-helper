from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AODP_NATS_STALE_MINUTES, FRESH_DATA_MAX_AGE_MINUTES, SUPPORTED_SERVERS
from db.database import Database
from services.arbitrage_service import ArbitrageService


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _age_minutes(value: str | None, now: datetime | None = None) -> float | None:
    parsed = _parse_ts(value)
    if parsed is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0.0, (current - parsed).total_seconds() / 60.0)


def observation_stats(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        """SELECT COUNT(*) total, COUNT(DISTINCT item_id) items,
                  COUNT(DISTINCT city) cities, COUNT(DISTINCT server) servers,
                  COUNT(DISTINCT item_id || '|' || city) item_city
           FROM market_price_history"""
    ).fetchone()
    dates = connection.execute(
        "SELECT MIN(recorded_at), MAX(recorded_at) FROM market_price_history"
    ).fetchone()
    by_server = connection.execute(
        "SELECT server, COUNT(*) FROM market_price_history GROUP BY server ORDER BY server"
    ).fetchall()
    by_city = connection.execute(
        "SELECT city, COUNT(*) FROM market_price_history GROUP BY city ORDER BY COUNT(*) DESC, city LIMIT 20"
    ).fetchall()
    by_item = connection.execute(
        "SELECT item_id, COUNT(*) FROM market_price_history GROUP BY item_id ORDER BY COUNT(*) DESC, item_id LIMIT 20"
    ).fetchall()
    return {
        "total_observations": row[0], "unique_items": row[1], "unique_cities": row[2],
        "unique_servers": row[3], "unique_item_city": row[4],
        "oldest_observation": dates[0], "newest_observation": dates[1],
        "observations_per_server": dict(by_server),
        "observations_per_city": dict(by_city),
        "observations_per_item": dict(by_item),
    }


def recent_records(connection: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT item_id, city, server, quality, sell_price_min, sell_price_min_date,
                  buy_price_max, buy_price_max_date, recorded_at
           FROM market_price_history ORDER BY recorded_at DESC, id DESC LIMIT ?""", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def history_samples(connection: sqlite3.Connection, limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    items = connection.execute(
        "SELECT item_id, COUNT(*) n FROM market_price_history GROUP BY item_id ORDER BY n DESC, item_id LIMIT ?",
        (limit,),
    ).fetchall()
    result: dict[str, list[dict[str, Any]]] = {}
    for item, _count in items:
        rows = connection.execute(
            """SELECT recorded_at, city, server, quality, sell_price_min, buy_price_max
               FROM market_price_history WHERE item_id=? ORDER BY recorded_at, id LIMIT 50""", (item,)
        ).fetchall()
        result[item] = [dict(r) for r in rows]
    return result


def integrity(connection: sqlite3.Connection) -> dict[str, Any]:
    checks = {
        "negative_price": connection.execute("SELECT COUNT(*) FROM market_price_history WHERE sell_price_min < 0 OR buy_price_max < 0").fetchone()[0],
        "zero_price": connection.execute("SELECT COUNT(*) FROM market_price_history WHERE sell_price_min = 0 OR buy_price_max = 0").fetchone()[0],
        "negative_liquidity_quantity": connection.execute("SELECT COUNT(*) FROM market_liquidity_orders WHERE quantity < 0").fetchone()[0],
        "unknown_location_numeric": connection.execute(
            "SELECT COUNT(*) FROM market_liquidity_orders WHERE city GLOB '[0-9]*'"
        ).fetchone()[0],
        "liquidity_current_rows": connection.execute("SELECT COUNT(*) FROM market_liquidity_orders").fetchone()[0],
        "liquidity_observations": connection.execute("SELECT COUNT(*) FROM market_liquidity_order_observations").fetchone()[0],
    }
    checks["nonzero_price_violation"] = checks["negative_price"] + checks["zero_price"]
    return checks


def multi_city_groups(connection: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT server, item_id, quality, COUNT(DISTINCT city) city_count,
                  GROUP_CONCAT(DISTINCT city) cities
           FROM market_liquidity_orders
           WHERE status='ACTIVE'
           GROUP BY server, item_id, quality
           HAVING COUNT(DISTINCT city) >= 2
           ORDER BY city_count DESC, item_id
           LIMIT ?""", (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def arbitrage_diagnostics(database: Database, server: str, *, max_age_minutes: float) -> dict[str, Any]:
    rows = database.current_prices(server=server)
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["item_id"], row["quality"])].append(row)

    pair_count = before_fees = fresh_pairs = executable_pairs = 0
    stale_pairs = quantity_filtered = 0
    examples: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for (item_id, quality), item_rows in grouped.items():
        for buy in item_rows:
            buy_price = buy.get("sell_price_min")
            if not isinstance(buy_price, (int, float)) or buy_price <= 0:
                continue
            for sell in item_rows:
                if buy["city"] == sell["city"]:
                    continue
                sell_price = sell.get("buy_price_max")
                if not isinstance(sell_price, (int, float)) or sell_price <= buy_price:
                    continue
                pair_count += 1
                before_fees += 1
                buy_age = _age_minutes(buy.get("sell_price_min_date"), now)
                sell_age = _age_minutes(sell.get("buy_price_max_date"), now)
                fresh = buy_age is not None and sell_age is not None and max(buy_age, sell_age) <= max_age_minutes
                if not fresh:
                    stale_pairs += 1
                    continue
                fresh_pairs += 1
                buy_orders = database.liquidity_orders(server=server, item_id=item_id, city=buy["city"], quality=quality, side="sell", stale_minutes=AODP_NATS_STALE_MINUTES)
                sell_orders = database.liquidity_orders(server=server, item_id=item_id, city=sell["city"], quality=quality, side="buy", stale_minutes=AODP_NATS_STALE_MINUTES)
                buy_qty = sum(float(x["quantity"]) for x in buy_orders)
                sell_qty = sum(float(x["quantity"]) for x in sell_orders)
                executable = min(buy_qty, sell_qty)
                if executable <= 0:
                    quantity_filtered += 1
                    continue
                executable_pairs += 1
                if len(examples) < 10:
                    examples.append({"item_id": item_id, "quality": quality, "buy_city": buy["city"], "sell_city": sell["city"], "buy_price": buy_price, "sell_price": sell_price, "spread": sell_price - buy_price, "executable_quantity": executable, "buy_age_minutes": buy_age, "sell_age_minutes": sell_age})
    service_result = ArbitrageService(database, server).opportunities(quality=1, quantity=1, sort="spread", limit=100)
    return {
        "candidate_pairs_with_positive_gross_spread": pair_count,
        "profitable_before_fees": before_fees,
        "profitable_after_fees": None,
        "fresh_pairs": fresh_pairs,
        "filtered_by_freshness": stale_pairs,
        "executable_pairs": executable_pairs,
        "filtered_by_quantity": quantity_filtered,
        "filtered_by_roi": None,
        "service_candidate_count": len(service_result),
        "service_candidates": service_result[:10],
        "live_executable_examples": examples,
        "cost_model": "unconfigured; net fees/ROI unavailable by design",
    }


def analyze(path: str | Path, server: str = "east") -> dict[str, Any]:
    if server not in SUPPORTED_SERVERS:
        raise ValueError(f"unsupported server: {server}")
    database = Database(path)
    database.initialize()
    with sqlite3.connect(path) as raw:
        raw.row_factory = sqlite3.Row
        result = {
            "database": str(path),
            "observation_stats": observation_stats(raw),
            "recent_real_price_records": recent_records(raw),
            "price_history_samples": history_samples(raw),
            "integrity": integrity(raw),
            "multi_city_groups": multi_city_groups(raw),
            "arbitrage": arbitrage_diagnostics(database, server, max_age_minutes=FRESH_DATA_MAX_AGE_MINUTES),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze real AODP market history and arbitrage candidates in an existing SQLite database.")
    parser.add_argument("--db", default="data/albion_market.db")
    parser.add_argument("--server", default="east", choices=tuple(SUPPORTED_SERVERS))
    args = parser.parse_args()
    print(json.dumps(analyze(args.db, args.server), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
