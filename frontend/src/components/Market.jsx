import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import { Badge, Metric, StatePanel, money, percent, text, freshnessText, tone } from './common';

function ItemIcon({ item, size = 'md' }) {
  const [failed, setFailed] = useState(false);
  if (!item?.icon || failed) return <div className={`item-icon-fallback ${size}`} aria-label="아이콘 없음">?</div>;
  return <img className={`item-icon ${size}`} src={item.icon} alt="" loading="lazy" onError={() => setFailed(true)} />;
}

function parseMarketTimestamp(value) {
  if (value == null || value === '') return null;
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? null : timestamp;
}

function formatFreshnessAge(ageMinutes) {
  if (ageMinutes == null || !Number.isFinite(ageMinutes)) return '확인 불가';
  if (ageMinutes < 1) return '방금 전';
  if (ageMinutes < 60) return `${Math.floor(ageMinutes)}분 전`;
  if (ageMinutes < 1440) return `${Math.floor(ageMinutes / 60)}시간 전`;
  return `${Math.floor(ageMinutes / 1440)}일 전`;
}

export function getMarketFreshness(row, now = new Date()) {
  const candidates = [];

  const sellPrice = Number(row?.sell_price_min);
  const sellTimestamp = parseMarketTimestamp(row?.sell_price_min_date);

  if (sellPrice > 0 && sellTimestamp) {
    candidates.push(sellTimestamp);
  }

  const buyPrice = Number(row?.buy_price_max);
  const buyTimestamp = parseMarketTimestamp(row?.buy_price_max_date);

  if (buyPrice > 0 && buyTimestamp) {
    candidates.push(buyTimestamp);
  }

  if (!candidates.length) {
    return {
      status: 'unknown',
      ageMinutes: null,
      timestamp: null,
      label: '확인 불가',
    };
  }

  const timestamp = new Date(
    Math.min(...candidates.map(value => value.getTime()))
  );

  const ageMinutes = Math.max(
    0,
    (now.getTime() - timestamp.getTime()) / 60000
  );

  const status = ageMinutes < 15
    ? 'fresh'
    : ageMinutes < 30
      ? 'recent'
      : 'stale';

  return {
    status,
    ageMinutes,
    timestamp,
    label: formatFreshnessAge(ageMinutes),
  };
}

export function LineChart({ rows }) {
  const points = (rows || []).filter(x => x.avg_price != null || x.sell_price_min != null).slice(-120);
  if (!points.length) return <div className="chart-empty">충분한 가격 기록이 없습니다.</div>;
  const values = points.map(x => Number(x.avg_price ?? x.sell_price_min)).filter(Number.isFinite);
  if (!values.length) return <div className="chart-empty">차트에 사용할 가격 데이터가 없습니다.</div>;
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const line = values.map((v, i) => `${i / Math.max(values.length - 1, 1) * 100},${92 - (v - min) / range * 76}`).join(' ');
  return <div className="chart-wrap"><svg viewBox="0 0 100 100" preserveAspectRatio="none" className="line-chart" aria-label="AODP 관측 가격 추세"><polyline points={line} fill="none" stroke="currentColor" vectorEffect="non-scaling-stroke" strokeWidth="1.5"/></svg></div>;
}

function ItemSearch({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function search(event) {
    event?.preventDefault();
    setLoading(true); setError('');
    try {
      const data = await api.items({ query, limit: 20 });
      setResults(data.items || []);
      if (data.error && !data.items?.length) setError('아이템 메타데이터를 불러오지 못했습니다.');
    } catch (e) {
      setResults([]); setError(e.message || '검색에 실패했습니다.');
    } finally { setLoading(false); }
  }

  return <div className="item-search panel">
    <form onSubmit={search} className="item-search-form">
      <label><span>아이템 검색</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="아이템 이름 또는 Item ID" /></label>
      <button className="primary-button" disabled={loading}>{loading ? '검색 중…' : '검색'}</button>
    </form>
    {error && <StatePanel error title="검색할 수 없습니다." detail={error} />}
    {!loading && !error && query && !results.length && <StatePanel title="검색 결과가 없습니다." detail="실제 item metadata에 존재하는 이름 또는 Item ID를 입력하세요." />}
    {!!results.length && <div className="item-search-results">{results.map(item => <button key={item.item_id} className="item-result" onClick={() => onSelect(item)}>
      <ItemIcon item={item}/><span><strong>{text(item.item_name, item.item_id)}</strong><small>{item.item_id} · T{item.tier ?? '?'}{item.enchantment ? `.${item.enchantment}` : ''} · {text(item.category, '분류 없음')}</small></span>
    </button>)}</div>}
  </div>;
}

function CityTable({ cities, onSelect, selectedCity }) {
  if (!cities?.length) return <StatePanel title="도시별 시장 데이터가 없습니다." detail="현재 backend가 보유한 관측 데이터가 없습니다." />;
  return <div className="market-table-wrap"><table className="market-table"><thead><tr><th>도시</th><th>최저 판매가</th><th>최고 구매가</th><th>데이터 상태</th></tr></thead><tbody>{cities.map(row => {
  const freshness = getMarketFreshness(row);
  return <tr key={`${row.city}-${row.quality}`} className={row.city === selectedCity ? 'selected' : ''} onClick={() => onSelect(row.city)}><td>{row.city}</td><td>{money(row.sell_price_min)}</td><td>{money(row.buy_price_max)}</td><td><Badge tone={tone(freshness.status)}>{freshnessText(freshness.status)}</Badge><span className="muted">{` · ${freshness.label}`}</span></td></tr>;})}</tbody></table></div>;
}

export default function Market({ server, initialItemId = '' }) {
  const [selected, setSelected] = useState(null);
  const [quality, setQuality] = useState(1);
  const [city, setCity] = useState('');
  const [detail, setDetail] = useState({ metadata: null, cities: [], history: [], opportunities: [], analysis: null, error: '', loading: false });
  const [range, setRange] = useState('7d');

  async function loadCityAnalysis(itemId, nextCity, nextQuality = quality, cities = detail.cities, metadata = detail.metadata, opportunities = detail.opportunities, nextRange = range) {
    if (!nextCity) return;
    setDetail(d => ({ ...d, loading: true, error: '' }));
    try {
      const [marketResponse, historyResponse] = await Promise.all([
        api.market({ itemId, city: nextCity, quality: nextQuality, server }),
        api.itemHistory({ itemId, server, quality: nextQuality, city: nextCity, range: nextRange }),
      ]);
      setCity(nextCity);
      setDetail({ metadata, cities, history: historyResponse.history || marketResponse.history || [], opportunities, analysis: marketResponse.analysis || null, error: '', loading: false });
    } catch (e) {
      setDetail(d => ({ ...d, loading: false, error: e.message || '선택한 도시의 데이터를 불러오지 못했습니다.' }));
    }
  }

  async function selectItem(item) {
    setSelected(item); setCity(''); setDetail(d => ({ ...d, loading: true, error: '' }));
    try {
      const [metadataResponse, marketResponse, opportunityResponse] = await Promise.all([
        api.item(item.item_id), api.itemMarket({ itemId: item.item_id, server, quality }), api.itemOpportunities({ itemId: item.item_id, server }),
      ]);
      const cities = marketResponse.cities || [];
      const firstCity = cities[0]?.city || '';
      const metadata = metadataResponse.item;
      const opportunities = opportunityResponse.opportunities || [];
      const historyResponse = firstCity ? await api.itemHistory({ itemId: item.item_id, server, quality, city: firstCity, range }) : { history: [] };
      setCity(firstCity);
      setDetail({ metadata, cities, history: historyResponse.history || [], opportunities, analysis: null, error: '', loading: false });
      if (firstCity) await loadCityAnalysis(item.item_id, firstCity, quality, cities, metadata, opportunities, range);
    } catch (e) {
      setDetail({ metadata: item, cities: [], history: [], opportunities: [], analysis: null, error: e.message || '시장 데이터를 불러오지 못했습니다.', loading: false });
    }
  }

  useEffect(() => {
    if (!initialItemId) return;
    let active = true;
    api.item(initialItemId).then(response => { if (active) selectItem(response.item); }).catch(() => {});
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialItemId, server]);

  useEffect(() => {
    if (!selected || !city) return;
    loadCityAnalysis(selected.item_id, city, quality, detail.cities, detail.metadata, detail.opportunities, range);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quality, range]);

  const current = detail.cities.find(x => x.city === city);
  const statistics = detail.analysis?.statistics;
  const chartRows = useMemo(() => detail.history || [], [detail.history]);

  return <div className="page"><div className="page-heading"><div><p className="eyebrow">MARKET INTELLIGENCE</p><h1>시장 분석</h1><p>실제 Albion 아이템 메타데이터와 보유 시장 관측 데이터를 연결합니다.</p></div></div>
    <ItemSearch onSelect={selectItem}/>
    {detail.error && <StatePanel error title="시장 데이터를 불러오지 못했습니다." detail={detail.error} />}
    {!selected ? <StatePanel title="아이템을 선택하세요." detail="검색 결과에서 아이템을 선택하면 실제 시장 데이터와 가격 기록을 조회합니다." /> : <>
      <section className="panel item-header-panel"><div className="item-identity"><ItemIcon item={detail.metadata || selected} size="lg"/><div><p className="eyebrow">ITEM</p><h2>{text(detail.metadata?.item_name, selected.item_id)}</h2><span>{selected.item_id} · Tier {detail.metadata?.tier ?? 'Unknown'}{detail.metadata?.enchantment ? `.${detail.metadata.enchantment}` : ''} · {text(detail.metadata?.category, '분류 없음')}</span></div></div><div className="item-header-controls"><label><span>품질</span><select value={quality} onChange={e => setQuality(Number(e.target.value))}>{[1,2,3,4,5].map(x => <option key={x} value={x}>{x}</option>)}</select></label><Badge>{detail.loading ? '데이터 확인 중' : detail.cities.length ? `${detail.cities.length}개 도시 관측` : '데이터 없음'}</Badge></div></section>
      <div className="summary-strip market-summary"><Metric label="최저 판매가" value={money(current?.sell_price_min)}/><Metric label="최고 구매가" value={money(current?.buy_price_max)}/><Metric label="최근 가격" value={money(statistics?.sell?.latest)}/><Metric label="평균 가격" value={money(statistics?.sell?.average)}/><Metric label="가격 변화" value={statistics?.change?.sell?.percent == null ? '—' : percent(statistics.change.sell.percent)}/></div>
      <section className="panel chart-panel"><div className="section-title"><div><p className="eyebrow">OBSERVED PRICE · {city || '—'}</p><h2>가격 추세</h2></div><div className="chart-controls">{['1d','7d','30d','90d'].map(x => <button key={x} className={range === x ? 'active' : ''} onClick={() => setRange(x)}>{x.toUpperCase()}</button>)}</div></div><div className="chart-tabs"><span className="active">라인</span><span className="disabled">캔들 · OHLC 데이터 없음</span></div><LineChart rows={chartRows}/><p className="chart-disclaimer">AODP 관측 가격 기반입니다. 체결 기반 거래소 캔들로 해석하지 않습니다.</p></section>
      <section className="panel"><div className="section-title"><div><p className="eyebrow">CITY COMPARISON</p><h2>도시별 가격</h2></div><span className="muted">행을 선택하면 해당 도시의 추세를 봅니다.</span></div><CityTable cities={detail.cities} selectedCity={city} onSelect={nextCity => loadCityAnalysis(selected.item_id, nextCity, quality, detail.cities, detail.metadata, detail.opportunities, range)}/></section>
      <section className="panel"><div className="section-title"><div><p className="eyebrow">BUSINESS OPPORTUNITIES</p><h2>이 아이템의 사업 기회</h2></div></div>{!detail.opportunities.length ? <StatePanel title="현재 발견된 사업 기회가 없습니다." detail="사업 기회가 0이라는 뜻이 아니라 현재 backend 조건에서 반환된 opportunity가 없다는 뜻입니다." /> : <div className="opportunity-list">{detail.opportunities.map((o, i) => <div className="opportunity-row" key={`${o.strategy_id}-${o.title}-${i}`}><div><Badge>{text(o.strategy_id)}</Badge><strong>{text(o.title, selected.item_id)}</strong><span>{text(o.explanation, '설명이 없습니다.')}</span></div><Metric label="예상 수익" value={o.expected_profit == null ? 'Unknown' : `${money(o.expected_profit)} S`} accent={o.expected_profit != null}/><Metric label="ROI" value={percent(o.roi_percent)}/></div>)}</div>}</section>
    </>}
  </div>;
}
