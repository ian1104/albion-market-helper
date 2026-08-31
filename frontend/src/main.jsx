import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { NAV, SERVER_NAMES } from './constants';
import { useBusinessData } from './hooks/useBusinessData';
import { Sidebar, Header, MobileNav } from './components/Layout';
import { OpportunityDrawer } from './components/common';
import { DashboardPage, MarketPage, StrategyPage, PortfolioPage, InsightPage, SettingsPage } from './pages';

const defaultProfile = { name: '', avatar: '', silver: '', items: [], server: 'east', minRoi: '', minProfit: '', risk: '' };

function readProfile() {
  try { return JSON.parse(localStorage.getItem('amh-profile')) || defaultProfile; } catch { return defaultProfile; }
}

function App() {
  const [page, setPage] = useState('dashboard');
  const [server, setServer] = useState('east');
  const [capital, setCapital] = useState('');
  const [risk, setRisk] = useState('');
  const [strategy, setStrategy] = useState('');
  const [sort, setSort] = useState('profit');
  const [selected, setSelected] = useState(null);
  const [profile, setProfileState] = useState(readProfile);
  const [marketQuery, setMarketQuery] = useState({ itemId: '', city: '', quality: 1 });

  const setProfile = value => { setProfileState(value); localStorage.setItem('amh-profile', JSON.stringify(value)); };
  const business = useBusinessData({ server, sort, capital, risk, strategy });

  const state = { server, setServer, names: { ...SERVER_NAMES, ...business.names }, capital, setCapital, risk, setRisk, strategy, setStrategy, sort, setSort, strategies: business.strategies, opportunities: business.opportunities, loading: business.loading, error: business.error };

  const openMarket = itemId => {
    setSelected(null);
    setMarketQuery({ itemId, city: '', quality: 1 });
    setPage('market');
  };

  let content = <DashboardPage state={state} setPage={setPage} open={setSelected}/>;
  if (page === 'market') content = <MarketPage server={server} initialItemId={marketQuery.itemId}/>;
  if (page === 'strategies') content = <StrategyPage strategies={business.strategies}/>;
  if (page === 'portfolio') content = <PortfolioPage profile={profile} setProfile={setProfile}/>;
  if (page === 'insights') content = <InsightPage opportunities={business.opportunities}/>;
  if (page === 'settings') content = <SettingsPage profile={profile} setProfile={setProfile} names={{ ...SERVER_NAMES, ...business.names }}/>;

  return <div className="app-shell"><Sidebar page={page} setPage={setPage}/><div className="main-shell"><Header page={page} refresh={business.refresh} refreshing={business.loading} profile={profile}/><main>{content}</main></div><OpportunityDrawer opportunity={selected} onClose={() => setSelected(null)} onMarket={openMarket}/><MobileNav page={page} setPage={setPage}/></div>;
}

createRoot(document.getElementById('root')).render(<App/>);
