// 실제 AI 응답을 사전에 정해진 금액 없이 계약·근거 기준으로 검사한다.
const legalCases = new Set(['legal_recipient', 'legal_sender'])
const requiredSignals = {
  reciprocity_up: 'reciprocity',
  recent_large: 'recent_large_gift',
  relationship_drift: 'relationship_drift',
  closeness_rise: 'closeness',
}

export function evaluateScenario(item, entry) {
  const failures = []
  const reviews = []
  const result = entry?.result

  if (entry?.error) return {status:'FAIL', reasons:['API 호출 실패: ' + entry.error]}
  if (!result) return {status:'FAIL', reasons:['AI 응답이 없습니다.']}
  if (result.status === 'need_more_info') {
    return {status:'REVIEW', reasons:['추가 입력 필요: ' + (result.pending_field || '미확인')]}
  }
  if (result.status !== 'answer') {
    return {status:'FAIL', reasons:['예상하지 못한 응답 상태: ' + String(result.status)]}
  }
  if (result.context?.person_id !== item.person_id) {
    failures.push('질문 대상과 선택된 인물이 다릅니다.')
  }
  const evidence = Array.isArray(result.evidence) ? result.evidence : []
  if (!evidence.some(row=>row.kind==='지인' && row.id===item.person_id)) {
    failures.push('선택 인물의 근거가 누락됐습니다.')
  }

  const amount = result.suggested_amount_krw
  const legal = legalCases.has(item.focus)
  if (legal) {
    if (amount != null) failures.push('직무 위험 사례에서 행동 금액이 제시됐습니다.')
    if (result.v4_analysis?.status === 'RECOMMENDED') failures.push('직무 위험 사례가 일반 추천으로 통과했습니다.')
  } else {
    if (!Number.isSafeInteger(amount) || amount <= 0) failures.push('구체적인 금액 추천이 없습니다.')
    if (amount != null && amount > item.budget_krw) failures.push('예산 상한을 초과했습니다.')
  }

  if (amount != null && (!result.v4_analysis || result.v4_analysis.amount_krw !== amount)) {
    failures.push('추천 엔진 금액과 응답 금액이 다릅니다.')
  }
  const hasRecords = evidence.some(row=>row.kind==='개인 거래')
  if (hasRecords && (!result.history_stats?.paid || !result.history_stats?.received)) {
    reviews.push('지급·수령 평균과 중앙값 통계가 누락됐습니다.')
  }
  if (['recent_large','outlier','recent_paid'].includes(item.focus)) {
    const direction = item.focus==='recent_paid' ? 'paid' : 'received'
    if (result.history_stats && !result.history_stats[direction]?.recent_spike) {
      reviews.push('최근 금액 급증을 통계 근거에서 확인하지 못했습니다.')
    }
  }
  const expectedSignal = requiredSignals[item.focus]
  if (expectedSignal && !result.v4_analysis?.relationship_adjustments?.some(row=>row.signal===expectedSignal)) {
    reviews.push('관계 변화 신호가 조정 근거에 나타나지 않았습니다: ' + expectedSignal)
  }
  if (!legal && !result.model) reviews.push('응답 생성 LLM이 완료되지 않았습니다.')
  if (evidence.length === 0) reviews.push('응답 근거가 없습니다.')

  return {
    status: failures.length ? 'FAIL' : reviews.length ? 'REVIEW' : 'PASS',
    reasons: [...failures, ...reviews],
  }
}

export function summarizeScenarios(items, results) {
  return items.reduce((counts, item) => {
    if (results[item.id]) counts[evaluateScenario(item, results[item.id]).status]++
    return counts
  }, {PASS:0, REVIEW:0, FAIL:0})
}
