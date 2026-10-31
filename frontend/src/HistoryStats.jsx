import React from 'react'

const money = value => value == null ? '기록 없음' : value.toLocaleString('ko-KR') + '원'

export default function HistoryStats({stats}) {
  if(!stats)return null
  return <section aria-label="지인별 금액 통계" style={{padding:10,margin:'8px 0',border:'1px solid var(--border, #ddd)',borderRadius:8}}>
    <strong>주고받은 금액 비교</strong>
    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(160px,1fr))',gap:8,marginTop:8}}>
      {[['paid','내가 낸'],['received','내가 받은']].map(([direction,title])=>{
        const item=stats[direction]
        if(!item)return null
        return <div key={direction}>
          <strong>{title} 평균: {money(item.average_krw)}</strong>
          <p>{item.count}건 · 중앙값 {money(item.median_krw)}</p>
          <p>합계 {money(item.total_krw)} · 최근 {money(item.latest_krw)}</p>
        </div>
      })}
    </div>
    {['paid','received'].filter(key=>stats[key]?.recent_spike).map(key=>{
      const item=stats[key]
      return <p key={key} role="note"><strong>최근 {key==='paid'?'지급':'수령'} 급증 신호:</strong> 이전 기록 중앙값 {money(item.previous_median_krw)} → 최근 {money(item.latest_krw)} ({item.recent_ratio}배)</p>
    })}
    <small>금액이 0원인 기록은 평균에서 제외합니다. 최근 급증은 이전 양수 거래 2건 이상을 기준으로 2배 이상 증가한 경우의 비교 신호이며 통계적 이상치 판정은 아닙니다.</small>
  </section>
}
