from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AODP_NATS_STALE_MINUTES, FRESH_DATA_MAX_AGE_MINUTES, SUPPORTED_SERVERS
from db.database import Database
from services.arbitrage_service import ArbitrageService


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def age_minutes(value: str | None, now: datetime | None = None) -> float | None:
    parsed = parse_ts(value)
    if parsed is None:
        return None
    return max(0.0, ((now or datetime.now(timezone.utc)) - parsed).total_seconds() / 60.0)


def price_stats(db: sqlite3.Connection) -> dict[str, Any]:
    row = db.execute("""SELECT COUNT(*), COUNT(DISTINCT item_id), COUNT(DISTINCT server),
        COUNT(DISTINCT city), COUNT(DISTINCT item_id||'|'||server||'|'||city),
        MIN(recorded_at), MAX(recorded_at) FROM market_price_history""").fetchone()
    return {
        "total_observations": row[0], "unique_items": row[1], "unique_servers": row[2],
        "unique_cities": row[3], "unique_item_server_city": row[4],
        "oldest_observation": row[5], "newest_observation": row[6],
    }


def recent_price_records(db: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    rows = db.execute("""SELECT item_id, server, city, quality, sell_price_min,
        buy_price_max, sell_price_min_date, buy_price_max_date, recorded_at
        FROM market_price_history ORDER BY recorded_at DESC, id DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


def price_integrity(db: sqlite3.Connection) -> dict[str, int]:
    return {
        "negative_price": db.execute("SELECT COUNT(*) FROM market_price_history WHERE sell_price_min < 0 OR buy_price_max < 0").fetchone()[0],
        "zero_price": db.execute("SELECT COUNT(*) FROM market_price_history WHERE sell_price_min = 0 OR buy_price_max = 0").fetchone()[0],
        "negative_quantity": db.execute("SELECT COUNT(*) FROM market_liquidity_orders WHERE quantity < 0").fetchone()[0],
        "numeric_location_rows": db.execute("SELECT COUNT(*) FROM market_liquidity_orders WHERE city GLOB '[0-9]*'").fetchone()[0],
    }


def nats_stats(db: sqlite3.Connection) -> dict[str, Any]:
    row = db.execute("""SELECT COUNT(*), COUNT(DISTINCT item_id), COUNT(DISTINCT city),
        COUNT(DISTINCT server), COUNT(DISTINCT item_id||'|'||server||'|'||city||'|'||quality)
        FROM market_liquidity_orders WHERE status='ACTIVE'""").fetchone()
    groups = db.execute("""SELECT server,item_id,quality,COUNT(DISTINCT city) city_count,
        GROUP_CONCAT(DISTINCT city) cities FROM market_liquidity_orders
        WHERE status='ACTIVE' GROUP BY server,item_id,quality HAVING city_count >= 2
        ORDER BY city_count DESC,item_id LIMIT 25""").fetchall()
    samples = db.execute("""SELECT item_id,server,city,quality,side,price,quantity,expires_at,observed_at
        FROM market_liquidity_orders WHERE status='ACTIVE' ORDER BY last_seen DESC,id DESC LIMIT 10""").fetchall()
    return {
        "active_orders": row[0], "unique_items": row[1], "unique_cities": row[2],
        "unique_servers": row[3], "unique_item_server_city_quality": row[4],
        "multi_city_groups": [dict(r) for r in groups], "samples": [dict(r) for r in samples],
    }


def _fresh(ts_values: list[str | None], max_age: float, now: datetime) -> bool:
    ages = [age_minutes(x, now) for x in ts_values]
    return bool(ages) and all(x is not None and x <= max_age for x in ages)


def _nats_books(db: sqlite3.Connection, server: str, now: datetime) -> dict[tuple[str, int, str], dict[str, Any]]:
    rows = db.execute("""SELECT item_id,quality,city,side,price,quantity,last_seen,expires_at
        FROM market_liquidity_orders WHERE server=? AND status='ACTIVE'""", (server,)).fetchall()
    books: dict[tuple[str, int, str], dict[str, Any]] = defaultdict(lambda: {"sell": [], "buy": []})
    for r in rows:
        if not _fresh([r["last_seen"]], AODP_NATS_STALE_MINUTES, now):
            continue
        if r["expires_at"] and not _fresh([r["expires_at"]], 10**9, now):
            continue
        key = (r["item_id"], r["quality"], r["city"])
        books[key][r["side"]].append(dict(r))
    return books


def nats_candidate_analysis(db: sqlite3.Connection, server: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    books = _nats_books(db, server, now)
    by_item: dict[tuple[str, int], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for (item, quality, city), book in books.items():
        by_item[(item, quality)].append((city, book))
    multi = positive = executable = 0
    examples: list[dict[str, Any]] = []
    for (item, quality), cities in by_item.items():
        if len(cities) < 2:
            continue
        multi += 1
        for buy_city, buy_book in cities:
            sells = buy_book["sell"]
            if not sells:
                continue
            buy = min(sells, key=lambda x: x["price"])
            for sell_city, sell_book in cities:
                if buy_city == sell_city or not sell_book["buy"]:
                    continue
                sell = max(sell_book["buy"], key=lambda x: x["price"])
                if sell["price"] <= buy["price"]:
                    continue
                positive += 1
                qty = min(sum(float(x["quantity"]) for x in sells), sum(float(x["quantity"]) for x in sell_book["buy"]))
                if qty <= 0:
                    continue
                executable += 1
                if len(examples) < 10:
                    examples.append({"item_id": item, "quality": quality, "buy_city": buy_city,
                        "sell_city": sell_city, "buy_price": buy["price"], "sell_price": sell["price"],
                        "executable_quantity": qty, "gross_spread": sell["price"] - buy["price"]})
    return {"multi_city_groups": multi, "positive_gross_pairs": positive,
            "executable_pairs": executable, "examples": examples}


def rest_candidate_analysis(database: Database, server: str) -> dict[str, Any]:
    rows = database.current_prices(server=server)
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[(r["item_id"], r["quality"])].append(r)
    counts = {"groups": 0, "multi_city_groups": 0, "positive_gross_pairs": 0,
              "fresh_pairs": 0, "executable_pairs": 0, "filtered_freshness": 0,
              "filtered_quantity": 0}
    examples: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for (item, quality), item_rows in grouped.items():
        counts["groups"] += 1
        if len({r["city"] for r in item_rows}) >= 2:
            counts["multi_city_groups"] += 1
        for buy in item_rows:
            bp = buy.get("sell_price_min")
            if not isinstance(bp, (int, float)) or bp <= 0:
                continue
            for sell in item_rows:
                if buy["city"] == sell["city"]:
                    continue
                sp = sell.get("buy_price_max")
                if not isinstance(sp, (int, float)) or sp <= bp:
                    continue
                counts["positive_gross_pairs"] += 1
                if not _fresh([buy.get("sell_price_min_date"), sell.get("buy_price_max_date")], FRESH_DATA_MAX_AGE_MINUTES, now):
                    counts["filtered_freshness"] += 1
                    continue
                counts["fresh_pairs"] += 1
                bq = database.liquidity_orders(server=server, item_id=item, city=buy["city"], quality=quality, side="sell", stale_minutes=AODP_NATS_STALE_MINUTES)
                sq = database.liquidity_orders(server=server, item_id=item, city=sell["city"], quality=quality, side="buy", stale_minutes=AODP_NATS_STALE_MINUTES)
                qty = min(sum(float(x["quantity"]) for x in bq), sum(float(x["quantity"]) for x in sq))
                if qty <= 0:
                    counts["filtered_quantity"] += 1
                    continue
                counts["executable_pairs"] += 1
                if len(examples) < 10:
                    examples.append({"item_id": item, "quality": quality, "buy_city": buy["city"], "sell_city": sell["city"],
                        "buy_price": bp, "sell_price": sp, "executable_quantity": qty, "gross_spread": sp-bp})
    service = ArbitrageService(database, server).opportunities(quality=1, quantity=1, sort="spread", limit=100)
    counts["service_candidates"] = len(service)
    return {"counts": counts, "examples": examples, "service_candidates": service[:10]}


def rest_vs_nats(db: sqlite3.Connection, server: str, limit: int = 20) -> list[dict[str, Any]]:
    rest = db.execute("""SELECT item_id,quality,city,sell_price_min,buy_price_max
        FROM market_prices WHERE server=? AND (sell_price_min IS NOT NULL OR buy_price_max IS NOT NULL)""", (server,)).fetchall()
    nats: dict[tuple[str,int,str], dict[str,float | None]] = defaultdict(lambda: {"sell": None,"buy":None})
    for r in db.execute("""SELECT item_id,quality,city,side,price FROM market_liquidity_orders
        WHERE server=? AND status='ACTIVE'""", (server,)).fetchall():
        key=(r["item_id"],r["quality"],r["city"])
        if r["side"] == "sell": nats[key]["sell"] = min(nats[key]["sell"], r["price"]) if nats[key]["sell"] is not None else r["price"]
        else: nats[key]["buy"] = max(nats[key]["buy"], r["price"]) if nats[key]["buy"] is not None else r["price"]
    out=[]
    for r in rest:
        k=(r["item_id"],r["quality"],r["city"]); n=nats.get(k)
        if not n: continue
        out.append({"item_id":r["item_id"],"quality":r["quality"],"city":r["city"],
            "rest_sell":r["sell_price_min"],"nats_lowest_sell":n["sell"],
            "rest_buy":r["buy_price_max"],"nats_highest_buy":n["buy"],
            "sell_delta": (r["sell_price_min"]-n["sell"]) if r["sell_price_min"] is not None and n["sell"] is not None else None,
            "buy_delta": (r["buy_price_max"]-n["buy"]) if r["buy_price_max"] is not None and n["buy"] is not None else None})
    return out[:limit]


def analyze(path: str | Path, server: str) -> dict[str, Any]:
    if server not in SUPPORTED_SERVERS:
        raise ValueError(f"unsupported server: {server}")
    database = Database(path); database.initialize()
    with sqlite3.connect(path) as raw:
        raw.row_factory = sqlite3.Row
        return {"database": str(path), "server": server, "price_stats": price_stats(raw),
            "recent_price_records": recent_price_records(raw), "price_integrity": price_integrity(raw),
            "nats_stats": nats_stats(raw), "rest_candidates": rest_candidate_analysis(database, server),
            "nats_candidates": nats_candidate_analysis(raw, server), "rest_vs_nats": rest_vs_nats(raw, server)}


def main() -> None:
    p=argparse.ArgumentParser(description="Phase 23 real REST-vs-NATS arbitrage diagnostics")
    p.add_argument("--db", default="data/phase23.db"); p.add_argument("--server", default="east", choices=tuple(SUPPORTED_SERVERS))
    p.add_argument("--output", default="phase23-analysis.json")
    args=p.parse_args(); result=analyze(args.db,args.server)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    print(text); Path(args.output).write_text(text,encoding="utf-8")

if __name__ == "__main__": main()
