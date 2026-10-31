import React from 'react'
import {compareBudget} from './budgetComparison.js'

const money = amount => amount.toLocaleString('ko-KR') + '원'

export default function BudgetComparison({result, budget, compact=false}) {
  const comparison=compareBudget(result,budget)
  if(!comparison)return null
  const {amount,gap,baseline,adjustments}=comparison
  return <section aria-label="추천 금액과 예산 비교" style={{margin:'8px 0',padding:10,border:'1px solid var(--border, #ddd)',borderRadius:8}}>
    <strong>{comparison.title}</strong>
    {amount == null
      ? <p>예산 {money(comparison.budget)} · 금액 제안 보류</p>
      : <p>예산 {money(comparison.budget)} → {comparison.referenceOnly?'비교 참고액':'추천액'} {money(amount)} · {gap>0?'잔여 '+money(gap):'예산과 동일'} ({comparison.usagePercent}% 사용)</p>}
    <p style={{fontSize:12}}>{comparison.detail}</p>
    {!compact&&amount!=null&&<div style={{fontSize:12}}>
      {result?.budget_analysis?.raw_base_amount_krw!=null&&result?.budget_analysis?.raw_personalized_amount_krw!=null
        ? <p>연속 계산: 기초 {money(result.budget_analysis.raw_base_amount_krw)} → 개인화 {money(result.budget_analysis.raw_personalized_amount_krw)} → 1만원 단위·예산 적용 {money(amount)}</p>
        : baseline!=null&&<p>개인화 전 기준 {money(baseline)} → 현재 선택 {money(amount)}</p>}
      {adjustments.map((item,index)=><p key={index}>관계 반영: {item.reason}</p>)}
      {!adjustments.length&&<p>추가 관계 금액 조정 없음 · 기존 기록 및 적격 근거 기준으로 선택</p>}
      {comparison.referenceOnly&&<p>법률 확인 전 비교 참고액이며 송금 가능 여부를 뜻하지 않습니다.</p>}
    </div>}
  </section>
}
