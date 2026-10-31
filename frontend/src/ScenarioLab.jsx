import React, {useEffect, useRef, useState} from 'react'
import {demoApi} from './services/demoApi.js'

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
    setRunning(true);setError('');setProgress('')
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
    {error&&<p role="alert">{error}</p>}
    <p style={{fontSize:12}}>실제 AI 설정이 없거나 호출에 실패하면 금액을 만들어 표시하지 않고 오류를 기록합니다. 20건 실행은 모델 사용량이 발생할 수 있습니다.</p>
    {Object.keys(results).length>0&&<div style={{overflowX:'auto'}}>
      <table style={{width:'100%',borderCollapse:'collapse',textAlign:'left'}}>
        <thead><tr><th>인물·상황</th><th>추천액</th><th>엔진/AI</th><th>결과·근거</th></tr></thead>
        <tbody>{cases.filter(item=>results[item.id]).map(item=>{
          const entry=results[item.id], result=entry.result
          const amount=result?.suggested_amount_krw
          const capOk=amount==null||amount<=item.budget_krw
          const engineOk=amount==null||!result?.v4_analysis||amount===result.v4_analysis.amount_krw
          return <tr key={item.id} style={{borderTop:'1px solid var(--border, #ddd)',verticalAlign:'top'}}>
            <td style={{padding:'8px 6px'}}><strong>{item.name}</strong><p>{item.title}</p><small>예산 {money(item.budget_krw)}</small></td>
            <td style={{padding:'8px 6px'}}><strong>{entry.error?'실패':money(amount)}</strong><p>{!entry.error&&!capOk?'예산 초과 오류':!entry.error&&!engineOk?'엔진 불일치 오류':result?.status||''}</p></td>
            <td style={{padding:'8px 6px'}}>{entry.error?'호출 실패':result?.v4_analysis?.status||'분석 상태 없음'}<p><small>LLM: {result?.model||'미실행'}</small></p></td>
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
