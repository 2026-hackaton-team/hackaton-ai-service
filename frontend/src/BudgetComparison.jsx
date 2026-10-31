import React from 'react'
import {compareBudget} from './budgetComparison.js'

const money = amount => amount.toLocaleString('ko-KR') + '원'

export default function BudgetComparison({result, budget, compact=false}) {
  const comparison=compareBudget(result,budget)
  if(!comparison)return null
  const {amount,gap,baseline,adjustments}=comparison
  return <details aria-label="추천 금액과 예산 비교" className="ai-result-card ai-analysis-details">
    <summary style={{cursor:'pointer'}}><strong>추천 근거 · {comparison.title}</strong></summary>
    {amount == null
      ? <p>예산 {money(comparison.budget)} · 금액 제안 보류</p>
      : <p>예산 {money(comparison.budget)} → {comparison.referenceOnly?'비교 참고액':'추천액'} {money(amount)} · {gap>0?'잔여 '+money(gap):'예산과 동일'} ({comparison.usagePercent}% 사용)</p>}
    <p style={{fontSize:12}}>{comparison.detail}</p>
    {compact&&<div style={{fontSize:12}}>
      {(result?.history_stats?.paid?.count||0)+(result?.history_stats?.received?.count||0)===0&&
        <p>선택한 지인과의 거래 기록이 없어 일반 비교 기준을 참고했습니다.</p>}
      {(result?.v4_analysis?.relationship_adjustments||[]).slice(0,3).map((item,index)=>
        <p key={index}>{item.reason}</p>)}
      {comparison.referenceOnly&&<p>법률 확인 전 참고액이며 실제 송금 가능 여부는 별도 확인이 필요합니다.</p>}
    </div>}
    {!compact&&amount!=null&&<div style={{fontSize:12}}>
      {result?.budget_analysis?.raw_base_amount_krw!=null&&result?.budget_analysis?.raw_personalized_amount_krw!=null
        ? <p>연속 계산: 기초 {money(result.budget_analysis.raw_base_amount_krw)} → 개인화 {money(result.budget_analysis.raw_personalized_amount_krw)} → 1만원 단위·예산 적용 {money(amount)}</p>
        : baseline!=null&&<p>개인화 전 기준 {money(baseline)} → 현재 선택 {money(amount)}</p>}
      {adjustments.map((item,index)=><p key={index}>관계 반영: {item.reason}</p>)}
      {!adjustments.length&&<p>추가 관계 금액 조정 없음 · 기존 기록 및 적격 근거 기준으로 선택</p>}
      {comparison.referenceOnly&&<p>법률 확인 전 비교 참고액이며 송금 가능 여부를 뜻하지 않습니다.</p>}
    </div>}
  </details>
}
