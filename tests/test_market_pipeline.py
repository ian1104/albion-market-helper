import pytest
from fastapi.testclient import TestClient
from api.main import app
from db.database import Database
from services.albion_api import AODPInvalidResponseError,AODPTimeoutError,parse_response
from services.market_service import MarketService

def rec(**kw):
 r={'item_id':'T4_BAG','city':'Caerleon','quality':1,'sell_price_min':10000,'sell_price_min_date':'2026-08-30T02:05:00Z','buy_price_max':9000,'buy_price_max_date':'2026-08-30T02:04:00Z'};r.update(kw);return r

def test_db_insert_update_history(tmp_path):
 db=Database(tmp_path/'m.db');s=MarketService(db)
 s.save_snapshot(rec(),'2026-08-30T12:00:00Z');s.save_snapshot(rec(),'2026-08-30T12:30:00Z');s.save_snapshot(rec(sell_price_min=10500),'2026-08-30T13:00:00Z')
 assert db.current_prices()[0]['sell_price_min']==10500;assert len(db.history())==3

def test_db_null_city_quality(tmp_path):
 db=Database(tmp_path/'m.db');s=MarketService(db);s.save_snapshot(rec(sell_price_min=None,sell_price_min_date=None),'2026-08-30T12:00:00Z');s.save_snapshot(rec(city='Bridgewatch',quality=2),'2026-08-30T12:00:01Z')
 assert db.current_prices(city='Caerleon')[0]['sell_price_min'] is None;assert len(db.current_prices())==2

def test_parser_normalization():
 p=parse_response([{'item_id':'T4_BAG','location':'Caerleon','quality':1,'sell_price_min':100,'sell_price_min_date':'2026-08-30T02:05:00','buy_price_max':None,'buy_price_max_date':None}])[0]
 assert p['city']=='Caerleon' and p['sell_price_min_date']=='2026-08-30T02:05:00Z' and p['buy_price_max'] is None

def test_parser_rejects_invalid():
 with pytest.raises(AODPInvalidResponseError):parse_response([rec(sell_price_min=-1)])
 with pytest.raises(AODPInvalidResponseError):parse_response([rec(sell_price_min_date='bad')])

def test_api(monkeypatch,tmp_path):
 import api.main as main
 db=Database(tmp_path/'a.db');s=MarketService(db);s.save_snapshot(rec(),'2026-08-30T12:00:00Z');monkeypatch.setattr(main,'database',db);monkeypatch.setattr(main,'market_service',s)
 c=TestClient(app);assert c.get('/').status_code==200;assert c.get('/api/market/prices',params={'item_id':'T4_BAG'}).status_code==200;assert c.get('/api/market/history',params={'item_id':'T4_BAG'}).status_code==200;assert c.get('/api/market/history',params={'start':'2026-08-31','end':'2026-08-30'}).status_code==400

def test_fetch_failure(monkeypatch):
 import api.main as main
 monkeypatch.setattr(main.albion_api,'fetch_prices',lambda *a,**k: (_ for _ in ()).throw(AODPTimeoutError('timeout')))
 assert TestClient(app).post('/api/market/fetch',json={'item_id':'T4_BAG','cities':['Caerleon'],'quality':1}).status_code==504
