// 예산은 목표액이 아니라 상한이며, 차이와 상한 작용 여부를 구분한다.
export function compareBudget(result, fallbackBudget) {
  if (!result || result.status !== 'answer') return null
  const budget = result?.budget_analysis?.budget_krw ?? result?.context?.budget_krw ?? fallbackBudget
  if (!Number.isSafeInteger(budget) || budget < 0) return null
  const amount = result?.suggested_amount_krw
  if (amount == null) return {
    kind:'withheld', budget, amount:null, gap:null, usagePercent:null,
    title:'추천 금액 보류',
    detail:['NEEDS_EXPERT_REVIEW','POTENTIALLY_PROHIBITED'].includes(result?.v4_analysis?.status)
      ? '법률·직무 관련 확인이 필요해 금액 제안을 보류했습니다.'
      : result?.v4_analysis?.status==='NO_AFFORDABLE_CANDIDATE'||budget<10000
        ? '현재 예산 안에서는 1만원 단위의 현금 추천 후보가 없습니다. 비금전적 대안도 고려해 보세요.'
        : result?.v4_analysis?.status==='NEEDS_FACTS'
          ? '법률·직무 관련 사실 확인 전에는 금액 제안을 확정할 수 없습니다.'
          : '현재 조건에서 추천 금액을 정하지 못했습니다. 추가 정보를 확인해 주세요.',
  }
  if (!Number.isSafeInteger(amount) || amount < 0 || amount > budget) return {
    kind:'over', budget, amount, gap:budget-amount, usagePercent:null,
    title:'예산 초과 또는 잘못된 금액',
    detail:'추천 금액과 서버 예산을 확인해야 합니다.',
  }
  const gap = budget - amount
  const limit = result?.budget_analysis?.budget_limited
  const unrestricted = result?.budget_analysis?.unrestricted_amount_krw
  const title = limit === true ? '예산 제한으로 높은 후보 제외'
    : gap === 0 ? '추천액과 예산이 같음' : '추천 후 예산 여유'
  const detail = limit === true && Number.isSafeInteger(unrestricted)
    ? '예산 제한이 없다면 ' + unrestricted.toLocaleString('ko-KR') + '원 후보였지만, 예산 이하 금액 단계에서 선택했습니다.'
    : limit === false
      ? '예산 제한 없이 계산한 후보도 현재 추천액과 같습니다. 예산을 모두 사용할 필요는 없습니다.'
      : '예산 제한이 실제로 금액을 낮췄는지는 이전 결과만으로 확인할 수 없습니다.'
  return {
    kind:gap>0?'below':'equal', budget, amount, gap,
    usagePercent:budget===0?0:Math.round(amount/budget*100),
    budgetLimited:limit, unrestricted, title, detail,
    baseline:result?.v4_analysis?.baseline_amount_krw ?? null,
    adjustments:result?.v4_analysis?.relationship_adjustments ?? [],
    referenceOnly:result?.budget_analysis?.reference_only ?? result?.v4_analysis?.reference_only ?? false,
  }
}
