from datetime import datetime,timezone
from db.database import Database

def utc_now(): return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
class MarketService:
 def __init__(self,database:Database):self.database=database; database.initialize()
 def save_current(self,record,updated_at=None):
  r=dict(record);r['updated_at']=updated_at or utc_now();self.database.upsert_current(r)
 def save_history(self,record,recorded_at=None):
  r=dict(record);r['recorded_at']=recorded_at or utc_now();self.database.insert_history(r)
 def save_snapshot(self,record,recorded_at=None):
  t=recorded_at or utc_now();self.save_current(record,t);self.save_history(record,t)
 def save_snapshot_batch(self,records,recorded_at=None):
  t=recorded_at or utc_now();n=0
  for r in records:self.save_snapshot(r,t);n+=1
  return n
