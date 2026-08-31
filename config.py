"""Application configuration."""

import os

SUPPORTED_SERVERS = {
    "east": "east.albion-online-data.com",
    "west": "west.albion-online-data.com",
    "europe": "europe.albion-online-data.com",
}


def _server() -> str:
    value = os.getenv("ALBION_SERVER", "east").strip().lower()
    if value not in SUPPORTED_SERVERS:
        raise ValueError(
            f"Invalid ALBION_SERVER={value!r}; expected one of: {', '.join(SUPPORTED_SERVERS)}"
        )
    return value


ALBION_SERVER = _server()
AODP_HOST = SUPPORTED_SERVERS[ALBION_SERVER]
AODP_TIMEOUT_SECONDS = float(os.getenv("AODP_TIMEOUT_SECONDS", "10"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/albion_market.db")
