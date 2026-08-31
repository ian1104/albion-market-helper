import React, { useState } from 'react';
import { money } from './common';

export default function Portfolio({ profile, setProfile }) {
  const [item, setItem] = useState('');
  const [qty, setQty] = useState('');
  const add = () => { if (!item || !qty || Number(qty) <= 0) return; setProfile({ ...profile, items: [...(profile.items || []), { item, qty: Number(qty) }] }); setItem(''); setQty(''); };
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">PERSONAL ECONOMY</p><h1>내 자산</h1><p>게임 계정과 자동 동기화하지 않습니다. 직접 입력한 정보만 저장합니다.</p></div></div><section className="portfolio-grid">
    <div className="panel"><p className="eyebrow">LIQUID CAPITAL</p><h2>보유 Silver</h2><div className="big-number">{money(profile.silver)} <small>S</small></div><label className="form-row"><span>수정</span><input type="number" min="0" value={profile.silver} onChange={e => setProfile({ ...profile, silver: e.target.value })}/></label></div>
    <div className="panel"><p className="eyebrow">HOLDINGS</p><h2>보유 아이템</h2><div className="holding-form"><input value={item} onChange={e => setItem(e.target.value)} placeholder="Item ID"/><input type="number" min="1" value={qty} onChange={e => setQty(e.target.value)} placeholder="수량"/><button className="primary-button" onClick={add}>추가</button></div><div className="holding-list">{!(profile.items || []).length ? <span className="muted">등록된 보유 아이템이 없습니다.</span> : profile.items.map((x, i) => <div key={`${x.item}-${i}`}><span>{x.item}</span><strong>× {x.qty}</strong><button onClick={() => setProfile({ ...profile, items: profile.items.filter((_, j) => i !== j) })}>삭제</button></div>)}</div></div>
  </section></div>;
}
