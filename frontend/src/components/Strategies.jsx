import React from 'react';
import { Badge, text } from './common';

export default function Strategies({ strategies }) {
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">STRATEGY EXPLORER</p><h1>사업 전략</h1><p>Registry에 등록된 전략만 표시합니다. 계산기가 없는 전략은 결과를 생성하지 않습니다.</p></div></div><div className="strategy-cards">
    {!strategies.length ? <div className="panel"><strong>등록된 전략이 없습니다.</strong></div> : strategies.map(x => <article className="large-strategy-card" key={x.strategy_id}><div className="strategy-card-head"><div className="strategy-symbol large">{String(x.name || x.strategy_id).slice(0, 1)}</div><Badge tone={x.calculator_key ? 'good' : 'neutral'}>{x.calculator_key ? '사용 가능' : '데이터 준비 중'}</Badge></div><h2>{text(x.name, x.strategy_id)}</h2><p>{text(x.description, '등록된 전략 설명이 없습니다.')}</p><div className="card-foot"><span>{text(x.category, '경제 활동')}</span><span>{x.calculator_key ? '계산 가능' : '메타데이터만 제공'}</span></div></article>)}
  </div></div>;
}
