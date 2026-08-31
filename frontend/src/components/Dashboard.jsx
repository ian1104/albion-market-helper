import React, { useMemo } from 'react';
import { RANKS } from '../constants';
import { Badge, DataStatus, Metric, OpportunityCard, StatePanel, Icon, money, percent, text, freshnessText } from './common';

export function DashboardFilters({ state }) {
  const { server, setServer, names, capital, setCapital, risk, setRisk, strategy, setStrategy, sort, setSort, strategies } = state;
  return <section className="filter-bar">
    <label><span>서버</span><select value={server} onChange={e => setServer(e.target.value)}>{Object.entries(names).length ? Object.entries(names).map(([id, name]) => <option key={id} value={id}>{name}</option>) : ['east', 'west', 'europe'].map(id => <option key={id} value={id}>{id}</option>)}</select></label>
    <label><span>가용 자본</span><div className="input-with-unit"><input type="number" min="0" value={capital} onChange={e => setCapital(e.target.value)} placeholder="입력"/><em>S</em></div></label>
    <label><span>위험</span><select value={risk} onChange={e => setRisk(e.target.value)}><option value="">전체</option><option value="low">낮음</option><option value="medium">보통</option><option value="high">높음</option><option value="unknown">미상</option></select></label>
    <label><span>전략</span><select value={strategy} onChange={e => setStrategy(e.target.value)}><option value="">전체 전략</option>{strategies.map(x => <option key={x.strategy_id} value={x.strategy_id}>{x.name || x.strategy_id}</option>)}</select></label>
    <label><span>정렬</span><select value={sort} onChange={e => setSort(e.target.value)}>{RANKS.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
  </section>;
}

export default function Dashboard({ state, setPage, open }) {
  const { server, names, capital, strategies, opportunities, loading, error, sort } = state;
  const bestProfit = useMemo(() => opportunities.reduce((best, o) => o.expected_profit == null ? best : best == null || o.expected_profit > best ? o.expected_profit : best, null), [opportunities]);
  const bestRoi = useMemo(() => opportunities.reduce((best, o) => o.roi_percent == null ? best : best == null || o.roi_percent > best ? o.roi_percent : best, null), [opportunities]);
  return <div className="page">
    <div className="hero"><div><p className="eyebrow">ECONOMIC COMMAND CENTER</p><h1>오늘의 경제 기회</h1><p>현재 시장과 자본 조건을 기준으로 실행 가능한 사업 기회를 비교합니다.</p></div><Badge tone={opportunities.length ? 'good' : 'neutral'}>{loading ? '데이터 확인 중' : opportunities.length ? '실행 기회 있음' : '기회 없음'}</Badge></div>
    <DashboardFilters state={state}/>
    <div className="summary-strip"><Metric label="가용 자본" value={capital ? `${money(capital)} S` : '미설정'}/><Metric label="등록 전략" value={strategies.length}/><Metric label="발견된 기회" value={opportunities.length}/><Metric label="최고 예상 수익" value={bestProfit == null ? 'Unknown' : `+${money(bestProfit)} S`} accent={bestProfit != null}/><Metric label="최고 ROI" value={percent(bestRoi)} accent={bestRoi != null}/><Metric label="데이터 상태" value={opportunities.length ? freshnessText(opportunities[0].freshness) : '데이터 없음'}/></div>
    {error && <StatePanel error title="데이터를 불러오지 못했습니다." detail={error}/>} 
    <section className="section-block"><div className="section-title"><div><p className="eyebrow">RANKED BY {RANKS.find(x => x[0] === sort)?.[1]?.toUpperCase()}</p><h2>오늘의 추천</h2></div><button className="text-button" onClick={() => setPage('strategies')}>전략 탐색 <Icon name="arrow"/></button></div>
      {!loading && !opportunities.length ? <StatePanel title="현재 추천할 기회가 없습니다." detail="시장 데이터, 유동성 또는 레시피 데이터가 충분하지 않을 수 있습니다. 이는 수익이 0이라는 의미가 아닙니다."/> : <div className="opportunity-grid">{opportunities.slice(0, 6).map((o, i) => <OpportunityCard key={`${o.strategy_id}-${o.title}-${i}`} opportunity={o} onOpen={open}/>)}</div>}
    </section>
    <section className="split-section"><div className="panel"><div className="section-title"><div><p className="eyebrow">REGISTRY</p><h2>사업 전략</h2></div><button className="text-button" onClick={() => setPage('strategies')}>전체 보기 <Icon name="arrow"/></button></div><div className="strategy-list">{strategies.map(x => <button className="strategy-row" key={x.strategy_id} onClick={() => setPage('strategies')}><div className="strategy-symbol">{String(x.name || x.strategy_id).slice(0, 1)}</div><div><strong>{text(x.name, x.strategy_id)}</strong><span>{text(x.description, '전략 설명 없음')}</span></div><Badge tone={x.calculator_key ? 'good' : 'neutral'}>{x.calculator_key ? '사용 가능' : '데이터 준비 중'}</Badge><Icon name="chevron"/></button>)}</div></div>
      <div className="panel market-condition"><div className="section-title"><div><p className="eyebrow">MARKET STATUS</p><h2>시장 상태</h2></div></div><div className="condition-grid"><Metric label="서버" value={names[server] || server}/><Metric label="기회 데이터" value={opportunities.length ? '사용 가능' : '제한적'}/><Metric label="데이터 품질" value={opportunities.length ? freshnessText(opportunities[0].freshness) : '데이터 없음'}/><Metric label="유동성" value={opportunities.length ? text(opportunities[0].liquidity) : '확인 불가'}/></div><div className="market-note">가격·유동성 데이터가 부족한 경우 수익성 판단을 확정하지 않습니다.</div></div>
    </section>
  </div>;
}
