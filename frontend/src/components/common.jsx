import React from 'react';

export const money = value => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toLocaleString();
export const percent = value => value == null || Number.isNaN(Number(value)) ? '—' : `${Number(value).toFixed(2)}%`;
export const text = (value, fallback = '—') => value == null || value === '' ? fallback : String(value);
export const riskText = value => ({ low: '낮음', medium: '보통', high: '높음', unknown: '미상' })[String(value || '').toLowerCase()] || text(value, '미상');
export const freshnessText = value => ({ fresh: '신선', recent: '최근', stale: '오래됨', insufficient: '데이터 부족' })[String(value || '').toLowerCase()] || text(value, '확인 불가');
export const tone = value => ['high', 'fresh'].includes(String(value || '').toLowerCase()) ? 'good' : ['medium', 'recent'].includes(String(value || '').toLowerCase()) ? 'warn' : 'neutral';

export function Icon({ name }) {
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    market: <><path d="M4 19V9M10 19V5M16 19v-7M3 19h18"/></>,
    strategies: <><circle cx="6" cy="7" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="12" cy="17" r="2"/><path d="m8 8.5 2.5 6.5M16 8.5l-2.5 6.5"/></>,
    portfolio: <><rect x="3" y="6" width="18" height="15" rx="2"/><path d="M8 6V4h8v2M3 11h18M15 15h3"/></>,
    insights: <><path d="M4 18h16M6 15l3-4 3 2 6-7M18 6h-4"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19 15.2a2 2 0 0 0 0-6.4M5 15.2a2 2 0 0 0 0-6.4M9 4.8a2 2 0 0 0 6 0M9 19.2a2 2 0 0 0 6 0"/></>,
    refresh: <><path d="M20 11a8 8 0 0 0-14.8-4L3 10M3 5v5h5M4 13a8 8 0 0 0 14.8 4L21 14M21 19v-5h-5"/></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6"/></>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  };
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

export function Badge({ children, tone: badgeTone = 'neutral' }) { return <span className={`badge ${badgeTone}`}>{children}</span>; }
export function Metric({ label, value, accent = false }) { return <div className="metric"><span>{label}</span><strong className={accent ? 'accent-value' : ''}>{value}</strong></div>; }
export function StatePanel({ title, detail, error = false }) { return <div className={`state-panel ${error ? 'error-state' : ''}`}><strong>{title}</strong>{detail && <span>{detail}</span>}</div>; }
export function DataStatus({ status }) { return <Badge tone={tone(status)}>{text(status, '확인 불가')}</Badge>; }

export function OpportunityCard({ opportunity, onOpen }) {
  const o = opportunity;
  return <button className="opportunity-card" onClick={() => onOpen(o)}>
    <div className="opportunity-card-head"><div><Badge>{text(o.strategy_id)}</Badge><h3>{text(o.title, '기회')}</h3></div><DataStatus status={o.confidence}/></div>
    <div className="route">{text(o.explanation, '실행 가능한 사업 기회')}</div>
    <div className="opportunity-metrics">
      <Metric label="예상 수익" value={o.expected_profit == null ? 'Unknown' : `+${money(o.expected_profit)} S`} accent={o.expected_profit != null}/>
      <Metric label="ROI" value={percent(o.roi_percent)}/>
      <Metric label="필요 자본" value={`${money(o.required_capital)} S`}/>
      <Metric label="시간당 수익" value={`${money(o.profit_per_hour)} S`}/>
    </div>
    <div className="opportunity-footer"><span>위험 {riskText(o.risk)}</span><span>유동성 {text(o.liquidity)}</span><span>데이터 {freshnessText(o.freshness)}</span><Icon name="chevron"/></div>
  </button>;
}

function opportunityItemId(opportunity) {
  if (opportunity?.item_id) return opportunity.item_id;
  const title = String(opportunity?.title || '');
  const candidate = title.split(':', 1)[0].trim();
  return /^T\d+_/.test(candidate) ? candidate : '';
}

export function OpportunityDrawer({ opportunity, onClose, onMarket }) {
  if (!opportunity) return null;
  const o = opportunity;
  const itemId = opportunityItemId(o);
  const rows = [
    ['필요 자본', `${money(o.required_capital)} S`], ['가용 자본', `${money(o.available_capital)} S`],
    ['자본 활용률', percent(o.capital_utilization_percent)], ['필요 수량', text(o.required_quantity)],
    ['실행 가능 수량', text(o.executable_quantity)], ['예상 매출', `${money(o.expected_revenue)} S`],
    ['예상 비용', `${money(o.expected_cost)} S`], ['예상 수익', o.expected_profit == null ? 'Unknown' : `${money(o.expected_profit)} S`],
    ['ROI', percent(o.roi_percent)], ['시간당 수익', `${money(o.profit_per_hour)} S`], ['위험', riskText(o.risk)],
    ['유동성', text(o.liquidity)], ['신뢰도', text(o.confidence)], ['신선도', freshnessText(o.freshness)],
    ['소요 시간', o.time_required == null ? '—' : `${Number(o.time_required).toFixed(1)} h`],
  ];
  return <div className="drawer-backdrop" onClick={onClose}><aside className="drawer" onClick={e => e.stopPropagation()}>
    <button className="icon-button close" onClick={onClose} aria-label="닫기"><Icon name="close"/></button>
    <Badge>{text(o.strategy_id)}</Badge><h2>{text(o.title)}</h2><p className="drawer-explanation">{text(o.explanation, '상세 설명이 없습니다.')}</p>
    <div className="detail-grid">{rows.map(([label, value]) => <Metric key={label} label={label} value={value}/>)}</div>
    {itemId && onMarket && <button className="primary-button drawer-market-button" onClick={() => onMarket(itemId)}>이 아이템 시장 상세 보기</button>}
    <div className="analysis-note"><strong>판단 근거</strong><p>{text(o.explanation, '데이터가 부족하여 추가 판단을 제공할 수 없습니다.')}</p></div>
  </aside></div>;
}
