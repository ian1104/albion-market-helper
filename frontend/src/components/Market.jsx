import React from 'react';
import { Badge, Metric, StatePanel, money, percent, text } from './common';

export function LineChart({ rows }) {
  const points = (rows || []).filter(x => x.sell_price_min != null).slice(-60);
  if (!points.length) return <div className="chart-empty">가격 이력 데이터를 사용할 수 없습니다.</div>;
  const values = points.map(x => Number(x.sell_price_min));
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const line = values.map((v, i) => `${i / Math.max(values.length - 1, 1) * 100},${92 - (v - min) / range * 76}`).join(' ');
  return <div className="chart-wrap"><svg viewBox="0 0 100 100" preserveAspectRatio="none" className="line-chart" aria-label="AODP 관측 가격 추세"><polyline points={line} fill="none" stroke="currentColor" vectorEffect="non-scaling-stroke" strokeWidth="1.5"/></svg></div>;
}

export default function Market({ market, setMarket, server, load }) {
  const hasQuery = market.itemId && market.city;
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">MARKET INTELLIGENCE</p><h1>시장 분석</h1><p>아이템별 현재 가격, 추세와 도시 간 가격 차이를 확인합니다.</p></div></div>
    <section className="market-search panel"><label><span>아이템 ID</span><input value={market.itemId} onChange={e => setMarket({ ...market, itemId: e.target.value })} placeholder="아이템 ID"/></label><label><span>도시</span><input value={market.city} onChange={e => setMarket({ ...market, city: e.target.value })} placeholder="도시"/></label><label><span>품질</span><input type="number" min="1" value={market.quality} onChange={e => setMarket({ ...market, quality: e.target.value })}/></label><button className="primary-button" onClick={load}>분석</button></section>
    {market.error && <StatePanel error title="시장 데이터를 불러오지 못했습니다." detail={market.error}/>} 
    {!hasQuery ? <StatePanel title="아이템과 도시를 입력하세요." detail="현재 backend가 제공하는 데이터만 표시합니다."/> : <>
      <div className="summary-strip market-summary"><Metric label="최저 판매가" value={money(market.current?.sell_price_min)}/><Metric label="최고 구매가" value={money(market.current?.buy_price_max)}/><Metric label="최근 가격" value={money(market.analysis?.statistics?.sell?.latest)}/><Metric label="평균 가격" value={money(market.analysis?.statistics?.sell?.average)}/><Metric label="가격 변화" value={market.analysis?.change?.sell?.percent == null ? '—' : percent(market.analysis.change.sell.percent)}/></div>
      <section className="panel chart-panel"><div className="section-title"><div><p className="eyebrow">OBSERVED PRICE</p><h2>가격 추세</h2></div><Badge>AODP 관측 가격</Badge></div><div className="chart-tabs"><span className="active">라인</span><span className="disabled">캔들 · OHLC 데이터 없음</span></div><LineChart rows={market.analysis?.trend?.series || market.history}/><p className="chart-disclaimer">AODP 관측 가격을 시각화한 추세입니다. 체결 기반 거래소 캔들로 해석하지 않습니다.</p></section>
      {market.spread?.data_sufficient && <section className="panel"><div className="section-title"><div><p className="eyebrow">CITY SPREAD</p><h2>도시 간 가격 차이</h2></div></div><div className="summary-strip"><Metric label="최저 도시" value={text(market.spread.spread.lowest_city)}/><Metric label="최고 도시" value={text(market.spread.spread.highest_city)}/><Metric label="절대 스프레드" value={money(market.spread.spread.absolute)}/><Metric label="스프레드" value={percent(market.spread.spread.percent)}/></div></section>}
    </>}
  </div>;
}
