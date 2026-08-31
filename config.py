"""Centralized application configuration."""
from __future__ import annotations

import os

SUPPORTED_SERVERS = {
    "east": "east.albion-online-data.com",
    "west": "west.albion-online-data.com",
    "europe": "europe.albion-online-data.com",
}
SERVER_DISPLAY_NAMES = {
    "east": "Asia / East",
    "west": "Americas / West",
    "europe": "Europe",
}
AODP_NATS_PORTS = {
    "east": 24222,
    "west": 4222,
    "europe": 34222,
}
# AODP MarketOrder.LocationId values are marketplace identifiers, not the
# numeric zone IDs used by the world map. These values are the canonical
# market-location IDs used by the Albion Data ecosystem and match the live
# IDs observed on marketorders.deduped. Unknown IDs remain numeric instead of
# being guessed.
#
# Source: albiondata-sql Location enum (public historical implementation),
# corroborated by the current AODP live payloads observed in Phase 18/19.
# Source metadata is kept below so a future world-metadata refresh can replace
# this static compatibility map without changing the adapter API.
AODP_LOCATION_NAMES = {
    "7": "Thetford",
    "1002": "Lymhurst",
    "2004": "Bridgewatch",
    "3003": "Black Market",
    "3005": "Caerleon",
    "3010": "Martlock",
    "4002": "Fort Sterling",
}
AODP_LOCATION_METADATA_SOURCE = "albiondata-sql Location enum + live AODP payload corroboration"
AODP_LOCATION_METADATA_VERSION = "market-location-ids-2026-09"
AODP_NATS_HOST = os.getenv("AODP_NATS_HOST", "nats.albion-online-data.com")
AODP_NATS_SUBJECT = os.getenv("AODP_NATS_SUBJECT", "marketorders.deduped")
AODP_NATS_ENABLED = os.getenv("AODP_NATS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_WATCHLIST = ("T4_BAG", "T5_BAG")
DEFAULT_CITIES = (
    "Caerleon",
    "Bridgewatch",
    "Fort Sterling",
    "Lymhurst",
    "Martlock",
    "Thetford",
    "Brecilien",
)
DEFAULT_QUALITIES = (1,)


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    value = float(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


ALBION_SERVER = os.getenv("ALBION_SERVER", "east").strip().lower()
if ALBION_SERVER not in SUPPORTED_SERVERS:
    raise ValueError(
        f"Invalid ALBION_SERVER={ALBION_SERVER!r}; expected one of: {', '.join(SUPPORTED_SERVERS)}"
    )
AODP_HOST = SUPPORTED_SERVERS[ALBION_SERVER]
AODP_TIMEOUT_SECONDS = _env_float("AODP_TIMEOUT_SECONDS", 10.0, 0.1)
AODP_RETRY_COUNT = _env_int("AODP_RETRY_COUNT", 2, 0)
AODP_RETRY_BACKOFF_SECONDS = _env_float("AODP_RETRY_BACKOFF_SECONDS", 0.5, 0.0)
AODP_REQUEST_DELAY_SECONDS = _env_float("AODP_REQUEST_DELAY_SECONDS", 0.5, 0.0)
AODP_URL_MAX_LENGTH = _env_int("AODP_URL_MAX_LENGTH", 4096, 256)
COLLECTOR_INTERVAL_SECONDS = _env_int("COLLECTOR_INTERVAL_SECONDS", 1800, 1)
FRESH_DATA_MAX_AGE_MINUTES = _env_float("FRESH_DATA_MAX_AGE_MINUTES", 30.0, 0.0)
AODP_NATS_STALE_MINUTES = _env_float("AODP_NATS_STALE_MINUTES", 15.0, 0.0)
AODP_NATS_RECONNECT_SECONDS = _env_float("AODP_NATS_RECONNECT_SECONDS", 1.0, 0.1)
AODP_NATS_RECONNECT_MAX_SECONDS = _env_float("AODP_NATS_RECONNECT_MAX_SECONDS", 60.0, 1.0)
AODP_NATS_SERVERS = tuple(x.strip().lower() for x in os.getenv("AODP_NATS_SERVERS", ALBION_SERVER).split(",") if x.strip())
if not AODP_NATS_SERVERS or any(x not in SUPPORTED_SERVERS for x in AODP_NATS_SERVERS):
    raise ValueError("AODP_NATS_SERVERS must contain only supported server identifiers")
WATCHLIST = tuple(x.strip() for x in os.getenv("WATCHLIST", ",".join(DEFAULT_WATCHLIST)).split(",") if x.strip())
CITIES = tuple(x.strip() for x in os.getenv("CITIES", ",".join(DEFAULT_CITIES)).split(",") if x.strip())
QUALITIES = tuple(int(x.strip()) for x in os.getenv("QUALITIES", "1").split(",") if x.strip())
if not WATCHLIST or not CITIES or not QUALITIES or any(q < 1 for q in QUALITIES):
    raise ValueError("WATCHLIST, CITIES, and QUALITIES must contain valid non-empty values")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/albion_market.db")
