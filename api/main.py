from __future__ import annotations
from datetime import datetime,timezone
from typing import Any
from fastapi import FastAPI,HTTPException,Query
from pydantic import BaseModel,Field
from db.database import Database
from services.market_service import MarketService
from services.albion_api import *
app=FastAPI(title='Albion Market Helper');database=Database();market_service=MarketService(database);albion_api=AlbionApiService()
class FetchRequest(BaseModel): item_id:str=Field(min_length=1); cities:list[str]=Field(min_length=1); quality:int=Field(ge=1)
def _error(e):
 if isinstance(e,AODPTimeoutError):return HTTPException(504,'AODP request timed out')
 if isinstance(e,AODPDNSError):return HTTPException(503,'AODP DNS resolution failed')
 if isinstance(e,AODPConnectionError):return HTTPException(503,'AODP connection failed')
 if isinstance(e,AODPHTTPError):return HTTPException(502,f'AODP HTTP error: {e.status_code}')
 if isinstance(e,AODPInvalidResponseError):return HTTPException(502,'AODP returned an invalid response')
 return HTTPException(500,'Market pipeline error')
@app.get('/')
def root()->dict[str,str]:return {'status':'ok','service':'Albion Market Helper'}
@app.get('/api/market/prices')
def prices(item_id:str|None=None,city:str|None=None,quality:int|None=Query(None,ge=1))->list[dict[str,Any]]:return database.current_prices(item_id,city,quality)
@app.get('/api/market/history')
def history(item_id:str|None=None,city:str|None=None,quality:int|None=Query(None,ge=1),start:str|None=None,end:str|None=None)->list[dict[str,Any]]:
 if start and end:
  try:s=datetime.fromisoformat(start.replace('Z','+00:00'));e=datetime.fromisoformat(end.replace('Z','+00:00'))
  except ValueError as ex:raise HTTPException(400,'start and end must be valid ISO-8601 timestamps') from ex
  if s.tzinfo is None:s=s.replace(tzinfo=timezone.utc)
  if e.tzinfo is None:e=e.replace(tzinfo=timezone.utc)
  if s>e:raise HTTPException(400,'start must not be later than end')
 return database.history(item_id,city,quality,start,end)
@app.post('/api/market/fetch')
def fetch(request:FetchRequest)->dict[str,Any]:
 try:
  records=albion_api.fetch_prices([request.item_id],request.cities,[request.quality]);count=market_service.save_snapshot_batch(records);return {'saved':count,'records':records}
 except Exception as e:raise _error(e)
