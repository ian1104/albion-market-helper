from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any
from config import DATABASE_PATH

SCHEMA='''
CREATE TABLE IF NOT EXISTS market_prices (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL,
 sell_price_min INTEGER, sell_price_min_date TEXT,
 buy_price_max INTEGER, buy_price_max_date TEXT,
 updated_at TEXT NOT NULL,
 UNIQUE(item_id, city, quality)
);
CREATE TABLE IF NOT EXISTS market_price_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 item_id TEXT NOT NULL, city TEXT NOT NULL, quality INTEGER NOT NULL,
 sell_price_min INTEGER, sell_price_min_date TEXT,
 buy_price_max INTEGER, buy_price_max_date TEXT,
 recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_price_history_lookup
ON market_price_history(item_id, city, quality, recorded_at);
'''

class Database:
 def __init__(self,path: str|Path=DATABASE_PATH): self.path=Path(path)
 def connect(self):
  self.path.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
 def initialize(self):
  with self.connect() as c: c.executescript(SCHEMA)
 def upsert_current(self,r:dict[str,Any]):
  self.initialize()
  with self.connect() as c: c.execute('''INSERT INTO market_prices(item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(item_id,city,quality) DO UPDATE SET sell_price_min=excluded.sell_price_min,sell_price_min_date=excluded.sell_price_min_date,buy_price_max=excluded.buy_price_max,buy_price_max_date=excluded.buy_price_max_date,updated_at=excluded.updated_at''', self._values(r,'updated_at'))
 def insert_history(self,r):
  self.initialize()
  with self.connect() as c: c.execute('''INSERT INTO market_price_history(item_id,city,quality,sell_price_min,sell_price_min_date,buy_price_max,buy_price_max_date,recorded_at) VALUES(?,?,?,?,?,?,?,?)''', self._values(r,'recorded_at'))
 @staticmethod
 def _values(r,t): return (r['item_id'],r['city'],r['quality'],r.get('sell_price_min'),r.get('sell_price_min_date'),r.get('buy_price_max'),r.get('buy_price_max_date'),r[t])
 def current_prices(self,item_id=None,city=None,quality=None): return self._query('market_prices',item_id,city,quality)
 def history(self,item_id=None,city=None,quality=None,start=None,end=None):
  self.initialize(); clauses=[]; params=[]
  for col,val in [('item_id',item_id),('city',city),('quality',quality)]:
   if val is not None: clauses.append(f'{col} = ?'); params.append(val)
  if start is not None: clauses.append('recorded_at >= ?'); params.append(start)
  if end is not None: clauses.append('recorded_at <= ?'); params.append(end)
  where=(' WHERE '+' AND '.join(clauses)) if clauses else ''
  with self.connect() as c: return [dict(x) for x in c.execute(f'SELECT * FROM market_price_history{where} ORDER BY recorded_at,id',params)]
 def _query(self,table,item_id,city,quality):
  self.initialize(); clauses=[]; params=[]
  for col,val in [('item_id',item_id),('city',city),('quality',quality)]:
   if val is not None: clauses.append(f'{col} = ?'); params.append(val)
  where=(' WHERE '+' AND '.join(clauses)) if clauses else ''
  with self.connect() as c: return [dict(x) for x in c.execute(f'SELECT * FROM {table}{where} ORDER BY item_id,city,quality',params)]
