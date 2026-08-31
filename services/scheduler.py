from __future__ import annotations

import threading
from config import COLLECTOR_INTERVAL_SECONDS


class CollectorScheduler:
    def __init__(self, collector, interval_seconds: int = COLLECTOR_INTERVAL_SECONDS):
        self.collector = collector
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, initial_collection: bool = True):
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        if initial_collection:
            self.collector.run()
        self._thread = threading.Thread(target=self._loop, name="collector-scheduler", daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        while not self._stop.wait(self.interval_seconds):
            try:
                self.collector.run()
            except Exception:
                continue

    def stop(self, timeout: float = 5.0):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
        self._thread = None

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())
