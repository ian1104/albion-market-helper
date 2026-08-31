from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from config import AODP_NATS_STALE_MINUTES


@dataclass(frozen=True)
class OrderLifecycleManager:
    """Applies observation/expiry rules to persisted market orders.

    AODP does not publish a guaranteed fill event, so lifecycle state is an
    observational state, not proof that an order still exists in-game.
    """

    database: object
    stale_minutes: float = AODP_NATS_STALE_MINUTES

    def __post_init__(self) -> None:
        if self.stale_minutes < 0:
            raise ValueError("stale_minutes must be >= 0")

    def refresh(self, *, server: str | None = None, now: str | None = None) -> dict[str, int]:
        return self.database.refresh_liquidity_order_status(
            server=server,
            now=now,
            stale_minutes=self.stale_minutes,
        )

    def is_active(self, order: dict, *, now: str | None = None) -> bool:
        current = datetime.fromisoformat(
            (now or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        if order.get("status") != "ACTIVE":
            return False
        expires_at = order.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at.replace("Z", "+00:00")).astimezone(timezone.utc) <= current:
                    return False
            except ValueError:
                return False
        return True
