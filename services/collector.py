from __future__ import annotations

from threading import Lock
from time import monotonic, sleep

from config import AODP_REQUEST_DELAY_SECONDS, ALBION_SERVER, CITIES, QUALITIES, WATCHLIST
from services.albion_api import AlbionApiService
from services.market_service import MarketService, utc_now


class Collector:
    def __init__(self, api: AlbionApiService, market_service: MarketService,
                 watchlist=WATCHLIST, cities=CITIES, qualities=QUALITIES,
                 request_delay: float = AODP_REQUEST_DELAY_SECONDS, server: str = ALBION_SERVER):
        self.api = api
        self.market_service = market_service
        self.watchlist = tuple(watchlist)
        self.cities = tuple(cities)
        self.qualities = tuple(qualities)
        self.request_delay = request_delay
        self.server = server
        self._lock = Lock()

    def run(self) -> dict:
        if not self._lock.acquire(blocking=False):
            return {"success": False, "skipped": True, "error": "collection already running"}
        started = utc_now()
        started_monotonic = monotonic()
        run_id = self.market_service.database.start_collection_run(started, self.server)
        received = saved = 0
        try:
            batches = self._batches()
            for index, batch in enumerate(batches):
                if index:
                    sleep(self.request_delay)
                records = self.api.fetch_prices(batch, self.cities, self.qualities)
                received += len(records)
                saved += self.market_service.save_snapshot_batch(records)
            finished = utc_now()
            duration = monotonic() - started_monotonic
            self.market_service.database.finish_collection_run(
                run_id, finished_at=finished, success=True,
                records_received=received, records_saved=saved, error=None,
                duration_seconds=duration,
            )
            return {"success": True, "skipped": False, "records_received": received,
                    "records_saved": saved, "started_at": started, "finished_at": finished,
                    "duration_seconds": duration}
        except Exception as exc:
            finished = utc_now()
            duration = monotonic() - started_monotonic
            self.market_service.database.finish_collection_run(
                run_id, finished_at=finished, success=False,
                records_received=received, records_saved=saved, error=str(exc),
                duration_seconds=duration,
            )
            raise
        finally:
            self._lock.release()

    def _batches(self):
        from services.albion_api import split_item_batches
        return split_item_batches(self.watchlist, self.cities, self.qualities, host=self.api.host)
