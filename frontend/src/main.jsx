import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const SERVER_IDS = ['east', 'west', 'europe'];

function Value({ label, value }) { return <div className="metric"><span>{label}</span><strong>{value ?? 'Unavailable'}</strong></div>; }
function formatSilver(value) { return value == null || Number.isNaN(Number(value)) ? 'Unavailable' : Number(value).toLocaleString(); }
function formatPercent(value) { return value == null || Number.isNaN(Number(value)) ? 'Unavailable' : `${Number(value).toFixed(2)}%`; }
function dataStatus(opportunities) {
  if (!opportunities.length) return 'Insufficient / No Data';
  const freshness = opportunities.map((o) => String(o.freshness || '').toLowerCase());
  if (freshness.every((x) => x === 'fresh')) return 'Fresh';
  if (freshness.some((x) => x === 'stale')) return 'Stale';
  if (freshness.some((x) => x === 'recent')) return 'Recent';
  return 'Limited';
}

function Dashboard({ server, setServer, serverNames, capital, setCapital, risk, setRisk, strategy, setStrategy, sort, setSort, opportunities, strategies, loading, onRefresh }) {
  const bestProfit = useMemo(() => opportunities.reduce((best, item) => item.expected_profit == null ? best : (best == null || item.expected_profit > best ? item.expected_profit : best), null), [opportunities]);
  const bestRoi = useMemo(() => opportunities.reduce((best, item) => item.roi_percent == null ? best : (best == null || item.roi_percent > best ? item.roi_percent : best), null), [opportunities]);
  return <section className="dashboard">
    <div className="dashboard-header"><div><p className="eyebrow">ALBION MARKET HELPER</p><h1>Business Dashboard</h1><p className="subtitle">Compare currently executable economic opportunities returned by the StrategyEngine.</p></div><button className="refresh" onClick={onRefresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button></div>
    <section className="filters card">
      <label>Server<select value={server} onChange={(e) => setServer(e.target.value)}>{SERVER_IDS.map((id) => <option key={id} value={id}>{serverNames[id] || id}</option>)}</select></label>
      <label>Available Capital<input type="number" min="1" value={capital} onChange={(e) => setCapital(e.target.value)} placeholder="Enter capital" /></label>
      <label>Risk<select value={risk} onChange={(e) => setRisk(e.target.value)}><option value="">Any</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="unknown">Unknown</option></select></label>
      <label>Strategy<select value={strategy} onChange={(e) => setStrategy(e.target.value)}><option value="">All registered</option>{strategies.map((s) => <option key={s.strategy_id} value={s.strategy_id}>{s.name}{s.calculator_key ? '' : ' — metadata only'}</option>)}</select></label>
      <label>Ranking<select value={sort} onChange={(e) => setSort(e.target.value)}><option value="profit">Expected Profit</option><option value="roi">ROI</option><option value="capital_efficiency">Capital Efficiency</option><option value="capital">Required Capital</option><option value="risk">Risk</option><option value="confidence">Confidence</option><option value="freshness">Freshness</option></select></label>
    </section>
    <section className="summary-grid">
      <div className="summary-card"><span>Available Capital</span><strong>{capital ? formatSilver(capital) : 'Not set'}</strong></div><div className="summary-card"><span>Strategies Registered</span><strong>{strategies.length}</strong></div><div className="summary-card"><span>Opportunities Found</span><strong>{opportunities.length}</strong></div><div className="summary-card"><span>Best Estimated Profit</span><strong>{formatSilver(bestProfit)}</strong></div><div className="summary-card"><span>Best ROI</span><strong>{formatPercent(bestRoi)}</strong></div><div className="summary-card"><span>Data Status</span><strong>{dataStatus(opportunities)}</strong></div>
    </section>
    <div className="section-heading"><div><h2>Best Opportunities</h2><p>Only backend BusinessOpportunity results are displayed. Unknown profit is not converted to zero.</p></div></div>
    {!opportunities.length ? <div className="empty card">No executable opportunities are available for the selected conditions. This does not mean zero profit.</div> : <div className="opportunity-grid">{opportunities.map((o, index) => <section className="opportunity-card card" key={`${o.strategy_id}-${o.title}-${index}`}>
      <div className="opportunity-top"><div><span className="strategy-tag">{o.strategy_id}</span><h3>{o.title}</h3></div><span className={`quality quality-${String(o.confidence || 'unavailable').toLowerCase()}`}>{o.confidence || 'Unavailable'}</span></div>
      <div className="metrics"><Value label="Expected Profit" value={formatSilver(o.expected_profit)} /><Value label="ROI" value={formatPercent(o.roi_percent)} /><Value label="Profit / Hour" value={formatSilver(o.profit_per_hour)} /><Value label="Required Capital" value={formatSilver(o.required_capital)} /><Value label="Capital Utilization" value={o.capital_utilization_percent == null ? 'Unavailable' : formatPercent(o.capital_utilization_percent)} /><Value label="Required Quantity" value={o.required_quantity} /><Value label="Executable Quantity" value={o.executable_quantity} /><Value label="Risk" value={o.risk} /><Value label="Liquidity" value={o.liquidity} /><Value label="Freshness" value={o.freshness} /><Value label="Time" value={o.time_required} /></div>
      {o.explanation && <p className="explanation">{o.explanation}</p>}
    </section>)}</div>}
    <div className="section-heading"><div><h2>Strategy Explorer</h2><p>Strategy metadata is discovered from the registry through <code>/api/strategies</code>.</p></div></div>
    <div className="strategy-grid">{strategies.map((s) => <article className="strategy-card card" key={s.strategy_id}><div><span className="strategy-tag">{s.strategy_id}</span><h3>{s.name}</h3></div><p>{s.description}</p><span className={s.calculator_key ? 'state available' : 'state metadata'}>{s.calculator_key ? 'Executable' : 'Metadata only'}</span></article>)}</div>
  </section>;
}

function Chart({ rows }) {
  const points = rows.filter((x) => x.sell_price_min != null);
  if (!points.length) return <div className="empty">No market data available.</div>;
  const values = points.map((x) => x.sell_price_min); const min = Math.min(...values); const range = Math.max(...values) - min || 1;
  const polyline = values.map((value, i) => `${(i / Math.max(values.length - 1, 1)) * 100},${90 - ((value - min) / range) * 80}`).join(' ');
  return <svg viewBox="0 0 100 100" className="chart" aria-label="Price history chart"><polyline points={polyline} fill="none" stroke="currentColor" vectorEffect="non-scaling-stroke" /></svg>;
}

function App() {
  const [itemId, setItem] = useState(''); const [city, setCity] = useState(''); const [quality, setQuality] = useState(1); const [server, setServer] = useState('east'); const [serverNames, setServerNames] = useState({}); const [range, setRange] = useState('24h');
  const [capital, setCapital] = useState(''); const [risk, setRisk] = useState(''); const [strategy, setStrategy] = useState(''); const [current, setCurrent] = useState(); const [analysis, setAnalysis] = useState(); const [spread, setSpread] = useState(); const [history, setHistory] = useState([]); const [status, setStatus] = useState(); const [opps, setOpps] = useState([]); const [dashboardOpps, setDashboardOpps] = useState([]); const [strategies, setStrategies] = useState([]); const [scanSort, setScanSort] = useState('roi'); const [dashboardSort, setDashboardSort] = useState('profit'); const [loadingDashboard, setLoadingDashboard] = useState(false); const [error, setError] = useState('');

  async function loadServerNames() {
    const entries = await Promise.all(SERVER_IDS.map(async (id) => { try { const response = await fetch(`${API}/api/sources?server=${id}`); if (!response.ok) return [id, id]; const data = await response.json(); return [id, data.server_name || id]; } catch { return [id, id]; } }));
    setServerNames(Object.fromEntries(entries));
  }
  async function loadStrategies() { try { const response = await fetch(`${API}/api/strategies`); if (response.ok) setStrategies((await response.json()).strategies || []); } catch { setStrategies([]); } }
  async function loadDashboard() {
    setLoadingDashboard(true);
    try { const params = new URLSearchParams({ server, sort: dashboardSort, limit: '12' }); if (capital) params.set('capital', capital); if (risk) params.set('risk', risk); if (strategy) params.set('strategy', strategy); const response = await fetch(`${API}/api/opportunities?${params}`); if (!response.ok) throw Error('Strategy API request failed'); setDashboardOpps((await response.json()).opportunities || []); setError(''); }
    catch (e) { setDashboardOpps([]); setError(e.message); } finally { setLoadingDashboard(false); }
  }
  async function loadMarket() {
    if (!itemId || !city) { setCurrent(); setAnalysis(); setSpread(); setHistory([]); setOpps([]); return; }
    try {
      const q = new URLSearchParams({ item_id: itemId, city, quality, server });
      const [a, b, c, d, e, f] = await Promise.all([fetch(`${API}/api/market/prices?${q}`), fetch(`${API}/api/market/analysis?${q}&range=${range}`), fetch(`${API}/api/market/history?${q}`), fetch(`${API}/api/collector/status`), fetch(`${API}/api/market/spread?item_id=${encodeURIComponent(itemId)}&quality=${quality}&server=${server}&range=${range}`), fetch(`${API}/api/arbitrage?item_id=${encodeURIComponent(itemId)}&quality=${quality}&server=${server}&sort=${scanSort}`)]);
      if (!a.ok || !b.ok || !c.ok) throw Error('Market API request failed'); setCurrent((await a.json())[0]); setAnalysis(await b.json()); setHistory(await c.json()); if (e.ok) setSpread(await e.json()); if (f.ok) setOpps((await f.json()).opportunities || []); if (d.ok) setStatus(await d.json());
    } catch (e) { setError(e.message); setCurrent(); setAnalysis(); setSpread(); setHistory([]); setOpps([]); }
  }
  async function load() { setError(''); await loadStrategies(); await loadDashboard(); await loadMarket(); }
  useEffect(() => { loadServerNames(); loadStrategies(); }, []);
  useEffect(() => { loadDashboard(); }, [server, dashboardSort, risk, strategy, capital]);
  useEffect(() => { loadMarket(); }, [server, range, scanSort, itemId, city, quality]);
  const sell = analysis?.statistics?.sell || {};

  return <main>
    <Dashboard server={server} setServer={setServer} serverNames={serverNames} capital={capital} setCapital={setCapital} risk={risk} setRisk={setRisk} strategy={strategy} setStrategy={setStrategy} sort={dashboardSort} setSort={setDashboardSort} opportunities={dashboardOpps} strategies={strategies} loading={loadingDashboard} onRefresh={load} />
    {error && <div className="error">{error}</div>}
    <details className="secondary-view"><summary>Market Analysis & Arbitrage</summary>
      <section className="controls card"><label>Item ID<input value={itemId} onChange={(e) => setItem(e.target.value)} /></label><label>City<input value={city} onChange={(e) => setCity(e.target.value)} /></label><label>Quality<input type="number" min="1" value={quality} onChange={(e) => setQuality(e.target.value)} /></label><label>Server<select value={server} onChange={(e) => setServer(e.target.value)}>{SERVER_IDS.map((x) => <option key={x}>{x}</option>)}</select></label><label>Period<select value={range} onChange={(e) => setRange(e.target.value)}>{['12h', '24h', '7d', '30d', 'all'].map((x) => <option key={x}>{x}</option>)}</select></label><button onClick={load}>Analyze</button></section>
      {current && <><h3>Current Market</h3><section className="card metrics"><Value label="Sell Min" value={current.sell_price_min} /><Value label="Buy Max" value={current.buy_price_max} /><Value label="Last Updated" value={current.updated_at} /></section></>}
      {!analysis ? <div className="empty">Enter an item ID and city to inspect market analysis.</div> : !analysis.data_sufficient ? <div className="empty">Not enough historical data.</div> : <><section className="card metrics"><Value label="Latest" value={sell.latest} /><Value label="Average" value={sell.average} /><Value label="Min / Max" value={`${sell.min ?? '—'} / ${sell.max ?? '—'}`} /><Value label="Change %" value={analysis.change?.sell?.percent == null ? '—' : `${analysis.change.sell.percent.toFixed(2)}%`} /></section><Chart rows={analysis.trend?.series || history} />{spread?.data_sufficient && <section className="card metrics"><Value label="Lowest City" value={spread.spread.lowest_city} /><Value label="Highest City" value={spread.spread.highest_city} /><Value label="Spread" value={`${spread.spread.absolute} (${spread.spread.percent?.toFixed(2)}%)`} /></section>}</>}
      <h2>Arbitrage Scanner</h2><section className="controls card"><label>Sort<select value={scanSort} onChange={(e) => setScanSort(e.target.value)}>{[['roi','ROI'],['profit','Profit'],['spread','Spread %'],['stability','Historical Stability'],['freshness','Freshness'],['confidence','Confidence']].map(([v,t]) => <option key={v} value={v}>{t}</option>)}</select></label></section>
      {!opps.length ? <div className="empty">No arbitrage opportunities.</div> : opps.map((o) => <section className="card opportunity-card" key={`${o.item_id}-${o.buy.city}-${o.sell.city}`}><div><strong>{o.item_id}</strong><br />{o.buy.city} → {o.sell.city}</div><div className="metrics"><Value label="Buy" value={o.buy.price} /><Value label="Sell" value={o.sell.price} /><Value label="Spread" value={`${o.spread.absolute} (${o.spread.percent.toFixed(2)}%)`} /><Value label="Gross Profit" value={o.profit.gross_profit} /><Value label="ROI" value={o.profit.roi_percent == null ? 'Cost model not configured' : `${o.profit.roi_percent.toFixed(2)}%`} /><Value label="Executable" value={o.liquidity?.executable_quantity ?? 'Unknown'} /><Value label="Slippage" value={o.slippage?.status === 'available' ? `${o.slippage.total_percent.toFixed(2)}%` : 'Unavailable'} /><Value label="Realistic Profit" value={o.realistic_profit?.net_profit ?? 'Unavailable'} /><Value label="Freshness" value={o.data?.freshness} /><Value label="Confidence" value={o.confidence} /></div></section>)}
      {status && <div className="status">Collector: {status.running ? 'running' : 'idle'} · Last collection: {status.last_collection?.finished_at ?? '—'}</div>}
    </details>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
