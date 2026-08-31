import React from 'react';

export default function Insights({ opportunities }) {
  const usable = opportunities.filter(x => x.expected_profit != null);
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">ANALYTICAL CONTEXT</p><h1>인사이트</h1><p>계산 엔진의 결과를 해석하기 위한 공간입니다. AI가 없는 상태에서는 임의의 분석을 생성하지 않습니다.</p></div></div><section className="insight-grid">
    <div className="panel insight-card"><div className="insight-icon">◎</div><h2>데이터 기반 판단</h2><p>{usable.length ? `현재 ${usable.length}개의 기회에서 계산 가능한 수익 데이터가 확인됩니다.` : '현재 수익을 계산할 수 있는 충분한 기회 데이터가 없습니다.'}</p></div>
    <div className="panel insight-card"><div className="insight-icon">◇</div><h2>불확실성 우선 표시</h2><p>가격 데이터만으로 주문 깊이나 실제 거래량을 추정하지 않습니다. 확인되지 않은 값은 Unknown 또는 Unavailable로 유지합니다.</p></div>
  </section></div>;
}
