import threading
import time
import pytest
from fastapi.testclient import TestClient
from api.main import app
from db.database import Database
from services.albion_api import (
    AODPConnectionError, AODPHTTPError, AODPInvalidResponseError, AODPTimeoutError,
    AlbionApiService, parse_response, split_item_batches,
)
from services.collector import Collector
from services.market_service import MarketService
from services.scheduler import CollectorScheduler


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


def test_config_defaults_and_batch_budget():
    import config
    assert config.ALBION_SERVER=='east' and config.AODP_HOST=='east.albion-online-data.com'
    batches=split_item_batches(['T4_BAG','T5_BAG','T6_BAG'],['Caerleon'],[1],max_url_length=110)
    assert len(batches)>1 and sum(map(len,batches))==3


def test_parser_null_and_location():
    row=parse_response([{'item_id':'T4_BAG','location':'Caerleon','quality':1,'sell_price_min':None,'sell_price_min_date':None,'buy_price_max':None,'buy_price_max_date':None}])[0]
    assert row['city']=='Caerleon' and row['sell_price_min'] is None


def test_client_timeout_retry():
    import httpx
    class Client:
        calls=0
        @classmethod
        def get(cls,*a,**k):
            cls.calls+=1
            raise httpx.ReadTimeout('timeout')
    with pytest.raises(AODPTimeoutError): AlbionApiService(client=Client,retry_count=2,retry_backoff=0,sleeper=lambda _:None).fetch_prices(['T4_BAG'])
    assert Client.calls==3


def test_client_connection_error():
    import httpx
    class Client:
        @classmethod
        def get(cls,*a,**k): raise httpx.ConnectError('connection refused')
    with pytest.raises(AODPConnectionError): AlbionApiService(client=Client,retry_count=0).fetch_prices(['T4_BAG'])


def test_api_retry_5xx_and_limit():
    class Response:
        status_code=500
        def json(self): return []
    class Client:
        calls=0
        @classmethod
        def get(cls,*a,**k): cls.calls+=1; return Response()
    with pytest.raises(AODPHTTPError): AlbionApiService(client=Client,retry_count=2,retry_backoff=0,sleeper=lambda _:None).fetch_prices(['T4_BAG'])
    assert Client.calls==3


def test_collector_failure_record(tmp_path):
    db=Database(tmp_path/'c.db'); service=MarketService(db)
    class Fake:
        host='east.albion-online-data.com'
        def fetch_prices(self,*a): raise AODPConnectionError('down')
    collector=Collector(Fake(),service,watchlist=['T4_BAG'],cities=['Caerleon'],qualities=[1],request_delay=0)
    with pytest.raises(AODPConnectionError): collector.run()
    assert db.latest_collection_run()['success']==0 and db.latest_collection_run()['error']=='down'


def test_collector_success_and_run_record(tmp_path):
    db=Database(tmp_path/'c.db'); service=MarketService(db)
    class Fake:
        host='east.albion-online-data.com'
        def fetch_prices(self, items, locations, qualities): return [rec(city=locations[0])]
    collector=Collector(Fake(),service,watchlist=['T4_BAG'],cities=['Caerleon'],qualities=[1],request_delay=0)
    result=collector.run(); assert result['success'] and result['records_saved']==1
    assert db.latest_collection_run()['success']==1


def test_collector_concurrent_prevention(tmp_path):
    db=Database(tmp_path/'c.db'); service=MarketService(db)
    entered=threading.Event(); release=threading.Event()
    class Fake:
        host='east.albion-online-data.com'
        def fetch_prices(self,*a): entered.set(); release.wait(1); return [rec()]
    collector=Collector(Fake(),service,watchlist=['T4_BAG'],cities=['Caerleon'],qualities=[1],request_delay=0)
    t=threading.Thread(target=collector.run);t.start();assert entered.wait(1); assert collector.run()['skipped'];release.set();t.join()


def test_scheduler_start_stop(tmp_path):
    calls=[]
    class C:
        def run(self): calls.append(1)
    scheduler=CollectorScheduler(C(),interval_seconds=60);assert scheduler.start(initial_collection=True);assert scheduler.running;scheduler.stop();assert not scheduler.running;assert calls==[1]
