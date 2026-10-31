import React, {useEffect, useRef, useState} from 'react'
import {Icon} from './ui.jsx'
import BudgetComparison from './BudgetComparison.jsx'
import {extractAIInterpretation} from './aiResponseText.js'
import { demoApi } from './services/demoApi.js'
export { demoApi } from './services/demoApi.js'
const QUICK_QUESTIONS = [
  '친구 결혼식인데 축의금은 얼마가 적당할까?',
  '회사 동료 부친상, 조의금과 조문 예절이 궁금해',
  '거래처 담당자 결혼식, 청탁금지법상 괜찮을까?',
  '조카 돌잔치에 현금과 선물 중 뭐가 좋을까?',
]
// 서버가 꺼져 있을 때 나오는 기술적인 오류를 사용자가 이해할 수 있는 문장으로 바꾼다.
const friendlyError = error => /Failed to fetch|NetworkError|Load failed|서버 요청에 실패/.test(String(error?.message || error))
  ? 'AI 서버에 연결할 수 없어요. 서버가 켜져 있는지 확인한 뒤 다시 시도해 주세요.'
  : String(error?.message || error)
export default function IntegratedAIPage({initialNoticeId='',embedded=false,userId=''}) {
  const [scenarioExamples,setScenarioExamples]=useState([])
  const [cid,setCid]=useState('')
  const [messages,setMessages]=useState([])
  const [question,setQuestion]=useState('')
  const [busy,setBusy]=useState(false)
  const [pendingQuestion,setPendingQuestion]=useState('')
  const [error,setError]=useState('')
  const controller=useRef(null)
  const bottom=useRef(null)
  const activeUser=useRef(userId)
  activeUser.current=userId
  useEffect(()=>()=>controller.current?.abort(),[])
  useEffect(()=>{
    controller.current?.abort()
    setMessages([]);setCid('');setScenarioExamples([]);setError('');setPendingQuestion('')
    if(!userId)return
    const ac=new AbortController()
    demoApi('/demo/v4-scenarios',{userId,signal:ac.signal}).then(r=>{if(!ac.signal.aborted)setScenarioExamples(r.items||[])}).catch(e=>{if(e.name!=='AbortError')setError(friendlyError(e))})
    return ()=>ac.abort()
  },[userId])
  useEffect(()=>{bottom.current?.scrollIntoView({block:'end',behavior:'smooth'})},[messages])
  function newConversation(){if(busy)return;setCid('');setMessages([]);setError('')}
  async function send(text, selection=null){
    const prompt=String(text||'').trim()
    if(!prompt||!userId||busy)return
    setBusy(true);setPendingQuestion(prompt);setError('')
    const ac=new AbortController();controller.current=ac
    try {
      let current=cid
      if(!current){
        const r=await demoApi('/conversations',{userId,method:'POST',signal:ac.signal})
        if(ac.signal.aborted||activeUser.current!==userId)return
        current=r.id;setCid(current)
      }
      const response=await demoApi('/conversations/'+encodeURIComponent(current)+'/messages',{
        userId,method:'POST',signal:ac.signal,
        body:{requestId:crypto.randomUUID(),text:prompt,selection}
      })
      if(ac.signal.aborted||activeUser.current!==userId)return
      setMessages(prev=>[...prev,{role:'user',body:prompt},{role:'assistant',body:response.message,result:response}])
      setQuestion('')
    } catch(e){if(e.name!=='AbortError'&&activeUser.current===userId)setError(friendlyError(e))}
    finally{setBusy(false);setPendingQuestion('');controller.current=null}
  }
  const latest=messages.at(-1)?.role==='assistant'?messages.at(-1).result:null
  const options=latest?.status==='need_more_info' ? latest.options||[] : []
  return <div className={'ai-page '+(embedded?'home-ai':'')}>
    <div className="page-heading"><div><h1>마음결 AI</h1></div></div>
    <section className="card ai-chat-card">
      <div className="ai-chat-header"><span className="ai-chat-brand"><Icon name="Sparkles" size={19}/><strong>함께 고민하는 마음결 AI</strong></span>
        <button className="button" type="button" disabled={!userId||busy} onClick={newConversation}>새 대화</button>
      </div>
      <div className="ai-conversation" aria-busy={busy}>
        <div className="ai-assistant-message"><span className="ai-assistant-avatar"><Icon name="Sparkles" size={17}/></span><div className="ai-assistant-content"><h3>어떤 경조사 고민이 있으세요?</h3><p>인맥을 먼저 선택하지 않아도 됩니다. 필요한 사항은 AI가 추가로 물어봅니다.</p></div></div>
        {scenarioExamples.length>0&&!messages.length&&!busy&&<div aria-label="분석 예시 선택" style={{padding:12}}>
          {[{category:'safety',title:'법률·직무 10개'},{category:'relationship',title:'감정·관계 10개'}].map(group=>
            <details key={group.category} open={group.category==='relationship'}>
              <summary>{group.title}</summary>
              <div className="ai-suggestion-chips">
                {scenarioExamples.filter(example=>(example.category||'safety')===group.category).map(example=>
                  <button type="button" key={example.id} disabled={busy} onClick={()=>send(example.question)} title={example.question}>{example.title}</button>)}
              </div>
            </details>)}
        </div>}
        {scenarioExamples.length===0&&!messages.length&&!busy&&<div className="ai-quick-questions" aria-label="예시 질문">
          {!userId&&<p className="ai-quick-hint">로그인하면 내 서버 기록을 바탕으로 답해 드려요.</p>}
          <div className="ai-suggestion-chips">{QUICK_QUESTIONS.map(item=><button type="button" key={item} disabled={!userId||busy} onClick={()=>send(item)}>{item}</button>)}</div>
        </div>}
        {messages.map((m,i)=><div key={i} className={m.role==='user'?'ai-user-message':'ai-assistant-message'}>
          <div className={m.role==='user'?'ai-user-bubble':'ai-assistant-content ai-answer-bubble'}>
            {m.role==='assistant'&&m.result?.v4_analysis?.amount_krw!=null&&extractAIInterpretation(m.body)&&
              <section className="ai-result-card" aria-label="AI 해석">
                <p className="ai-interpretation">{extractAIInterpretation(m.body)}</p>
              </section>}
            {m.role==='assistant'&&m.result?.v4_analysis?.amount_krw!=null&&
              <section className="ai-result-card" aria-label="추천 참고 금액">
                <p className="ai-recommended-amount">{m.result.v4_analysis.status==='NEEDS_FACTS'?'법률 확인 전 비교 참고액':'추천 참고액'}: {m.result.v4_analysis.amount_krw.toLocaleString('ko-KR')}원</p>
              </section>}
            {m.role==='assistant'&&!m.result?.v4_analysis&&m.result?.suggested_amount_krw!=null&&
              <section className="ai-result-card" aria-label="추천 참고 금액">
                <p className="ai-recommended-amount">참고 금액: {m.result.suggested_amount_krw.toLocaleString('ko-KR')}원</p>
              </section>}
            {(m.role==='user'||m.result?.v4_analysis?.amount_krw==null)&&<p style={{whiteSpace:'pre-wrap'}}>{m.body}</p>}
            {m.role==='assistant'&&m.result?.budget_analysis&&<BudgetComparison result={m.result} compact/>}
          </div>
        </div>)}
        {options.length>0&&<div style={{display:'flex',flexWrap:'wrap',gap:8,padding:12}}>
          {options.map((item,i)=><button className="button" key={i} disabled={busy} onClick={()=>send(item.reply||item.name||item.title||item.label||item.id,
            item.reply?null:{field:latest.pending_field,value:item.id||item.value})}>{item.label||item.name||item.title||item.id}</button>)}
          {latest.allow_unknown&&<button className="button" disabled={busy} onClick={()=>send('잘 모르겠어요')}>잘 모르겠어요</button>}
        </div>}
        {busy&&<><div className="ai-user-message"><div className="ai-user-bubble"><p style={{whiteSpace:'pre-wrap'}}>{pendingQuestion}</p></div></div>
          <div className="ai-waiting" role="status" aria-live="polite"><Icon name="Sparkles" size={16}/> 답변 생성 중이에요. 잠시 후 결과가 표시됩니다.</div></>}
        <div ref={bottom}/>
      </div>
      {error&&<div role="alert" className="ai-request-error">{error}<button type="button" className="text-button" onClick={()=>setError('')}>닫기</button></div>}
      <div className="ai-composer-wrap"><form className="ai-composer" onSubmit={e=>{e.preventDefault();send(question)}}>
        <Icon name="Sparkles" size={18}/><input aria-label="마음결 AI 질문" value={question} onChange={e=>setQuestion(e.target.value)}
          disabled={!userId||busy} placeholder={userId?'예: 친구 결혼식인데 예산은 3만원이야':'로그인 후 AI 상담을 이용할 수 있어요'} maxLength={2000}/>
        <button type="submit" aria-label="질문 보내기" disabled={!userId||busy||!question.trim()}><Icon name="ArrowUp" size={19}/></button>
        {busy&&<button type="button" aria-label="중단" onClick={()=>controller.current?.abort()}><Icon name="X" size={17}/></button>}
      </form>{!userId&&<p className="ai-login-hint" role="status">상단 계정 메뉴에서 로그인하면 AI 상담을 시작할 수 있어요.</p>}
      <p className="ai-disclaimer">선택한 프로필 기준의 참고 답변이에요. 법적 적법성이나 금액을 확정하지 않습니다.</p></div>
    </section>
  </div>
}
