from datetime import datetime, timezone
from db.database import Database


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class MarketService:
    def __init__(self, database: Database):
        self.database = database
        database.initialize()

    def save_current(self, record, updated_at=None):
        row = dict(record)
        row["updated_at"] = updated_at or utc_now()
        self.database.upsert_current(row)

    def save_history(self, record, recorded_at=None):
        row = dict(record)
        row["recorded_at"] = recorded_at or utc_now()
        self.database.insert_history(row)

    def save_snapshot(self, record, recorded_at=None):
        timestamp = recorded_at or utc_now()
        self.save_current(record, timestamp)
        self.save_history(record, timestamp)

    def save_snapshot_batch(self, records, recorded_at=None):
        timestamp = recorded_at or utc_now()
        count = 0
        for record in records:
            self.save_snapshot(record, timestamp)
            count += 1
        return count
