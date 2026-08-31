"""Centralized application configuration."""
from __future__ import annotations

import os

SUPPORTED_SERVERS = {
    "east": "east.albion-online-data.com",
    "west": "west.albion-online-data.com",
    "europe": "europe.albion-online-data.com",
}
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
WATCHLIST = tuple(x.strip() for x in os.getenv("WATCHLIST", ",".join(DEFAULT_WATCHLIST)).split(",") if x.strip())
CITIES = tuple(x.strip() for x in os.getenv("CITIES", ",".join(DEFAULT_CITIES)).split(",") if x.strip())
QUALITIES = tuple(int(x.strip()) for x in os.getenv("QUALITIES", "1").split(",") if x.strip())
if not WATCHLIST or not CITIES or not QUALITIES or any(q < 1 for q in QUALITIES):
    raise ValueError("WATCHLIST, CITIES, and QUALITIES must contain valid non-empty values")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/albion_market.db")
