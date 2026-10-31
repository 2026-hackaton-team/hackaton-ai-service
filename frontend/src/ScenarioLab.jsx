import React, {useEffect, useRef, useState} from 'react'
import {demoApi} from './services/demoApi.js'
import {evaluateScenario, summarizeScenarios} from './scenarioEvaluation.js'

const money = value => value == null ? '보류 또는 미제시' : value.toLocaleString('ko-KR') + '원'

export default function ScenarioLab({userId, onQuestion}) {
  const [cases,setCases] = useState([])
  const [selected,setSelected] = useState('')
  const [results,setResults] = useState({})
  const [running,setRunning] = useState(false)
  const [progress,setProgress] = useState('')
  const [error,setError] = useState('')
  const controller = useRef(null)

  useEffect(()=>{
    const ac=new AbortController()
    demoApi('/demo/kim-scenarios',{userId,signal:ac.signal})
      .then(data=>{if(!ac.signal.aborted){setCases(data.items||[]);setSelected(data.items?.[0]?.id||'')}})
      .catch(err=>{if(!ac.signal.aborted)setError(err.message)})
    return ()=>{ac.abort();controller.current?.abort()}
  },[userId])

  async function run(items) {
    if(running || !items.length)return
    setRunning(true);setError('');setProgress('');setResults({})
    const ac=new AbortController()
    controller.current=ac
    for(let index=0;index<items.length;index++){
      if(ac.signal.aborted)break
      const item=items[index]
      setProgress(`${index+1}/${items.length} · ${item.name}`)
      try{
        // 수동 자유 상담과 동일한 대화 생성/질문 API를 호출한다.
        const created=await demoApi('/conversations',{userId,method:'POST',signal:ac.signal})
        const result=await demoApi('/conversations/'+encodeURIComponent(created.id)+'/messages',{
          userId,method:'POST',signal:ac.signal,
          body:{requestId:crypto.randomUUID(),text:item.question}
        })
        if(ac.signal.aborted)break
        setResults(prev=>({...prev,[item.id]:{result,conversationId:created.id}}))
      }catch(err){
        if(ac.signal.aborted)break
        setResults(prev=>({...prev,[item.id]:{error:err.message}}))
      }
    }
    controller.current=null
    setRunning(false)
    setProgress('')
  }

  const totals=summarizeScenarios(cases,results)
  const completed=Object.keys(results).length
  function downloadReport() {
    const report={
      schemaVersion:1, generatedAt:new Date().toISOString(), userId,
      results:cases.filter(item=>results[item.id]).map(item=>({
        scenarioId:item.id,personId:item.person_id,question:item.question,
        budgetKrw:item.budget_krw,focus:item.focus,
        assessment:evaluateScenario(item,results[item.id]),
        ...results[item.id],
      })),
    }
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}))
    const link=document.createElement('a')
    link.href=url;link.download='kim-scenario-evaluation.json';link.click()
    URL.revokeObjectURL(url)
  }

  return <section className="card" style={{padding:16,marginBottom:16}}> 
    <h2 style={{margin:'0 0 8px'}}>김시나리오 · 실제 AI 추천 검증</h2>
    <p>서버에 등록된 합성 인맥 20명의 질문을 일반 자유 상담 API로 실행합니다. 시나리오별 정답을 출력하지 않으며 실제 모델 호출이 발생합니다.</p>
    <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap',marginBottom:12}}>
      <label htmlFor="kim-persona">가상 관계</label>
      <select className="input" id="kim-persona" aria-label="검증 인물" value={selected} disabled={running} onChange={e=>setSelected(e.target.value)}>
        {cases.map(item=><option key={item.id} value={item.id}>{item.name} · {item.title} ({item.group})</option>)}
      </select>
      <button type="button" className="button" disabled={running||!selected} onClick={()=>run(cases.filter(item=>item.id===selected))}>선택 1건 실행</button>
      <button type="button" className="button" disabled={running||!cases.length} onClick={()=>run(cases)}>전체 {cases.length}건 순차 실행</button>
      {running&&<button type="button" className="button" onClick={()=>controller.current?.abort()}>실행 중단</button>}
      <button type="button" className="text-button" disabled={running||!selected} onClick={()=>onQuestion(cases.find(item=>item.id===selected)?.question||'')}>질문 입력창에 불러오기</button>
    </div>
    {progress&&<p role="status">{progress} 분석 중</p>}
    {completed>0&&<div role="status" style={{display:'flex',gap:12,alignItems:'center',flexWrap:'wrap',marginBottom:12}}>
      <strong>{completed}/{cases.length}건 실행</strong>
      <span>통과 {totals.PASS} · 검토 {totals.REVIEW} · 실패 {totals.FAIL}</span>
      <button type="button" className="button" onClick={downloadReport}>결과 JSON 저장</button>
    </div>}
    {error&&<p role="alert">{error}</p>}
    <p style={{fontSize:12}}>PASS는 입력·엔진·근거 계약 검증이며 금액의 사회적 정답이나 법적 적법성 인증이 아닙니다. REVIEW는 추가 확인이 필요한 사례입니다. 실제 모델이 연결되지 않으면 오류로 기록합니다. 20건 실행에는 모델 사용량이 발생할 수 있습니다.</p>
    {Object.keys(results).length>0&&<div style={{overflowX:'auto'}}>
      <table style={{width:'100%',borderCollapse:'collapse',textAlign:'left'}}>
        <thead><tr><th>인물·상황</th><th>추천액</th><th>평가·엔진/AI</th><th>결과·근거</th></tr></thead>
        <tbody>{cases.filter(item=>results[item.id]).map(item=>{
          const entry=results[item.id], result=entry.result
          const amount=result?.suggested_amount_krw
          const assessment=evaluateScenario(item,entry)
          return <tr key={item.id} style={{borderTop:'1px solid var(--border, #ddd)',verticalAlign:'top'}}>
            <td style={{padding:'8px 6px'}}><strong>{item.name}</strong><p>{item.title}</p><small>예산 {money(item.budget_krw)}</small></td>
            <td style={{padding:'8px 6px'}}><strong>{entry.error?'실패':money(amount)}</strong><p>{result?.status||''}</p></td>
            <td style={{padding:'8px 6px'}}><strong>{assessment.status}</strong>
              {assessment.reasons.map((reason,index)=><p key={index}>{reason}</p>)}
              <p>{result?.v4_analysis?.status||'분석 상태 없음'}</p>
              <small>의도 분류: {result?.classification_model||'미실행'}</small>
              <p><small>응답 생성: {result?.model||'미실행'}</small></p>
            </td>
            <td style={{padding:'8px 6px'}}>
              {entry.error?<span role="alert">{entry.error}</span>:<details>
                <summary>AI 답변과 근거 {result?.evidence?.length||0}건 보기</summary>
                <p style={{whiteSpace:'pre-wrap'}}>{result?.message}</p>
                {result?.v4_analysis?.relationship_adjustments?.map((adj,index)=><p key={index}>관계 조정: {adj.reason}</p>)}
                {result?.evidence?.map((ev,index)=><p key={index}>{ev.kind}: {ev.text}{ev.url&&<> · <a href={ev.url} target="_blank" rel="noopener noreferrer">출처</a></>}</p>)}
                <small>근거 수준: {result?.evidence_level||'미확인'} / 추천 기준: {result?.recommendation_basis||'미확인'}</small>
              </details>}
            </td>
          </tr>
        })}
        </tbody>
      </table>
    </div>}
  </section>
}
