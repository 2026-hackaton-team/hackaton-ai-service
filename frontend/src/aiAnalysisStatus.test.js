import test from 'node:test'
import assert from 'node:assert/strict'
import { aiAnalysisStatusLabel } from './aiAnalysisStatus.js'

test('성공한 AI 해석은 실제 모델 이름과 함께 표시한다', () => {
  assert.equal(aiAnalysisStatusLabel('generated', 'fixed-model'),
    '실제 AI 해석 완료 · 사용 모델: fixed-model')
  assert.equal(aiAnalysisStatusLabel('generated', null),
    '실제 AI 해석 완료 · 모델 정보 미확인')
})

test('미설정과 호출 실패를 서로 다른 상태로 표시한다', () => {
  assert.match(aiAnalysisStatusLabel('not_configured', null), /API 키 미설정/)
  assert.match(aiAnalysisStatusLabel('unavailable', null), /모델 호출 또는 검증 실패/)
  assert.doesNotMatch(aiAnalysisStatusLabel('unavailable', null), /API 키 미설정/)
})

test('AI 미요청과 기존 대화의 상태 누락을 구분한다', () => {
  assert.match(aiAnalysisStatusLabel('not_requested', null), /미요청/)
  assert.match(aiAnalysisStatusLabel(undefined, null), /상태 미확인/)
  assert.doesNotMatch(aiAnalysisStatusLabel(undefined, null), /API 키 미설정/)
})
