import React from 'react';
import { SERVERS } from '../constants';

export default function Settings({ profile, setProfile, names }) {
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">PREFERENCES</p><h1>설정</h1><p>개인 프로필과 경제 분석 기본값을 관리합니다.</p></div></div><section className="settings-grid">
    <div className="panel"><p className="eyebrow">PROFILE</p><h2>프로필</h2><label className="form-row"><span>표시 이름</span><input value={profile.name} onChange={e => setProfile({ ...profile, name: e.target.value })}/></label><label className="form-row"><span>프로필 이미지 URL</span><input value={profile.avatar || ''} onChange={e => setProfile({ ...profile, avatar: e.target.value })} placeholder="선택 사항"/></label><p className="muted">설정은 이 브라우저의 localStorage에 저장됩니다.</p></div>
    <div className="panel"><p className="eyebrow">ECONOMY</p><h2>경제 설정</h2><label className="form-row"><span>주요 서버</span><select value={profile.server} onChange={e => setProfile({ ...profile, server: e.target.value })}>{SERVERS.map(id => <option key={id} value={id}>{names[id] || id}</option>)}</select></label><label className="form-row"><span>최소 ROI</span><input type="number" value={profile.minRoi} onChange={e => setProfile({ ...profile, minRoi: e.target.value })}/></label><label className="form-row"><span>최소 수익</span><input type="number" value={profile.minProfit} onChange={e => setProfile({ ...profile, minProfit: e.target.value })}/></label><label className="form-row"><span>위험 선호</span><select value={profile.risk} onChange={e => setProfile({ ...profile, risk: e.target.value })}><option value="">전체</option><option value="low">낮음</option><option value="medium">보통</option><option value="high">높음</option></select></label></div>
  </section></div>;
}
