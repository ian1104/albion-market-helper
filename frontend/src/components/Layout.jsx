import React from 'react';
import { NAV } from '../constants';
import { Icon } from './common';

export function Sidebar({ page, setPage }) {
  return <aside className="sidebar"><div className="brand"><div className="brand-mark">A</div><div><strong>ALBION</strong><span>MARKET HELPER</span></div></div><nav>{NAV.map(([id, label]) => <button key={id} className={page === id ? 'active' : ''} onClick={() => setPage(id)}><Icon name={id}/><span>{label}</span></button>)}</nav><div className="sidebar-bottom"><div className="system-pill"><span className="live-dot"/> Market engine</div><small>Backend-driven analysis</small></div></aside>;
}

export function Header({ page, refreshing, refresh, profile }) {
  return <header className="topbar"><div><span className="mobile-brand">ALBION</span><span className="breadcrumb">Business Intelligence / {NAV.find(x => x[0] === page)?.[1]}</span></div><div className="top-actions"><button className="icon-button" onClick={refresh} disabled={refreshing} aria-label="새로고침"><Icon name="refresh"/></button><div className="profile-chip">{profile.avatar ? <img className="avatar avatar-image" src={profile.avatar} alt="프로필"/> : <div className="avatar">{profile.name?.[0]?.toUpperCase() || 'U'}</div>}<span>{profile.name || '사용자'}</span></div></div></header>;
}

export function MobileNav({ page, setPage }) {
  return <nav className="mobile-nav">{NAV.slice(0, 5).map(([id, label]) => <button key={id} className={page === id ? 'active' : ''} onClick={() => setPage(id)}><Icon name={id}/><span>{label}</span></button>)}</nav>;
}
