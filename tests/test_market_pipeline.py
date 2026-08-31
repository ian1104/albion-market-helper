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
    assert config.SUPPORTED_SERVERS['west']=='west.albion-online-data.com' and config.SUPPORTED_SERVERS['europe']=='europe.albion-online-data.com'
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

from services.analysis_service import AnalysisService


def arec(item='T4_BAG', city='Caerleon', quality=1, sell=100, buy=90, at='2026-08-30T12:00:00Z', server='east'):
    return {'server': server, 'item_id': item, 'city': city, 'quality': quality,
            'sell_price_min': sell, 'sell_price_min_date': at,
            'buy_price_max': buy, 'buy_price_max_date': at, 'recorded_at': at}


def seed_analysis_db(tmp_path):
    db=Database(tmp_path/'analysis.db'); service=MarketService(db)
    rows=[
        arec(city='Caerleon',sell=100,buy=90,at='2026-08-30T10:00:00Z'),
        arec(city='Bridgewatch',sell=80,buy=75,at='2026-08-30T10:00:00Z'),
        arec(city='Caerleon',sell=110,buy=100,at='2026-08-30T11:00:00Z'),
        arec(city='Bridgewatch',sell=90,buy=85,at='2026-08-30T11:00:00Z'),
        arec(city='Caerleon',sell=120,buy=110,at='2026-08-30T12:00:00Z'),
        arec(city='Bridgewatch',sell=100,buy=95,at='2026-08-30T12:00:00Z'),
    ]
    for r in rows: service.save_snapshot(r, r['recorded_at'])
    return db


def test_analysis_statistics_and_change(tmp_path):
    db=seed_analysis_db(tmp_path); a=AnalysisService(db)
    result=a.statistics('T4_BAG','Caerleon',1,'all')
    assert result['data_sufficient']
    assert result['statistics']['sell']['min']==100
    assert result['statistics']['sell']['max']==120
    assert result['statistics']['sell']['average']==110
    assert result['statistics']['sell']['median']==110
    assert result['statistics']['sell']['first']==100
    assert result['statistics']['sell']['latest']==120
    assert result['change']['sell']['absolute']==20
    assert result['change']['sell']['percent']==20


def test_analysis_insufficient_data(tmp_path):
    db=Database(tmp_path/'empty.db'); result=AnalysisService(db).statistics('T4_BAG','Caerleon',1,'24h')
    assert result['data_sufficient'] is False and result['records']==0


def test_analysis_trend_and_moving_average(tmp_path):
    db=seed_analysis_db(tmp_path); result=AnalysisService(db).trend('T4_BAG','Caerleon',1,'all',ma_windows=(3,))
    assert [x['sell_price_min'] for x in result['series']]==[100,110,120]
    assert result['series'][2]['moving_average']['ma3']==110


def test_analysis_spread_and_gross_foundation(tmp_path):
    db=seed_analysis_db(tmp_path); result=AnalysisService(db).spread('T4_BAG',1,'all')
    assert result['data_sufficient']
    assert result['spread']['highest_city']=='Caerleon'
    assert result['spread']['lowest_city']=='Bridgewatch'
    assert result['spread']['absolute']==20
    assert result['arbitrage_foundation']
    assert 'Gross spread only' in result['note']


def test_spread_stability(tmp_path):
    db=seed_analysis_db(tmp_path); result=AnalysisService(db).spread_stability('T4_BAG',1,'all')
    assert result['data_sufficient'] and result['observations']==3
    assert result['minimum_spread']==20 and result['maximum_spread']==20
    assert result['average_spread']==20


def test_null_prices_excluded_from_spread(tmp_path):
    db=Database(tmp_path/'null.db'); s=MarketService(db)
    s.save_snapshot(arec(city='Caerleon',sell=None,buy=None), '2026-08-30T10:00:00Z')
    s.save_snapshot(arec(city='Bridgewatch',sell=100,buy=90), '2026-08-30T10:00:00Z')
    result=AnalysisService(db).spread('T4_BAG',1,'all')
    assert result['data_sufficient'] is False


def test_cross_server_isolation(tmp_path):
    db=Database(tmp_path/'servers.db'); s=MarketService(db)
    s.save_snapshot(arec(server='east',sell=100), '2026-08-30T10:00:00Z')
    west=MarketService(db,server='west'); west.save_snapshot(arec(server='west',sell=200), '2026-08-30T10:00:00Z')
    assert db.history('T4_BAG','Caerleon',1,server='east')[0]['sell_price_min']==100
    assert db.history('T4_BAG','Caerleon',1,server='west')[0]['sell_price_min']==200
    assert len(db.current_prices(server='east'))==1 and len(db.current_prices(server='west'))==1


def test_quality_metrics(tmp_path):
    db=seed_analysis_db(tmp_path)
    s=MarketService(db)
    s.save_snapshot(arec(city='Caerleon',sell=120,buy=110), '2026-08-30T13:00:00Z')
    s.save_snapshot(arec(city='Caerleon',sell=120,buy=110), '2026-08-30T14:00:00Z')
    result=AnalysisService(db).quality('all')
    assert result['total_records']==8
    assert result['unique_items']==1 and result['unique_cities']==2 and result['unique_qualities']==1
    assert result['duplicate_payload_count']==2
    assert result['coverage']['successful_runs']==0


def test_quality_coverage(tmp_path):
    db=Database(tmp_path/'coverage.db'); s=MarketService(db)
    db.start_collection_run('2026-08-30T10:00:00Z')
    db.finish_collection_run(1,finished_at='2026-08-30T10:01:00Z',success=True,records_received=14,records_saved=14,error=None,duration_seconds=60)
    for city in ['Caerleon','Bridgewatch']:
        for item in ['T4_BAG','T5_BAG']:
            s.save_snapshot(arec(item=item,city=city), '2026-08-30T10:00:00Z')
    result=AnalysisService(db).quality('all')
    assert result['coverage']['successful_runs']==1
    assert result['coverage']['expected_records_per_successful_run']==14
    assert result['coverage']['actual_records']==4


def test_migration_preserves_legacy_data(tmp_path):
    p=tmp_path/'legacy.db'
    import sqlite3
    c=sqlite3.connect(p)
    c.executescript('''CREATE TABLE market_prices (id INTEGER PRIMARY KEY AUTOINCREMENT,item_id TEXT NOT NULL,city TEXT NOT NULL,quality INTEGER NOT NULL,sell_price_min INTEGER,sell_price_min_date TEXT,buy_price_max INTEGER,buy_price_max_date TEXT,updated_at TEXT NOT NULL,UNIQUE(item_id,city,quality));CREATE TABLE market_price_history (id INTEGER PRIMARY KEY AUTOINCREMENT,item_id TEXT NOT NULL,city TEXT NOT NULL,quality INTEGER NOT NULL,sell_price_min INTEGER,sell_price_min_date TEXT,buy_price_max INTEGER,buy_price_max_date TEXT,recorded_at TEXT NOT NULL);CREATE INDEX idx_market_price_history_lookup ON market_price_history(item_id,city,quality,recorded_at);CREATE TABLE collection_runs (id INTEGER PRIMARY KEY AUTOINCREMENT,started_at TEXT NOT NULL,finished_at TEXT,success INTEGER NOT NULL DEFAULT 0,records_received INTEGER NOT NULL DEFAULT 0,records_saved INTEGER NOT NULL DEFAULT 0,error TEXT,duration_seconds REAL);''')
    c.execute("INSERT INTO market_prices(item_id,city,quality,sell_price_min,updated_at) VALUES('T4_BAG','Caerleon',1,123,'2026-08-30T10:00:00Z')")
    c.execute("INSERT INTO market_price_history(item_id,city,quality,sell_price_min,recorded_at) VALUES('T4_BAG','Caerleon',1,123,'2026-08-30T10:00:00Z')")
    c.commit(); c.close()
    db=Database(p); db.initialize()
    assert db.current_prices()[0]['sell_price_min']==123
    assert db.history()[0]['sell_price_min']==123
    assert db.current_prices()[0]['server']=='east'


def test_analysis_api_endpoints(tmp_path, monkeypatch):
    import api.main as main
    db=seed_analysis_db(tmp_path); monkeypatch.setattr(main,'database',db)
    c=TestClient(app)
    assert c.get('/api/market/stats',params={'item_id':'T4_BAG','city':'Caerleon','quality':1,'range':'all'}).status_code==200
    assert c.get('/api/market/quality',params={'range':'all'}).status_code==200
    assert c.get('/api/market/analysis',params={'item_id':'T4_BAG','city':'Caerleon','quality':1,'range':'all'}).status_code==200
    assert c.get('/api/market/trend',params={'item_id':'T4_BAG','city':'Caerleon','quality':1,'range':'all'}).status_code==200
    assert c.get('/api/market/spread',params={'item_id':'T4_BAG','quality':1,'range':'all'}).status_code==200
    assert c.get('/api/market/stats',params={'item_id':'T4_BAG','city':'Caerleon','quality':1,'range':'bad'}).status_code==400


def test_invalid_server_rejected(tmp_path):
    with pytest.raises(ValueError):
        AnalysisService(Database(tmp_path/'invalid.db'), server='mars')
