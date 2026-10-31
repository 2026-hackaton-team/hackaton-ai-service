import test from 'node:test'
import assert from 'node:assert/strict'
import {evaluateScenario, summarizeScenarios} from './scenarioEvaluation.js'

const item={id:'KIM-01',person_id:'KIMP001',focus:'reciprocity_up',budget_krw:120000}
const valid={
  status:'answer',context:{person_id:'KIMP001'},suggested_amount_krw:100000,
  model:'codyssey',evidence:[{kind:'지인',id:'KIMP001',text:'김지훈'}],
  v4_analysis:{status:'NEEDS_FACTS',amount_krw:100000,reference_only:true,
    relationship_adjustments:[{signal:'reciprocity',reason:'수령액 반영'}]},
}

test('정확한 지인·엔진 금액·예산·관계 근거가 있으면 통과한다',()=>{
  assert.deepEqual(evaluateScenario(item,{result:valid}),{status:'PASS',reasons:[]})
})

test('인물 혼동, 예산 초과, 엔진과 출력 금액의 불일치를 실패로 분류한다',()=>{
  const wrong={...valid,context:{person_id:'KIMP002'},suggested_amount_krw:150000}
  const checked=evaluateScenario(item,{result:wrong})
  assert.equal(checked.status,'FAIL')
  assert.equal(checked.reasons.some(value=>value.includes('인물')),true)
  assert.equal(checked.reasons.some(value=>value.includes('예산')),true)
  assert.equal(checked.reasons.some(value=>value.includes('엔진')),true)
})

test('직무 위험 사례에서는 금액 보류를 확인한다',()=>{
  const caseItem={...item,focus:'legal_sender'}
  const answer={...valid,suggested_amount_krw:null,model:null,
    v4_analysis:{status:'NEEDS_FACTS',amount_krw:null,relationship_adjustments:[]}}
  assert.equal(evaluateScenario(caseItem,{result:answer}).status,'PASS')
  assert.equal(evaluateScenario(caseItem,{result:valid}).status,'FAIL')
})

test('추가 질문, 모델 미완료, 관계 조정 누락은 검토 대상으로 분류한다',()=>{
  assert.equal(evaluateScenario(item,{result:{status:'need_more_info',pending_field:'person_id'}}).status,'REVIEW')
  const review=evaluateScenario(item,{result:{...valid,model:null,v4_analysis:{...valid.v4_analysis,relationship_adjustments:[]}}})
  assert.equal(review.status,'REVIEW')
  assert.equal(review.reasons.length,2)
})

test('API 오류와 누락된 응답은 실패로, 완료 건만 집계한다',()=>{
  assert.equal(evaluateScenario(item,{error:'모델 호출 실패'}).status,'FAIL')
  assert.equal(evaluateScenario(item,{}).status,'FAIL')
  const counts=summarizeScenarios(
    [item,{...item,id:'KIM-02'},{...item,id:'KIM-03'},{...item,id:'KIM-04'}],
    {'KIM-01':{result:valid},'KIM-02':{error:'실패'},'KIM-03':{result:{status:'need_more_info'}}},
  )
  assert.deepEqual(counts,{PASS:1,REVIEW:1,FAIL:1})
})

test('실거래가 있는데 평균/중앙값 통계가 빠지면 재검토한다',()=>{
  const result={...valid,evidence:[...valid.evidence,{kind:'개인 거래',id:'TX1'}]}
  const checked=evaluateScenario(item,{result})
  assert.equal(checked.status,'REVIEW')
  assert.equal(checked.reasons.some(reason=>reason.includes('평균')),true)
})

test('최근 큰 수령과 최근 큰 지급의 급증 신호를 별도로 검사한다',()=>{
  const base={...valid,
    history_stats:{paid:{recent_spike:false},received:{recent_spike:false}},
  }
  const received=evaluateScenario({...item,focus:'outlier'},{result:base})
  assert.equal(received.status,'REVIEW')
  assert.equal(received.reasons.some(reason=>reason.includes('급증')),true)
  const paid=evaluateScenario({...item,focus:'recent_paid'},{result:{
    ...base,history_stats:{paid:{recent_spike:true},received:{recent_spike:false}},
  }})
  assert.equal(paid.status,'PASS')
})
