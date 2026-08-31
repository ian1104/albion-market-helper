from __future__ import annotations
from datetime import datetime,timezone
from typing import Any
import httpx
from config import AODP_HOST,AODP_TIMEOUT_SECONDS

class AODPError(Exception): pass
class AODPTimeoutError(AODPError): pass
class AODPDNSError(AODPError): pass
class AODPConnectionError(AODPError): pass
class AODPHTTPError(AODPError):
 def __init__(self,status_code,message): super().__init__(message); self.status_code=status_code
class AODPInvalidResponseError(AODPError): pass

def normalize_timestamp(value:Any)->str|None:
 if value is None:return None
 if not isinstance(value,str) or not value.strip(): raise AODPInvalidResponseError('invalid timestamp')
 s=value.strip(); s=s[:-1]+'+00:00' if s.endswith('Z') else s
 try: dt=datetime.fromisoformat(s)
 except ValueError as e: raise AODPInvalidResponseError(f'invalid timestamp: {value!r}') from e
 if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
 else: dt=dt.astimezone(timezone.utc)
 return dt.isoformat(timespec='seconds').replace('+00:00','Z')

def _price(v,field):
 if v is None:return None
 if isinstance(v,bool) or not isinstance(v,(int,float)) or int(v)!=v: raise AODPInvalidResponseError(f'{field} must be an integer price or null')
 if v<0: raise AODPInvalidResponseError(f'{field} cannot be negative')
 return int(v)

def parse_response(payload:Any):
 if not isinstance(payload,list): raise AODPInvalidResponseError('AODP response must be a JSON array')
 out=[]
 for i,r in enumerate(payload):
  if not isinstance(r,dict): raise AODPInvalidResponseError(f'record {i} is not an object')
  item=r.get('item_id'); city=r.get('city',r.get('location')); quality=r.get('quality')
  if not isinstance(item,str) or not item.strip(): raise AODPInvalidResponseError(f'record {i}: invalid item_id')
  if not isinstance(city,str) or not city.strip(): raise AODPInvalidResponseError(f'record {i}: invalid city/location')
  if isinstance(quality,bool) or not isinstance(quality,int) or quality<1: raise AODPInvalidResponseError(f'record {i}: invalid quality')
  sell=_price(r.get('sell_price_min'),'sell_price_min'); buy=_price(r.get('buy_price_max'),'buy_price_max')
  sd=normalize_timestamp(r.get('sell_price_min_date')); bd=normalize_timestamp(r.get('buy_price_max_date'))
  if sell is not None and sd is None: raise AODPInvalidResponseError(f'record {i}: sell price has no timestamp')
  if buy is not None and bd is None: raise AODPInvalidResponseError(f'record {i}: buy price has no timestamp')
  out.append({'item_id':item.strip(),'city':city.strip(),'quality':quality,'sell_price_min':sell,'sell_price_min_date':sd,'buy_price_max':buy,'buy_price_max_date':bd})
 return out

class AlbionApiService:
 def __init__(self,host=AODP_HOST,timeout=AODP_TIMEOUT_SECONDS): self.host=host; self.timeout=timeout
 def fetch_prices(self,item_ids,locations=None,qualities=None):
  if isinstance(item_ids,str):item_ids=[item_ids]
  if not item_ids or any(not isinstance(x,str) or not x.strip() for x in item_ids): raise ValueError('item_ids must contain at least one non-empty item id')
  path='/api/v2/stats/prices/'+','.join(x.strip() for x in item_ids)+'.json'; params={}
  if locations:params['locations']=','.join(locations)
  if qualities:params['qualities']=','.join(map(str,qualities))
  try:r=httpx.get(f'https://{self.host}{path}',params=params,timeout=self.timeout)
  except httpx.TimeoutException as e:raise AODPTimeoutError('AODP request timed out') from e
  except httpx.ConnectError as e:
   msg=str(e).lower()
   if 'name or service not known' in msg or 'nodename' in msg or 'getaddrinfo' in msg:raise AODPDNSError('AODP DNS resolution failed') from e
   raise AODPConnectionError('AODP connection failed') from e
  except httpx.RequestError as e:raise AODPConnectionError('AODP request failed') from e
  if not 200<=r.status_code<300:raise AODPHTTPError(r.status_code,f'AODP returned HTTP {r.status_code}')
  try:p=r.json()
  except ValueError as e:raise AODPInvalidResponseError('AODP returned invalid JSON') from e
  return parse_response(p)
