import React, {useEffect, useRef, useState} from 'react'
import {Icon} from './ui.jsx'
export async function demoApi(path,{userId,method='GET',body,signal}={}) {
  const response=await fetch('/api'+path,{method,signal,headers:{...(userId?{'X-Demo-User-Id':userId}:{}),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})})
  const result=await response.json().catch(()=>({}))
  if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'서버 요청에 실패했습니다.')
  return result
}
const stored=()=>sessionStorage.getItem('rag-demo-user')||''
export default function IntegratedAIPage({initialNoticeId='',embedded=false}) {
  const [view,setView]=useState('chat')
  const [users,setUsers]=useState([])
  const [scenarioExamples,setScenarioExamples]=useState([])
  const [userId,setUserId]=useState(stored)
  const [cid,setCid]=useState('')
  const [conversations,setConversations]=useState([])
  const [messages,setMessages]=useState([])
  const [question,setQuestion]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const controller=useRef(null)
  const bottom=useRef(null)
  useEffect(()=>{demoApi('/demo/users').then(r=>setUsers(r.items||[])).catch(e=>setError(e.message))},[])
  useEffect(()=>{
    controller.current?.abort()
    setMessages([]);setCid('');setConversations([]);setError('')
    if(!userId){setScenarioExamples([]);return}
    sessionStorage.setItem('rag-demo-user',userId)
    demoApi('/conversations',{userId}).then(r=>setConversations(r.items||[])).catch(e=>setError(e.message))
    demoApi('/demo/v4-scenarios',{userId}).then(r=>setScenarioExamples(r.items||[])).catch(e=>setError(e.message))
  },[userId])
  useEffect(()=>{bottom.current?.scrollIntoView({block:'end',behavior:'smooth'})},[messages])
  async function openConversation(id) {
    if(!userId||busy)return
    try{const r=await demoApi('/conversations/'+encodeURIComponent(id),{userId});setCid(id);setMessages(r.messages||[]);setError('')}
    catch(e){setError(e.message)}
  }
  function newConversation(){if(busy)return;setCid('');setMessages([]);setError('')}
  async function send(text, selection=null){
    const prompt=String(text||'').trim()
    if(!prompt||!userId||busy)return
    setBusy(true);setError('')
    const ac=new AbortController();controller.current=ac
    try {
      let current=cid
      if(!current){
        const r=await demoApi('/conversations',{userId,method:'POST',signal:ac.signal})
        current=r.id;setCid(current);setConversations(prev=>[{id:current,created_at:r.createdAt},...prev])
      }
      const response=await demoApi('/conversations/'+encodeURIComponent(current)+'/messages',{
        userId,method:'POST',signal:ac.signal,
        body:{requestId:crypto.randomUUID(),text:prompt,selection}
      })
      setMessages(prev=>[...prev,{role:'user',body:prompt},{role:'assistant',body:response.message,result:response}])
      setQuestion('')
    } catch(e){if(e.name!=='AbortError')setError(e.message)}
    finally{setBusy(false);controller.current=null}
  }
  const latest=messages.at(-1)?.role==='assistant'?messages.at(-1).result:null
  const options=latest?.status==='need_more_info' ? latest.options||[] : []
  return <div className={'ai-page '+(embedded?'home-ai':'')}>
    <div style={{display:'flex',gap:12,marginBottom:16}}><button type='button' className='button' aria-pressed={view==='chat'} onClick={()=>setView('chat')}>AI 자유 상담</button><button type='button' className='button' aria-pressed={view==='risk'} onClick={()=>setView('risk')}>v4 직무·법적 위험 분석</button></div>
    {view==='risk' ? <section className='card' aria-label='온마음 v4 직무분석' style={{padding:0,overflow:'hidden'}}><iframe title='온마음 v4 양방향 직무관계 분석 및 RAG 추천' src='/v4/' style={{display:'block',border:0,width:'100%',height:'1300px'}}/></section> : <>
    <div className="page-heading"><div><h1>내 기록을 아는, 마음 AI</h1><p>RAG 데이터 기반 가상 시연 · 입력 내용은 계정별로 서버에 저장됩니다.</p></div></div>
    <section className="card ai-chat-card">
      <div className="ai-chat-header"><span className="ai-chat-brand"><Icon name="Sparkles" size={19}/><strong>함께 고민하는 마음 AI</strong></span>
        <label>가상 계정 <select className="input" aria-label="가상 계정" value={userId} onChange={e=>setUserId(e.target.value)}>
          <option value="">계정 선택</option>{users.map(u=><option key={u.id} value={u.id}>{u.name} · {u.affiliation||u.id}</option>)}
        </select></label>
        <button className="button" type="button" disabled={!userId||busy} onClick={newConversation}>새 대화</button>
      </div>
      <div style={{display:'flex',gap:8,overflowX:'auto',padding:12}}>
        {conversations.map(c=><button key={c.id} type="button" className="text-button" onClick={()=>openConversation(c.id)} disabled={busy} aria-pressed={cid===c.id}>{new Date(c.updated_at||c.created_at).toLocaleString('ko-KR')}</button>)}
      </div>
      <div className="ai-conversation" aria-busy={busy}>
        <div className="ai-assistant-message"><span className="ai-assistant-avatar"><Icon name="Sparkles" size={17}/></span><div className="ai-assistant-content"><h3>어떤 경조사 고민이 있으세요?</h3><p>인맥을 먼저 선택하지 않아도 됩니다. 필요한 사항은 AI가 추가로 물어봅니다.</p></div></div>
        {scenarioExamples.length>0&&!messages.length&&<div className="ai-suggestion-chips" aria-label="가상 분석 시연 선택">
          {scenarioExamples.map(example=><button type="button" key={example.id} disabled={busy} onClick={()=>send(example.question)} title={example.question}>{example.title}</button>)}
        </div>}
        {messages.map((m,i)=><div key={i} className={m.role==='user'?'ai-user-message':'ai-assistant-message'}>
          <div className={m.role==='user'?'':'ai-assistant-content'}>
            <p style={{whiteSpace:'pre-wrap'}}>{m.body}</p>
            {m.role==='assistant'&&m.result?.v4_analysis&&<div className="ai-evidence">
              <p><strong>v4 분석: {m.result.v4_analysis.status}</strong></p>
              {m.result.v4_analysis.amount_krw!=null
                ? <p>예산 안의 참고 금액: <strong>{m.result.v4_analysis.amount_krw.toLocaleString('ko-KR')}원</strong></p>
                : <p>송금 추천 금액: 보류</p>}
              {m.result.v4_analysis.legal_assessment?.reason&&<p>{m.result.v4_analysis.legal_assessment.reason}</p>}
              {m.result.v4_analysis.missing_questions?.map((item,j)=><p key={j}>추가 확인: {item}</p>)}
              <small>시연용 합성 정보·공개 근거를 활용한 참고 분석이며 법률 자문이 아닙니다.</small>
            </div>}
            {m.role==='assistant'&&!m.result?.v4_analysis&&m.result?.suggested_amount_krw!=null&&<p><strong>참고 금액: {m.result.suggested_amount_krw.toLocaleString('ko-KR')}원</strong></p>}
            {m.role==='assistant'&&Array.isArray(m.result?.evidence)&&m.result.evidence.length>0&&<details><summary>근거 보기</summary>{m.result.evidence.map((e,j)=><p key={j}>{e.kind}: {e.text}</p>)}</details>}
          </div>
        </div>)}
        {options.length>0&&<div style={{display:'flex',flexWrap:'wrap',gap:8,padding:12}}>
          {options.map((item,i)=><button className="button" key={i} disabled={busy} onClick={()=>send(item.reply||item.name||item.title||item.label||item.id,
            item.reply?null:{field:latest.pending_field,value:item.id||item.value})}>{item.label||item.name||item.title||item.id}</button>)}
          {latest.allow_unknown&&<button className="button" disabled={busy} onClick={()=>send('잘 모르겠어요')}>잘 모르겠어요</button>}
        </div>}
        <div ref={bottom}/>
      </div>
      {error&&<div role="alert" className="ai-request-error">{error}<button type="button" className="text-button" onClick={()=>setError('')}>닫기</button></div>}
      <div className="ai-composer-wrap"><form className="ai-composer" onSubmit={e=>{e.preventDefault();send(question)}}>
        <Icon name="Sparkles" size={18}/><input aria-label="마음 AI 질문" value={question} onChange={e=>setQuestion(e.target.value)}
          placeholder="예: 친구 결혼식인데 예산은 3만원이야" maxLength={2000}/>
        <button type="submit" aria-label="질문 보내기" disabled={!userId||busy||!question.trim()}><Icon name="ArrowUp" size={19}/></button>
        {busy&&<button type="button" aria-label="중단" onClick={()=>controller.current?.abort()}><Icon name="X" size={17}/></button>}
      </form><p className="ai-disclaimer">가상 계정을 사용하는 로컬 시연입니다. 법적 적법성이나 금액을 확정하지 않습니다.</p></div>
    </section></>}
  </div>
}
