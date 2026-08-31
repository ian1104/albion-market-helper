import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

function Chart({ rows }) {
  const points = rows.filter((x) => x.sell_price_min != null);
  if (!points.length) return <div className="empty">No market data available.</div>;
  const values = points.map((x) => x.sell_price_min);
  const min = Math.min(...values);
  const range = Math.max(...values) - min || 1;
  const polyline = values.map((value, i) => `${(i / Math.max(values.length - 1, 1)) * 100},${90 - ((value - min) / range) * 80}`).join(' ');
  return <svg viewBox="0 0 100 100" className="chart" aria-label="Price history chart"><polyline points={polyline} fill="none" stroke="currentColor" vectorEffect="non-scaling-stroke" /></svg>;
}

function Value({ label, value }) {
  return <div><span>{label}</span><strong>{value ?? '—'}</strong></div>;
}

function Dashboard({ server, capital, setCapital, risk, setRisk, strategy, setStrategy, sort, setSort, opportunities, strategies }) {
  const implemented = strategies.filter((s) => s.calculator_key);
  return <section>
    <h1>Albion Business Dashboard</h1>
    <section className="controls">
      <label>Server<select value={server} onChange={() => {}} disabled><option>{server}</option></select></label>
      <label>Capital (Silver)<input type="number" min="1" value={capital} onChange={(e) => setCapital(e.target.value)} placeholder="Enter capital" /></label>
      <label>Risk<select value={risk} onChange={(e) => setRisk(e.target.value)}><option value="">Any</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="unknown">Unknown</option></select></label>
      <label>Strategy<select value={strategy} onChange={(e) => setStrategy(e.target.value)}><option value="">All implemented</option>{implemented.map((s) => <option key={s.strategy_id} value={s.strategy_id}>{s.name}</option>)}</select></label>
      <label>Rank<select value={sort} onChange={(e) => setSort(e.target.value)}><option value="profit">Expected Profit</option><option value="roi">ROI</option><option value="capital_efficiency">Capital Efficiency</option><option value="capital">Required Capital</option><option value="risk">Risk</option><option value="confidence">Confidence</option><option value="freshness">Freshness</option></select></label>
    </section>
    <h2>Best Opportunities</h2>
    {!opportunities.length ? <div className="empty">No implemented strategy opportunities available.</div> : opportunities.map((o) => <section className="card opportunity" key={`${o.strategy_id}-${o.title}`}>
      <div><strong>{o.strategy_id}</strong><br />{o.title}</div>
      <Value label="Expected Profit" value={o.expected_profit} /><Value label="ROI" value={o.roi_percent == null ? 'Unavailable' : `${o.roi_percent.toFixed(2)}%`} />
      <Value label="Profit / Hour" value={o.profit_per_hour == null ? 'Unavailable' : o.profit_per_hour.toFixed(2)} />
      <Value label="Required Capital" value={o.required_capital} /><Value label="Utilization" value={o.capital_utilization_percent == null ? '—' : `${o.capital_utilization_percent.toFixed(1)}%`} />
      <Value label="Risk" value={o.risk} /><Value label="Liquidity" value={o.liquidity} /><Value label="Confidence" value={o.confidence} /><Value label="Freshness" value={o.freshness} />
    </section>)}
  </section>;
}

function App() {
  const [itemId, setItem] = useState('');
  const [city, setCity] = useState('');
  const [quality, setQuality] = useState(1);
  const [server, setServer] = useState('east');
  const [range, setRange] = useState('24h');
  const [capital, setCapital] = useState('');
  const [risk, setRisk] = useState('');
  const [strategy, setStrategy] = useState('');
  const [current, setCurrent] = useState();
  const [analysis, setAnalysis] = useState();
  const [spread, setSpread] = useState();
  const [history, setHistory] = useState([]);
  const [status, setStatus] = useState();
  const [opps, setOpps] = useState([]);
  const [dashboardOpps, setDashboardOpps] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [scanSort, setScanSort] = useState('roi');
  const [dashboardSort, setDashboardSort] = useState('profit');
  const [error, setError] = useState('');

  async function loadDashboard() {
    try {
      const params = new URLSearchParams({ server, sort: dashboardSort, limit: '12' });
      if (capital) params.set('capital', capital);
      if (risk) params.set('risk', risk);
      if (strategy) params.set('strategy', strategy);
      const response = await fetch(`${API}/api/opportunities?${params}`);
      if (!response.ok) throw Error('Strategy API request failed');
      setDashboardOpps((await response.json()).opportunities || []);
    } catch (e) {
      setDashboardOpps([]);
      setError(e.message);
    }
  }

  async function load() {
    setError('');
    try {
      const strategyResponse = await fetch(`${API}/api/strategies`);
      if (strategyResponse.ok) setStrategies((await strategyResponse.json()).strategies || []);
      await loadDashboard();
      if (!itemId || !city) {
        setCurrent(); setAnalysis(); setSpread(); setHistory([]); setOpps([]);
        return;
      }
      const q = new URLSearchParams({ item_id: itemId, city, quality, server });
      const [a, b, c, d, e, f] = await Promise.all([
        fetch(`${API}/api/market/prices?${q}`),
        fetch(`${API}/api/market/analysis?${q}&range=${range}`),
        fetch(`${API}/api/market/history?${q}`),
        fetch(`${API}/api/collector/status`),
        fetch(`${API}/api/market/spread?item_id=${encodeURIComponent(itemId)}&quality=${quality}&server=${server}&range=${range}`),
        fetch(`${API}/api/arbitrage?item_id=${encodeURIComponent(itemId)}&quality=${quality}&server=${server}&sort=${scanSort}`),
      ]);
      if (!a.ok || !b.ok || !c.ok) throw Error('Market API request failed');
      setCurrent((await a.json())[0]);
      setAnalysis(await b.json());
      setHistory(await c.json());
      if (e.ok) setSpread(await e.json());
      if (f.ok) setOpps((await f.json()).opportunities || []);
      if (d.ok) setStatus(await d.json());
    } catch (e) {
      setError(e.message);
      setCurrent(); setAnalysis(); setSpread(); setHistory([]); setOpps([]);
    }
  }

  useEffect(() => { load(); }, [server, range, scanSort]);
  const sell = analysis?.statistics?.sell || {};

  return <main>
    <Dashboard server={server === 'east' ? 'Asia / East' : server} capital={capital} setCapital={setCapital} risk={risk} setRisk={setRisk} strategy={strategy} setStrategy={setStrategy} sort={dashboardSort} setSort={setDashboardSort} opportunities={dashboardOpps} strategies={strategies} />
    <section className="status">Registered strategies: {strategies.map((s) => `${s.name}${s.calculator_key ? '' : ' (metadata only)'}`).join(', ') || 'None'}. No fabricated strategy results are shown.</section>
    <button onClick={loadDashboard}>Refresh Dashboard</button>

    <h2>Market Analysis</h2>
    <section className="controls">
      <label>Item ID<input value={itemId} onChange={(e) => setItem(e.target.value)} /></label>
      <label>City<input value={city} onChange={(e) => setCity(e.target.value)} /></label>
      <label>Quality<input type="number" min="1" value={quality} onChange={(e) => setQuality(e.target.value)} /></label>
      <label>Server<select value={server} onChange={(e) => setServer(e.target.value)}>{['east', 'west', 'europe'].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>Period<select value={range} onChange={(e) => setRange(e.target.value)}>{['12h', '24h', '7d', '30d', 'all'].map((x) => <option key={x}>{x}</option>)}</select></label>
      <button onClick={load}>Analyze</button>
    </section>
    {error && <div className="error">{error}</div>}
    {current && <><h3>Current Market</h3><section className="card"><Value label="Sell Min" value={current.sell_price_min} /><Value label="Buy Max" value={current.buy_price_max} /><Value label="Last Updated" value={current.updated_at} /></section></>}
    {!analysis ? <div className="empty">Enter an item ID and city to inspect market analysis.</div> : !analysis.data_sufficient ? <div className="empty">Not enough historical data.</div> : <>
      <section className="card"><Value label="Latest" value={sell.latest} /><Value label="Average" value={sell.average} /><Value label="Min / Max" value={`${sell.min ?? '—'} / ${sell.max ?? '—'}`} /><Value label="Change %" value={analysis.change?.sell?.percent == null ? '—' : `${analysis.change.sell.percent.toFixed(2)}%`} /></section>
      <Chart rows={analysis.trend?.series || history} />
      {spread?.data_sufficient && <section className="card"><Value label="Lowest City" value={spread.spread.lowest_city} /><Value label="Highest City" value={spread.spread.highest_city} /><Value label="Spread" value={`${spread.spread.absolute} (${spread.spread.percent?.toFixed(2)}%)`} /></section>}
    </>}

    <h2>Arbitrage Scanner</h2>
    <section className="controls"><label>Sort<select value={scanSort} onChange={(e) => setScanSort(e.target.value)}>{[['roi','ROI'],['profit','Profit'],['spread','Spread %'],['stability','Historical Stability'],['freshness','Freshness'],['confidence','Confidence']].map(([v,t]) => <option key={v} value={v}>{t}</option>)}</select></label><button onClick={load}>Scan</button></section>
    {!opps.length ? <div className="empty">No arbitrage opportunities.</div> : opps.map((o) => <section className="card opportunity" key={`${o.item_id}-${o.buy.city}-${o.sell.city}`}>
      <div><strong>{o.item_id}</strong><br />{o.buy.city} → {o.sell.city}</div>
      <Value label="Buy" value={o.buy.price} /><Value label="Sell" value={o.sell.price} /><Value label="Spread" value={`${o.spread.absolute} (${o.spread.percent.toFixed(2)}%)`} />
      <Value label="Gross Profit" value={o.profit.gross_profit} /><Value label="ROI" value={o.profit.roi_percent == null ? 'Cost model not configured' : `${o.profit.roi_percent.toFixed(2)}%`} />
      <Value label="Requested" value={o.liquidity?.requested_quantity} /><Value label="Executable" value={o.liquidity?.executable_quantity ?? 'Unknown'} />
      <Value label="Slippage" value={o.slippage?.status === 'available' ? `${o.slippage.total_percent.toFixed(2)}%` : 'Unavailable'} />
      <Value label="Historical" value={o.historical?.positive_spread_ratio == null ? 'Insufficient' : `${o.historical.positive_spread_ratio.toFixed(1)}% positive`} />
      <Value label="Freshness" value={o.data?.freshness} /><Value label="Confidence" value={o.confidence} />
      <Value label="Realistic Profit" value={o.realistic_profit?.net_profit ?? 'Unavailable'} />
    </section>)}
    {status && <div className="status">Collector: {status.running ? 'running' : 'idle'} · Last collection: {status.last_collection?.finished_at ?? '—'}</div>}
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
