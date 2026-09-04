import React from 'react';
import { NAV } from '../constants';
import { Icon } from './common';

const RECENT_COLLECTION_MS = 60 * 60 * 1000;

function collectorStatus(data) {
  if (!data) return 'UNKNOWN';
  if (data.running === true) return 'RUNNING';
  const last = data.last_collection;
  if (!last) return 'UNKNOWN';
  if (last.success === false) return 'ERROR';
  if (last.success !== true || !last.finished_at) return 'UNKNOWN';
  const finishedAt = Date.parse(last.finished_at);
  if (!Number.isFinite(finishedAt) || Date.now() - finishedAt > RECENT_COLLECTION_MS) return 'UNKNOWN';
  return 'IDLE';
}

function statusValue(status, data) {
  if (status === 'backend') return data?.backend?.status || 'UNKNOWN';
  if (status === 'collector') return collectorStatus(data?.collector);
  if (status === 'nats') {
    if (!data?.liquidity) return 'UNKNOWN';
    if (data.liquidity.connected === false) return 'OFFLINE';
    if (data.liquidity.connected === true && data.liquidity.subscription_active === true) return 'CONNECTED';
    return 'UNKNOWN';
  }
  if (status === 'database') return 'UNKNOWN';
  if (status === 'engine') return data?.backend?.status === 'ONLINE' ? 'AVAILABLE' : 'UNKNOWN';
  return 'UNKNOWN';
}

function statusTone(value) {
  if (['ONLINE', 'RUNNING', 'CONNECTED', 'AVAILABLE'].includes(value)) return 'good';
  if (value === 'IDLE') return 'warn';
  if (['ERROR', 'OFFLINE'].includes(value)) return 'bad';
  return 'neutral';
}

function formatStatusTime(value) {
  if (!value) return null;
  const time = new Date(value);
  return Number.isNaN(time.getTime()) ? null : time.toLocaleString();
}

function SystemStatus({ status, statusLoading, onStatusRefresh }) {
  const rows = [
    ['Backend API', 'backend'],
    ['Collector', 'collector'],
    ['AODP NATS', 'nats'],
    ['Database', 'database'],
    ['Market Engine', 'engine'],
  ];
  const collector = status?.collector;
  const liquidity = status?.liquidity;
  const collectorTime = formatStatusTime(collector?.last_collection?.finished_at);
  const messageTime = formatStatusTime(liquidity?.last_message_at);

  return <div className="system-status-panel" role="status" aria-label="System Status">
    <div className="system-status-head"><strong>System Status</strong><button className="system-status-refresh" onClick={onStatusRefresh} disabled={statusLoading}>{statusLoading ? 'Loading…' : 'Refresh'}</button></div>
    <div className="system-status-rows">
      {rows.map(([label, key]) => {
        const value = statusValue(key, status);
        return <div className="system-status-row" key={key}><span className={`status-indicator ${statusTone(value)}`}/><span className="system-status-name">{label}</span><strong className={`system-status-value ${statusTone(value)}`}>{value}</strong></div>;
      })}
    </div>
    {(collectorTime || messageTime || liquidity?.messages_received != null) && <div className="system-status-details">
      {collectorTime && <span>Last collection: {collectorTime}</span>}
      {liquidity?.messages_received != null && <span>Messages: {liquidity.messages_received}</span>}
      {messageTime && <span>Last message: {messageTime}</span>}
    </div>}
  </div>;
}

export function Sidebar({ page, setPage, statusOpen, status, statusLoading, onStatusToggle, onStatusRefresh }) {
  return <aside className="sidebar"><div className="brand"><div className="brand-mark">A</div><div><strong>ALBION</strong><span>MARKET HELPER</span></div></div><nav>{NAV.map(([id, label]) => <button key={id} className={page === id ? 'active' : ''} onClick={() => setPage(id)}><Icon name={id}/><span>{label}</span></button>)}</nav><div className="sidebar-bottom"><button className={`system-status-trigger ${statusOpen ? 'active' : ''}`} onClick={onStatusToggle} aria-expanded={statusOpen}><span className="live-dot"/><span>System Status</span></button>{statusOpen && <SystemStatus status={status} statusLoading={statusLoading} onStatusRefresh={onStatusRefresh}/>}</div></aside>;
}

export function Header({ page, refreshing, refresh, profile, statusOpen, status, statusLoading, onStatusToggle, onStatusRefresh }) {
  return <header className="topbar"><div><span className="mobile-brand">ALBION</span><span className="breadcrumb">Business Intelligence / {NAV.find(x => x[0] === page)?.[1]}</span></div><div className="top-actions"><button className={`system-status-mobile ${statusOpen ? 'active' : ''}`} onClick={onStatusToggle} aria-expanded={statusOpen}>Status</button>{statusOpen && <SystemStatus status={status} statusLoading={statusLoading} onStatusRefresh={onStatusRefresh}/>}<button className="icon-button" onClick={refresh} disabled={refreshing} aria-label="새로고침"><Icon name="refresh"/></button><div className="profile-chip">{profile.avatar ? <img className="avatar avatar-image" src={profile.avatar} alt="프로필"/> : <div className="avatar">{profile.name?.[0]?.toUpperCase() || 'U'}</div>}<span>{profile.name || '사용자'}</span></div></div></header>;
}

export function MobileNav({ page, setPage }) {
  return <nav className="mobile-nav">{NAV.slice(0, 5).map(([id, label]) => <button key={id} className={page === id ? 'active' : ''} onClick={() => setPage(id)}><Icon name={id}/><span>{label}</span></button>)}</nav>;
}
