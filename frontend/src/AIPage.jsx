import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './ui.jsx';
import { getAdvice } from './domain.js';
import { aiConfig, createAiChat } from './services/aiChat.js';
import './ai-chat-api.css';

const modes = [
  {label:'금액 참고',icon:'HandHeart',description:'지난 기록을 바탕으로'},
  {label:'참석 대응',icon:'CalendarCheck',description:'상황에 맞게 준비해요'},
  {label:'메시지 작성',icon:'MessageCircle',description:'마음을 담은 한마디'},
  {label:'우선순위',icon:'Bookmark',description:'먼저 챙겨야 할 마음'},
];
const config = aiConfig();
const providerLabel = provider => provider === 'openai' ? 'AI 응답' : '모의 응답';
const defaultSuggestions = ['금액을 참고하고 싶어요', '참석하지 못한다면?', '축하·위로 메시지 작성'];

export default function AIPage({people, events, records, today, initialPersonId, notify, embedded = false}) {
  const Heading = embedded ? 'h2' : 'h1';
  const api = useMemo(() => createAiChat({baseUrl:config.baseUrl}), []);
  const [source,setSource] = useState(config.defaultSource);
  const [mode,setMode] = useState('금액 참고');
  const [personId,setPersonId] = useState(initialPersonId || people[0]?.id || '');
  const [question,setQuestion] = useState('');
  const [messages,setMessages] = useState([]);
  const [context,setContext] = useState(null);
  const [connection,setConnection] = useState('loading');
  const [contextError,setContextError] = useState('');
  const [reload,setReload] = useState(0);
  const [busy,setBusy] = useState(false);
  const request = useRef(null);
  const serial = useRef(0);
  const busyRef = useRef(false);
  const end = useRef(null);
  const preferredName = useRef(people.find(item => item.id === initialPersonId)?.name || people[0]?.name || '');
  const server = source === 'server';
  const currentPeople = server ? context?.people || [] : people;
  const person = currentPeople.find(item => item.id === personId);
  const ready = !server || connection === 'ready';
  const canSend = ready && !!person && !busy;
  const initial = server ? null : getAdvice({mode,person,people,events,records,today});

  function invalidate() {
    serial.current++;
    request.current?.controller.abort();
    request.current = null;
    busyRef.current = false;
    setBusy(false);
  }
  useEffect(() => () => { serial.current++; request.current?.controller.abort(); }, []);
  useEffect(() => {
    if (!server) return;
    let active = true;
    const controller = new AbortController();
    setConnection('loading'); setContext(null); setContextError('');
    api.context({signal:controller.signal}).then(result => {
      if (!active) return;
      setContext(result);
      setPersonId(result.people.find(item => item.name === preferredName.current)?.id || result.people[0]?.id || '');
      setConnection('ready');
    }).catch(error => {
      if (!active) return;
      setConnection('error');
      setContextError(error.message || '서버에 연결하지 못했어요.');
    });
    return () => { active = false; controller.abort(); };
  }, [server,reload,api]);
  useEffect(() => {
    if (!server && !people.some(item => item.id === personId)) setPersonId(people[0]?.id || '');
  }, [server,people,personId]);
  useEffect(() => { if (messages.length) end.current?.scrollIntoView({behavior:'smooth',block:'nearest'}); }, [messages,busy]);

  function changeSource(value) {
    preferredName.current = person?.name || '';
    invalidate(); setMessages([]); setSource(value); setQuestion('');
    if (value === 'server') { setContext(null); setConnection('loading'); setContextError(''); }
    if (value === 'local') setPersonId(people.find(item => item.name === preferredName.current)?.id || people[0]?.id || '');
  }
  function changePerson(value) { preferredName.current = currentPeople.find(item => item.id === value)?.name || ''; invalidate(); setMessages([]); setPersonId(value); }
  function stop() {
    const id = request.current?.id;
    invalidate();
    if (id) setMessages(current => current.map(item => item.id === id ? {...item,error:'요청을 취소했어요. 다시 시도할 수 있어요.'} : item));
  }
  async function send(raw, nextMode = mode, retryId = null) {
    const text = raw.trim();
    if (!text || !person || !ready || busyRef.current) return;
    const id = retryId || crypto.randomUUID();
    const token = ++serial.current;
    const controller = new AbortController();
    busyRef.current = true; setBusy(true);
    request.current = {controller,id};
    const update = patch => setMessages(current => current.map(item => item.id === id ? {...item,...patch} : item));
    if (retryId) update({error:'',response:null});
    else setMessages(current => [...current,{id,question:text,mode:nextMode,response:null,error:''}]);
    try {
      const response = server
        ? await api.advice({question:text,mode:nextMode,personId:person.id},{signal:controller.signal})
        : getAdvice({question:text,mode:nextMode,person,people,events,records,today});
      if (serial.current !== token) return;
      update({response,error:''});
      setQuestion(current => current.trim() === text ? '' : current);
    } catch (error) {
      if (serial.current !== token) return;
      update({error:error.message || '응답을 받지 못했어요. 다시 시도해 주세요.'});
    } finally {
      if (serial.current === token) { request.current = null; busyRef.current = false; setBusy(false); }
    }
  }
  function chooseMode(value) {
    if (!canSend) return;
    setMode(value);
    const name = person?.name || '소중한 사람';
    const prompts = {'금액 참고':`${name}님의 경조사 금액을 참고하고 싶어요`,'참석 대응':`${name}님의 경조사 참석 대응을 알려 주세요`,'메시지 작성':`${name}님께 보낼 메시지를 작성해 주세요`,'우선순위':'가장 먼저 챙길 경조사를 알려 주세요'};
    send(prompts[value],value);
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); notify('메시지를 복사했어요. 마음을 조금 더 담아 전해 보세요.'); }
    catch { notify('복사를 지원하지 않는 환경이에요. 문구를 선택해 복사해 주세요.'); }
  }
  const suggestions = [...messages].reverse().find(message => message.response)?.response.suggestions || initial?.suggestions || defaultSuggestions;

  return <div className={`ai-page ${embedded ? 'home-ai' : ''}`}>
    <div className="page-heading"><div><Heading>{embedded ? '마음결 AI와 바로 이야기해요' : '내 기록을 아는, 마음결 AI'}</Heading></div></div>
    <section className="card ai-chat-card">
      <div className="ai-chat-header">
        <span className="ai-chat-brand"><Icon name="Sparkles" size={19}/><strong>함께 고민하는 마음결 AI</strong></span>
        <div className="ai-chat-selectors">
          <label className="ai-source-selector"><span>참고 데이터</span><select className="input" aria-label="AI 참고 데이터" value={source} onChange={e => changeSource(e.target.value)}><option value="local">브라우저 기록 체험</option><option value="server" disabled={!config.serverAvailable}>서버 가상데이터{!config.serverAvailable ? ' · PC 실행 시 사용' : ''}</option></select></label>
          <label className="ai-person-selector"><span>누구에게 전할까요?</span><select className="input" aria-label="AI 참고 인맥" value={personId} disabled={!ready || !currentPeople.length} onChange={e => changePerson(e.target.value)}>{!currentPeople.length && <option value="">{server ? (connection === 'loading' ? '가상 인맥을 불러오는 중' : '가상 인맥 없음') : '인맥을 등록해 주세요'}</option>}{currentPeople.map(item => <option key={item.id} value={item.id}>{item.name} · {item.relation}</option>)}</select></label>
        </div>
      </div>
      {server && <div className={`ai-server-status ${connection === 'error' ? 'has-error' : ''}`}>
        {connection === 'loading' ? <span role="status">서버의 가상 인맥과 기록을 확인하고 있어요…</span> : connection === 'error' ? <><span role="alert">{contextError} FastAPI 서버 실행 상태를 확인해 주세요.</span><button className="text-button" onClick={() => setReload(value => value + 1)}>다시 연결<Icon name="RefreshCw" size={13}/></button></> : <span role="status"><strong>{providerLabel(context?.provider)}</strong> · 선택한 가상 인맥의 서버 기록을 참고합니다. 브라우저 장부는 전송하지 않아요.</span>}
      </div>}
      <div className="ai-conversation" aria-busy={busy}>
        <div className="ai-assistant-message ai-service-intro"><span className="ai-assistant-avatar"><Icon name="Sparkles" size={17}/></span><div className="ai-assistant-content"><div className="ai-assistant-name">마음결 AI</div><h3>어떤 마음을 전하고 싶으세요?</h3><p>필요한 도움을 선택하거나 편하게 질문해 주세요.</p><div className="ai-service-options" aria-label="대화 도움 선택">{modes.map(item => <button type="button" key={item.label} className="ai-service-option" disabled={!canSend} onClick={() => chooseMode(item.label)}><span className="ai-service-icon"><Icon name={item.icon} size={19}/></span><span><strong>{item.label}</strong><small>{item.description}</small></span><Icon name="ChevronRight" size={15}/></button>)}</div></div></div>
        {messages.map(message => <React.Fragment key={message.id}><div className="ai-user-message"><span>{message.question}</span></div>{message.response ? <AdviceMessage advice={message.response} onCopy={copy} compact={embedded}/> : message.error ? <div className="ai-request-error" role="alert"><Icon name="CircleAlert" size={17}/><div><p>{message.error}</p><button className="text-button" disabled={!canSend} onClick={() => send(message.question,message.mode,message.id)}>다시 시도<Icon name="RefreshCw" size={13}/></button></div></div> : <div className="ai-waiting" role="status"><Icon name="Sparkles" size={16}/>기록을 살펴보고 있어요…</div>}</React.Fragment>)}
        <div ref={end}/>
      </div>
      <div className="ai-composer-wrap"><div className="ai-suggestion-chips">{suggestions.map(text => <button key={text} disabled={!canSend} onClick={() => send(text)}>{text}<Icon name="Plus" size={12}/></button>)}</div>
        <form className="ai-composer" onSubmit={e => {e.preventDefault();send(question);}}><Icon name="Sparkles" size={18}/><input aria-label="마음결 AI 질문" placeholder={`예: ${person?.name || '선택한 인맥'} 경조사에 참석하지 못하면?`} value={question} onChange={e => setQuestion(e.target.value)} maxLength={1000}/>{busy ? <button aria-label="응답 중지" type="button" onClick={event => { event.preventDefault(); stop(); }}><Icon name="X" size={18}/></button> : <button aria-label="질문 보내기" type="submit" disabled={!canSend || !question.trim()}><Icon name="ArrowUp" size={19}/></button>}</form>
        <p className="ai-disclaimer"><Icon name="ShieldCheck" size={12}/>{server ? '가상 기록을 참고한 제안이에요.' : '등록된 기록으로 만든 체험용 제안이에요.'} 금액과 참석은 내 상황에 맞게 결정해 주세요.</p>
      </div>
    </section>
    <div className="ai-privacy-note"><Icon name="LockKeyhole" size={14}/>{!server ? '브라우저 기록으로 답변하며, 질문과 기록을 외부로 전송하지 않아요.' : context?.provider === 'openai' ? '질문과 선택한 가상 인맥의 참고 기록을 AI 서비스에 전달합니다. 실제 장부는 전달하지 않아요.' : '질문은 모의 서버로 전송됩니다. 모의 응답은 외부 AI 호출 없이 만들어져요.'}</div>
  </div>;
}

function AdviceMessage({advice,onCopy,compact=false}) {
  return <div className="ai-assistant-message"><span className="ai-assistant-avatar"><Icon name="Sparkles" size={17}/></span><div className="ai-assistant-content"><div className="ai-assistant-name">마음결 AI<span>{advice.provider ? `${providerLabel(advice.provider)} · 가상 기록` : '내 기록 참고'}</span></div><h3>{advice.title}</h3>{advice.amount && <div className="ai-amount"><strong>{(advice.amount/10000).toLocaleString('ko-KR')}</strong>만 원<span>기록에서 찾은 참고 금액</span></div>}<p className={advice.isMessage ? 'generated-message' : ''}>{advice.text}</p>{advice.isMessage && <button className="text-button copy-message" onClick={() => onCopy(advice.text)}><Icon name="Copy" size={14}/>메시지 복사</button>}{advice.evidence.length>0 && <details className="ai-evidence" open={!compact}><summary><Icon name="NotebookPen" size={15}/>참고한 기록과 관계<Icon name="ChevronDown" size={14}/></summary><div>{advice.evidence.map((item,index) => <div key={`${item.label}-${index}`}><span>{item.label}</span><strong>{item.value}</strong></div>)}</div></details>}</div></div>;
}
