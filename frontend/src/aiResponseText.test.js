import test from 'node:test'
import assert from 'node:assert/strict'
import {extractAIInterpretation, extractAILead, visibleAIMessage} from './aiResponseText.js'

test('법률 안내와 계산 서두를 제외하고 실제 AI 해석만 보여 준다',()=>{
  const message='법률 확인 전 일반 비교 참고액은 70,000원입니다. 법적 송금 가능 여부는 별도로 확인해야 합니다.\n\nAI 해석: 식사 예정이라면 과거 이력과 예산을 함께 고려합니다.'
  assert.equal(extractAIInterpretation(message),'AI 해석: 식사 예정이라면 과거 이력과 예산을 함께 고려합니다.')
})

test('AI 해석이 없는 서버 안내에서는 해석을 만들어 내지 않는다',()=>{
  assert.equal(extractAIInterpretation('법적 송금 가능 여부는 별도로 확인해야 합니다.'),'')
  assert.equal(extractAIInterpretation(null),'')
})

test('해석만 있는 메시지와 여러 해석 경계를 처리한다',()=>{
  assert.equal(extractAIInterpretation('AI 해석: 관계를 고려합니다.'),'AI 해석: 관계를 고려합니다.')
  assert.equal(extractAIInterpretation('초기 결과\n\nAI 해석: 예전 설명\n\nAI 해석: 최신 설명'),'AI 해석: 최신 설명')
})

test('금액 분석 카드가 있어도 서버의 앞부분 설명을 보존한다',()=>{
  const message='예산 50,000원과 법률 확인 안내를 함께 드립니다.\n\nAI 해석: 조문 예절도 안내합니다.'
  assert.equal(extractAILead(message),'예산 50,000원과 법률 확인 안내를 함께 드립니다.')
  assert.equal(extractAIInterpretation(message),'AI 해석: 조문 예절도 안내합니다.')
  assert.equal(extractAILead('AI 해석: 조문 예절을 안내합니다.'),'')
  assert.equal(extractAILead('예산을 알려 주세요.'),'예산을 알려 주세요.')
})

test('현금 추천액이 없을 때도 현금·선물 상담 답변이 누락되지 않는다',()=>{
  const message='예산 1,111원에는 현금 후보가 없습니다.\n\nAI 해석: 현금 대신 카드와 작은 선물을 고려해 보세요.'
  assert.equal(visibleAIMessage(message,null),message)
  assert.equal(visibleAIMessage(message,undefined),message)
  assert.equal(visibleAIMessage(message,50000),'예산 1,111원에는 현금 후보가 없습니다.')
})
