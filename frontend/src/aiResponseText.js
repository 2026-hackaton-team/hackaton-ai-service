// 실제 AI 해석이 생성된 경우에만 서두의 서버 계산 안내와 분리해 표시한다.
export function extractAIInterpretation(message) {
  const text=String(message||'')
  const marker='\n\nAI 해석: '
  const index=text.lastIndexOf(marker)
  if(index>=0)return text.slice(index+2).trim()
  return text.startsWith('AI 해석: ') ? text.trim() : ''
}

export function extractAILead(message) {
  const text=String(message||'')
  const index=text.lastIndexOf('\n\nAI 해석: ')
  if(index>=0)return text.slice(0,index).trim()
  return text.startsWith('AI 해석: ') ? '' : text
}

export function visibleAIMessage(message, amount) {
  return amount == null ? String(message||'') : extractAILead(message)
}
