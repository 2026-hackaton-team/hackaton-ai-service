export function aiAnalysisStatusLabel(status, model) {
  if (status === 'generated') return model
    ? '실제 AI 해석 완료 · 사용 모델: ' + model
    : '실제 AI 해석 완료 · 모델 정보 미확인'
  if (status === 'not_configured') return '실제 AI 해석 미실행 · API 키 미설정 (규칙 기반 분석만 표시)'
  if (status === 'unavailable') return '실제 AI 해석 미실행 · 모델 호출 또는 검증 실패 (규칙 기반 분석만 표시)'
  if (status === 'not_requested') return 'AI 해석 미요청 · 규칙 기반 정책·계산 결과만 표시'
  return 'AI 실행 상태 미확인 · 규칙 기반 분석만 표시'
}
