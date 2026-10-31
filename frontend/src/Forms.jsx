import { useEffect, useState } from 'react'
import { Modal, Icon } from './ui.jsx'
import { RELATION_OPTIONS, IMPORTANCE_OPTIONS, resolveRelation } from './relationships.js'
import './forms.css'
import PersonSearch from './PersonSearch.jsx'
import { demoApi } from './services/demoApi.js'
import { findAccount, normalizeUsername, normalizePhone, normalizeEmail, signupError, profileUpdateError, publicProfile, WORK_TYPES, VISIBILITY_OPTIONS } from './accountRules.js'

const EVENT_TYPES = ['결혼식', '돌잔치', '장례식', '생일']
const CUSTOM_TYPE = '__custom'
const CUSTOM_TYPE_SUGGESTIONS = ['환갑', '칠순', '팔순', '졸업', '집들이']
const ACCOUNTS_KEY = 'maeum-demo-accounts-v1'
const PBKDF2_ITERATIONS = 210000

function todayInSeoul() {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date())
  const read = (type) => parts.find((part) => part.type === type)?.value
  return `${read('year')}-${read('month')}-${read('day')}`
}

function Field({ label, required, hint, children, full = false }) {
  return <label className={`field${full ? ' field-full' : ''}`}>
    <span className="field-label">{label}{required && <span className="field-required" aria-hidden="true">*</span>}</span>
    {children}
    {hint && <span className="field-hint">{hint}</span>}
  </label>
}

function FormError({ message }) {
  return message ? <p className="form-error" role="alert"><Icon name="CircleAlert" size={16} />{message}</p> : null
}

function FormActions({ onClose, children, disabled = false }) {
  return <div className="form-actions">
    <button type="button" className="button button-secondary" onClick={onClose}>취소</button>
    <button type="submit" className="button button-primary" disabled={disabled}>{children}</button>
  </div>
}

export function EventForm({ people = [], onSave, onClose, user = null }) {
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    owner: 'other', personId: '', personName: '', title: '', type: '결혼식', date: todayInSeoul(),
    time: '14:00', location: '', attendance: '참석', reminderDays: 1,
    shareScope: 'private', shareMessage: '', consent: false, customType: '',
  })
  const update = (key, value) => setForm((previous) => ({ ...previous, [key]: value }))
  const selectedPerson = people.find((person) => person.id === form.personId)
  const mine = form.owner === 'me'
  const myName = user?.name || '나'
  const custom = form.type === CUSTOM_TYPE
  const type = custom ? form.customType.trim() : form.type
  const [quick, setQuick] = useState('')
  const [quickStatus, setQuickStatus] = useState({ state: 'idle', text: '' })

  // 한 줄 문장을 AI(서버)로 해석해 입력칸을 채운다. 저장은 사용자가 확인한 뒤에만 한다.
  async function fillFromText() {
    const text = quick.trim()
    if (!text || quickStatus.state === 'loading') return
    setQuickStatus({ state: 'loading', text: '문장을 해석하고 있어요…' })
    try {
      const result = await demoApi('/events/parse', { method: 'POST', body: { text, today: todayInSeoul() } })
      const s = result.suggestion || {}
      let matched = false
      setForm((prev) => {
        const next = { ...prev }
        if (s.type) {
          if (EVENT_TYPES.includes(s.type)) next.type = s.type
          else { next.type = CUSTOM_TYPE; next.customType = String(s.type).slice(0, 20) }
        }
        if (s.date) next.date = s.date
        if (s.time) next.time = s.time
        if (s.location) next.location = s.location
        if (s.title) next.title = s.title
        // 이름이 직접 나온 경우에만 인맥을 채운다. ('사촌'처럼 관계만 있으면 사용자가 고르게 둔다)
        if (prev.owner !== 'me' && s.person_name) {
          const match = people.find((person) => person.name === s.person_name)
          if (match) { next.personId = match.id; matched = true }
          else { next.personId = '__new'; next.personName = s.person_name }
        }
        return next
      })
      const filled = ['type', 'date', 'time', 'location'].filter((key) => s[key]).length
      setQuickStatus({ state: filled ? 'ok' : 'error', text: filled
        ? `${result.source === 'ai' ? 'AI가' : '문장에서'} ${filled}개 항목을 채웠어요.${matched ? ' 이름이 같은 인맥을 골라 두었어요.' : ''} 저장 전에 내용을 확인해 주세요.`
        : '일정 정보를 찾지 못했어요. 날짜·행사·장소를 함께 적어 주세요.' })
    } catch (error) {
      setQuickStatus({ state: 'error', text: /Failed to fetch|NetworkError|서버 요청에 실패/.test(String(error?.message)) ? 'AI 서버에 연결할 수 없어요. 아래 칸에 직접 입력해 주세요.' : String(error?.message || '해석하지 못했어요.') })
    }
  }

  function submit(event) {
    event.preventDefault()
    if (custom && !type) { setError('행사 유형을 직접 입력해 주세요. 예) 칠순, 졸업'); return }
    if (!type || !form.date || !form.time || !form.location.trim()) {
      setError('행사 유형, 날짜, 시간, 장소를 모두 확인해 주세요.')
      return
    }
    if (mine) {
      if (form.shareScope !== 'private' && !user) { setError('친구에게 보내려면 먼저 로그인해 주세요.'); return }
      if (form.shareScope !== 'private' && type === '장례식' && !form.consent) { setError('장례 소식은 유족(가족)의 공유 동의를 확인한 뒤 보낼 수 있어요.'); return }
      onSave({
        owner: 'me', personId: '', title: form.title.trim() || `${myName}의 ${type}`,
        type, date: form.date, time: form.time, location: form.location.trim(),
        attendance: '참석', reminderDays: Number(form.reminderDays), memo: form.shareMessage.trim(),
        shareScope: form.shareScope, shareMessage: form.shareMessage.trim(),
      })
      return
    }
    if (!selectedPerson && form.personId !== '__new') { setError('검색 결과에서 인맥을 선택해 주세요.'); return }
    const name = selectedPerson?.name || form.personName.trim()
    if (!name) { setError('누구의 경조사인지 선택하거나 이름을 입력해 주세요.'); return }
    onSave({
      personId: selectedPerson?.id || '',
      ...(selectedPerson ? {} : { personName: name }),
      title: form.title.trim() || `${name} ${type}`,
      type, date: form.date, time: form.time, location: form.location.trim(),
      attendance: form.attendance, reminderDays: Number(form.reminderDays),
    })
  }

  return <Modal title="새로운 마음을 챙겨요" subtitle={mine ? '내 경조사를 등록하고, 소중한 사람들에게 알려요.' : '경조사를 등록하고, 마음을 전할 때를 기억하세요.'} onClose={onClose} wide>
    <form onSubmit={submit} className="app-form">
      <div className="form-grid">
        <div className="owner-toggle" role="group" aria-label="누구의 경조사인가요?">
          <button type="button" aria-pressed={!mine} onMouseDown={event => event.preventDefault()} onClick={() => { update('owner', 'other'); setError('') }}><Icon name="UsersRound" size={16} />지인의 경조사</button>
          <button type="button" aria-pressed={mine} onMouseDown={event => event.preventDefault()} onClick={() => { update('owner', 'me'); setError('') }}><Icon name="Heart" size={16} />내 경조사</button>
        </div>
        <div className="quick-parse">
          <span><Icon name="Sparkles" size={15} />한 줄로 입력하기</span>
          <div className="quick-parse-row"><input className="input" aria-label="한 줄로 입력하기" value={quick} onChange={(event) => setQuick(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); fillFromText() } }} placeholder="예) 다음 주 토요일 1시 라온웨딩홀 사촌 결혼식" maxLength={300} />
            <button type="button" className="button button-secondary" disabled={!quick.trim() || quickStatus.state === 'loading'} onClick={fillFromText}>{quickStatus.state === 'loading' ? '해석 중…' : 'AI로 채우기'}</button></div>
          <small className={quickStatus.state} role="status">{quickStatus.text || '문장은 일정 해석에만 쓰이고 저장되지 않아요. 채운 내용은 저장 전에 직접 확인해 주세요.'}</small>
        </div>
        {!mine && <PersonSearch people={people} value={form.personId} onChange={value => update('personId', value)} />}
        {!mine && form.personId === '__new' && <Field label="이름" required full hint="새 인맥으로 함께 저장됩니다. 관계는 인맥 관리에서 수정할 수 있어요.">
          <input className="input" value={form.personName} onChange={(event) => update('personName', event.target.value)} placeholder="이름을 입력해 주세요" maxLength={40} required />
        </Field>}
        <Field label="행사 유형" required full={mine}>
          <select className="input" value={form.type} onChange={(event) => update('type', event.target.value)} required>
            <option value="" disabled>유형 선택</option>{EVENT_TYPES.map((item) => <option key={item}>{item}</option>)}<option value={CUSTOM_TYPE}>직접 입력</option>
          </select>
        </Field>
        {custom && <Field label="행사 유형 직접 입력" required full hint="환갑·칠순·팔순, 졸업, 집들이처럼 목록에 없는 행사를 적어 주세요.">
          <input className="input" value={form.customType} onChange={(event) => update('customType', event.target.value)} placeholder="예) 칠순" maxLength={20} autoFocus required />
          <span className="custom-type-chips">{CUSTOM_TYPE_SUGGESTIONS.map((item) => <button type="button" key={item} className={`filter-chip ${form.customType === item ? 'active' : ''}`} onClick={() => update('customType', item)}>{item}</button>)}</span>
        </Field>}
        {!mine && <Field label="참석 여부">
          <select className="input" value={form.attendance} onChange={(event) => update('attendance', event.target.value)}>
            {['참석', '불참'].map((value) => <option key={value}>{value}</option>)}
          </select>
        </Field>}
        <Field label="날짜" required><input className="input" type="date" value={form.date} onChange={(event) => update('date', event.target.value)} min="1900-01-01" max="2099-12-31" required /></Field>
        <Field label="시간" required><input className="input" type="time" value={form.time} onChange={(event) => update('time', event.target.value)} required /></Field>
        <Field label="장소" required full><input className="input" value={form.location} onChange={(event) => update('location', event.target.value)} placeholder={mine && type === '장례식' ? '예) 서울 마음빛 장례식장 1호실' : '예) 그린 웨딩홀 3층 그랜드홀'} maxLength={150} required /></Field>
        <Field label="일정 이름" full hint={mine ? '비워 두면 내 이름과 행사 유형으로 만들어 드려요.' : '비워 두면 이름과 행사 유형으로 만들어 드려요.'}><input className="input" value={form.title} onChange={(event) => update('title', event.target.value)} placeholder={mine ? `${myName}의 ${type || '결혼식'}` : `${selectedPerson?.name || form.personName || '김도윤'} ${type || '결혼식'}`} maxLength={80} /></Field>
        {mine && <>
          <Field label="친구에게 알리기" full hint={!user ? '로그인하면 마음결 친구에게 일정을 보낼 수 있어요.' : form.shareScope === 'friends_of_friends' ? '보낼 친구를 고른 뒤, 내 친구와 친구인 사람들에게도 소식이 보여요.' : form.shareScope === 'friends' ? '등록 후 일정을 받을 친구를 고를 수 있어요.' : '나만 볼 수 있어요. 나중에 일정 상세에서 보낼 수도 있어요.'}>
            <select className="input" value={form.shareScope} onChange={(event) => update('shareScope', event.target.value)} disabled={!user}>
              <option value="private">나만 보기</option><option value="friends">친구에게 보내기</option><option value="friends_of_friends">친구의 친구까지 알리기</option>
            </select>
          </Field>
          {form.shareScope !== 'private' && <Field label="전할 말" full><textarea className="input" rows={2} maxLength={300} value={form.shareMessage} onChange={(event) => update('shareMessage', event.target.value)} placeholder={type === '장례식' ? '예) 갑작스러운 소식 전합니다. 마음으로 함께해 주세요.' : '예) 소중한 날에 함께해 주시면 기쁘겠습니다.'} /></Field>}
          {form.shareScope !== 'private' && type === '장례식' && <label className="social-consent field-full"><input type="checkbox" checked={form.consent} onChange={(event) => update('consent', event.target.checked)} /><span>유족(가족)에게 소식 공유 동의를 받았어요.</span></label>}
        </>}
        <Field label="행사 전 알림" full hint="알림함에서 확인할 수 있어요. 브라우저 알림은 알림 설정에서 켤 수 있습니다.">
          <select className="input" value={form.reminderDays} onChange={(event) => update('reminderDays', event.target.value)}>
            <option value={0}>행사 당일</option><option value={1}>1일 전</option><option value={3}>3일 전</option><option value={7}>7일 전</option>
          </select>
        </Field>
      </div>
      <FormError message={error} />
      <FormActions onClose={onClose}><Icon name={mine && form.shareScope !== 'private' ? 'Send' : 'Plus'} size={17} />{mine && form.shareScope !== 'private' ? '등록하고 친구 고르기' : '일정 등록하기'}</FormActions>
    </form>
  </Modal>
}

export function PersonForm({ onSave, onClose }) {
  const [error, setError] = useState('')
  const [form, setForm] = useState({ name: '', relation: '친구', group: '', importance: '보통', closeness_score: null, special: false, lastMet: '', memo: '' })
  const [customRelation, setCustomRelation] = useState('')
  const update = (key, value) => setForm((previous) => ({ ...previous, [key]: value }))
  function submit(event) {
    event.preventDefault()
    if (!form.name.trim()) { setError('이름을 입력해 주세요.'); return }
    if (form.lastMet && form.lastMet > todayInSeoul()) { setError('마지막 만남은 오늘 또는 이전 날짜로 입력해 주세요.'); return }
    onSave({ ...form, relation: resolveRelation(form.relation, customRelation), name: form.name.trim(), group: form.group.trim(), memo: form.memo.trim(), interactions: [] })
  }
  return <Modal title="오래 이어갈 인연" subtitle="이름부터 함께한 순간까지, 소중한 사람을 기록해요." onClose={onClose}>
    <form onSubmit={submit} className="app-form">
      <div className="form-grid">
        <Field label="이름" required full><input className="input" value={form.name} onChange={(event) => update('name', event.target.value)} placeholder="이름을 입력해 주세요" maxLength={40} autoComplete="name" required /></Field>
        <Field label="관계" required><select className="input" aria-label="관계" value={form.relation} onChange={(event) => update('relation', event.target.value)}>{RELATION_OPTIONS.map((relation) => <option key={relation}>{relation}</option>)}</select></Field>
        <Field label="중요도"><select className="input" aria-label="중요도" value={form.importance} onChange={(event) => update('importance', event.target.value)}>{IMPORTANCE_OPTIONS.map(value => <option key={value}>{value}</option>)}</select></Field>
        <Field label="친밀도 (선택)"><select className="input" aria-label="친밀도" value={form.closeness_score ?? ''} onChange={event => update('closeness_score', event.target.value ? Number(event.target.value) : null)}><option value="">미기록</option>{[1, 2, 3, 4, 5].map(score => <option key={score} value={score}>{score}/5</option>)}</select></Field>
        <Field label="특별 관리"><label><input type="checkbox" checked={form.special} onChange={event => update('special', event.target.checked)} /> 특별히 챙길 사람</label></Field>
        {form.relation === '기타' && <Field label="관계 직접 입력" full hint="비워 두면 ‘기타’로 표시돼요."><input className="input" aria-label="관계 직접 입력" value={customRelation} onChange={event => setCustomRelation(event.target.value)} placeholder="예) 동호회 선배, 이웃" maxLength={40} /></Field>}
        <Field label="소속 그룹" full><input className="input" value={form.group} onChange={(event) => update('group', event.target.value)} placeholder="예) 대학 동기, 마케팅팀, 외가" maxLength={40} /></Field>
        <Field label="마지막으로 만난 날" full><input className="input" type="date" value={form.lastMet} onChange={(event) => update('lastMet', event.target.value)} min="1900-01-01" max={todayInSeoul()} /></Field>
        <Field label="기억하고 싶은 이야기" full><textarea className="input" value={form.memo} onChange={(event) => update('memo', event.target.value)} placeholder="취향이나 함께한 추억을 남겨 보세요." rows={3} maxLength={1000} /></Field>
      </div>
      <FormError message={error} />
      <FormActions onClose={onClose}><Icon name="UserPlus" size={17} />인맥 등록하기</FormActions>
    </form>
  </Modal>
}

export function RecordForm({ people = [], events = [], onSave, onClose, initialPersonId = '', initialEventId = '', initialRecord = null }) {
  const [error, setError] = useState('')
  const editing = !!initialRecord
  const recordTypes = [...new Set([...EVENT_TYPES, '기타', initialRecord?.type, ...events.map((event) => event.type)].filter(Boolean))]
  const [form, setForm] = useState(() => {
    const selectedPersonId = initialRecord?.personId || initialPersonId
    const selectedEventId = initialRecord?.eventId || initialEventId
    const linkedEvent = events.find((event) => event.id === selectedEventId && (!selectedPersonId || event.personId === selectedPersonId))
    const personId = people.some((person) => person.id === selectedPersonId)
      ? selectedPersonId
      : (people.some((person) => person.id === linkedEvent?.personId) ? linkedEvent.personId : '')
    return {
      direction: initialRecord?.direction || '보낸 마음', personId,
      eventId: linkedEvent?.personId === personId ? linkedEvent.id : '',
      type: initialRecord?.type || (linkedEvent?.personId === personId ? linkedEvent.type : '결혼식'),
      date: initialRecord?.date || todayInSeoul(), amount: initialRecord?.amount ?? '', memo: initialRecord?.memo || '',
    }
  })
  const update = (key, value) => setForm((previous) => ({ ...previous, [key]: value }))
  const personEvents = events.filter((event) => event.personId === form.personId)
  function selectEvent(eventId) {
    const selected = events.find((event) => event.id === eventId)
    setForm((previous) => ({ ...previous, eventId, ...(selected ? { type: selected.type } : {}) }))
  }
  function submit(event) {
    event.preventDefault()
    const amount = Number(form.amount)
    if (!people.some((person) => person.id === form.personId)) { setError('기록할 사람을 선택해 주세요.'); return }
    if (!Number.isSafeInteger(amount) || amount <= 0 || amount > 1000000000) { setError('금액은 1원부터 10억 원까지 정수로 입력해 주세요.'); return }
    if (!form.date) { setError('주고받은 날짜를 선택해 주세요.'); return }
    onSave({ ...form, amount, memo: form.memo.trim() })
  }
  return <Modal title={editing ? "금액 기록 수정" : "주고받은 마음 기록"} subtitle={editing ? "수정한 내용은 장부와 통계에 함께 반영돼요." : "다음에 마음을 전할 때 참고할 수 있도록 남겨요."} onClose={onClose}>
    <form onSubmit={submit} className="app-form">
      <div className="money-direction" aria-label="주고받은 방향">
        {['보낸 마음', '받은 마음'].map((direction) => <button type="button" key={direction} className={form.direction === direction ? 'active' : ''} aria-pressed={form.direction === direction} onClick={() => update('direction', direction)}>
          <Icon name={direction === '보낸 마음' ? 'ArrowUpRight' : 'ArrowDownLeft'} size={18} />{direction}
        </button>)}
      </div>
      {people.length === 0 && <p className="form-note">먼저 인맥 관리에서 사람을 등록해 주세요.</p>}
      <div className="form-grid">
        <Field label={form.direction === '보낸 마음' ? '누구에게 전했나요?' : '누구에게 받았나요?'} required full>
          <select className="input" value={form.personId} onChange={(event) => setForm((previous) => ({ ...previous, personId: event.target.value, eventId: '' }))} required>
            <option value="" disabled>사람을 선택해 주세요</option>{people.map((person) => <option key={person.id} value={person.id}>{person.name} · {person.relation}</option>)}
          </select>
        </Field>
        {personEvents.length > 0 && <Field label="연결할 일정" full><select className="input" value={form.eventId} onChange={(event) => selectEvent(event.target.value)}><option value="">일정 연결 없이 기록</option>{personEvents.map((event) => <option key={event.id} value={event.id}>{event.title} · {event.date}</option>)}</select></Field>}
        <Field label="행사 유형" required><select className="input" value={form.type} onChange={(event) => setForm(previous => ({...previous, type:event.target.value, eventId:events.find(item => item.id === previous.eventId)?.type === event.target.value ? previous.eventId : ''}))}>{recordTypes.map((type) => <option key={type}>{type}</option>)}</select></Field>
        <Field label="주고받은 날짜" required><input type="date" className="input" value={form.date} onChange={(event) => update('date', event.target.value)} min="1900-01-01" max="2099-12-31" required /></Field>
        <Field label="금액" required full>
          <span className="money-input-wrap"><input className="input" inputMode="numeric" type="number" min={1} max={1000000000} step={1} value={form.amount} onChange={(event) => update('amount', event.target.value)} placeholder="0" required /><span>원</span></span>
        </Field>
        <div className="quick-amounts field-full">{[50000, 100000, 200000].map((amount) => <button className="filter-chip" type="button" key={amount} onClick={() => update('amount', String(amount))}>{amount / 10000}만 원</button>)}<span className="field-hint">{Number(form.amount) > 0 ? `${Number(form.amount).toLocaleString('ko-KR')}원` : '금액을 선택하거나 직접 입력하세요'}</span></div>
        <Field label="메모" full><textarea className="input" rows={3} value={form.memo} onChange={(event) => update('memo', event.target.value)} placeholder="예) 결혼식에 참석해 직접 전달" maxLength={1000} /></Field>
      </div>
      <FormError message={error} />
      <FormActions onClose={onClose} disabled={!people.length}><Icon name="Check" size={17} />{editing ? '변경사항 저장' : '마음 기록하기'}</FormActions>
    </form>
  </Modal>
}

function bytesToBase64(bytes) {
  return btoa(String.fromCharCode(...bytes))
}

function base64ToBytes(value) {
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0))
}

async function hashPassword(password, salt, iterations = PBKDF2_ITERATIONS) {
  if (!globalThis.crypto?.subtle) throw new Error('crypto-unavailable')
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits'])
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', salt, iterations, hash: 'SHA-256' }, key, 256)
  return bytesToBase64(new Uint8Array(bits))
}

function readAccounts() {
  const stored = localStorage.getItem(ACCOUNTS_KEY)
  if (!stored) return []
  const accounts = JSON.parse(stored)
  if (!Array.isArray(accounts)) throw new Error('invalid-storage')
  return accounts
}

const emptyAuthForm = { username: '', name: '', password: '', confirmation: '', phone: '', email: '', workplace: '', organization: '', workType: '', visibility: '' }

function WorkFields({ form, update, disabled }) {
  return <>
    <Field label="직장" hint="선택 입력 · 예: 마음전자"><input className="input" aria-label="직장" value={form.workplace} onChange={event => update('workplace', event.target.value)} maxLength={60} autoComplete="organization" disabled={disabled}/></Field>
    <Field label="소속기관" hint="선택 입력 · 예: 인사팀, ○○시청"><input className="input" aria-label="소속기관" value={form.organization} onChange={event => update('organization', event.target.value)} maxLength={60} disabled={disabled}/></Field>
    <Field label="직무형태" required hint="공직자 등은 청탁금지법 기준을 함께 안내해요."><select className="input" aria-label="직무형태" value={form.workType} onChange={event => update('workType', event.target.value)} required disabled={disabled}><option value="" disabled>직무형태 선택</option>{WORK_TYPES.map(item => <option key={item}>{item}</option>)}</select></Field>
    <Field label="정보공개여부" required hint="친구 찾기에서 내 정보가 보이는 범위예요."><select className="input" aria-label="정보공개여부" value={form.visibility} onChange={event => update('visibility', event.target.value)} required disabled={disabled}><option value="" disabled>공개 범위 선택</option>{VISIBILITY_OPTIONS.map(item => <option key={item}>{item}</option>)}</select></Field>
  </>
}

function accountErrorMessage(cause) {
  return cause?.message === 'crypto-unavailable'
    ? '이 브라우저에서는 계정을 저장할 수 없어요. localhost 또는 HTTPS 환경에서 다시 시도해 주세요.'
    : '브라우저 저장소를 사용할 수 없어요. 저장 공간과 브라우저 설정을 확인해 주세요.'
}

export function AuthModal({ mode = 'login', onClose, onSuccess, onSwitch }) {
  const signup = mode === 'signup'
  const [form, setForm] = useState(emptyAuthForm)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const update = (key, value) => setForm((previous) => ({ ...previous, [key]: value }))
  useEffect(() => {
    setError('')
    setForm((previous) => ({ ...previous, password: '', confirmation: '' }))
  }, [mode])

  async function submit(event) {
    event.preventDefault()
    if (pending) return
    if (signup) { const error = signupError(form); if (error) { setError(error); return } }
    setPending(true)
    setError('')
    try {
      const accounts = readAccounts()
      if (signup) {
        const error = signupError(form, accounts)
        if (error) { setError(error); return }
        const salt = crypto.getRandomValues(new Uint8Array(16))
        const hash = await hashPassword(form.password, salt)
        const account = { username: normalizeUsername(form.username), name: form.name.trim(), phone: normalizePhone(form.phone), email: normalizeEmail(form.email), workplace: form.workplace.trim(), organization: form.organization.trim(), workType: form.workType, visibility: form.visibility, salt: bytesToBase64(salt), hash, iterations: PBKDF2_ITERATIONS }
        localStorage.setItem(ACCOUNTS_KEY, JSON.stringify([...accounts, account]))
        onSuccess(publicProfile(account))
      } else {
        const account = findAccount(accounts, form.username)
        if (!account?.salt || !account?.hash) { setError('아이디와 비밀번호를 확인해 주세요. 처음이라면 회원가입을 해 주세요.'); return }
        const hash = await hashPassword(form.password, base64ToBytes(account.salt), account.iterations || PBKDF2_ITERATIONS)
        if (hash !== account.hash) { setError('아이디와 비밀번호를 확인해 주세요.'); return }
        onSuccess(publicProfile(account))
      }
    } catch (cause) {
      setError(accountErrorMessage(cause))
    } finally {
      setPending(false)
    }
  }

  return <Modal title={signup ? '함께 마음을 이어가요' : '다시 만나 반가워요'} subtitle={signup ? '소중한 관계를 챙기는 작은 습관, 지금 시작해요.' : '기억해 둔 마음을 다시 만나 보세요.'} onClose={pending ? () => {} : onClose} wide={signup}>
    <form onSubmit={submit} className="app-form auth-form">
      {signup ? <div className="form-grid">
        <Field label="아이디" required hint="영문·숫자·밑줄 4~20자, 대소문자를 구분하지 않아요."><input className="input" aria-label="아이디" value={form.username} onChange={event => update('username', event.target.value)} minLength={4} maxLength={20} autoComplete="username" autoCapitalize="none" spellCheck={false} required disabled={pending}/></Field>
        <Field label="이름" required><input className="input" aria-label="이름" value={form.name} onChange={event => update('name', event.target.value)} maxLength={40} autoComplete="name" required disabled={pending}/></Field>
        <Field label="비밀번호" required hint="8자 이상으로 입력해 주세요."><input className="input" aria-label="비밀번호" type="password" value={form.password} onChange={event => update('password', event.target.value)} minLength={8} maxLength={128} autoComplete="new-password" required disabled={pending}/></Field>
        <Field label="비밀번호 확인" required><input className="input" aria-label="비밀번호 확인" type="password" value={form.confirmation} onChange={event => update('confirmation', event.target.value)} minLength={8} maxLength={128} autoComplete="new-password" required disabled={pending}/></Field>
        <Field label="전화번호" required hint="예: 010-1234-5678"><input className="input" aria-label="전화번호" type="tel" value={form.phone} onChange={event => update('phone', event.target.value)} maxLength={24} autoComplete="tel" required disabled={pending}/></Field>
        <Field label="이메일" required><input className="input" aria-label="이메일" type="email" value={form.email} onChange={event => update('email', event.target.value)} maxLength={254} autoComplete="email" required disabled={pending}/></Field>
        <WorkFields form={form} update={update} disabled={pending} />
      </div> : <div className="auth-login-fields">
        <Field label="아이디" required><input className="input" aria-label="아이디" value={form.username} onChange={event => update('username', event.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} required disabled={pending}/></Field>
        <Field label="비밀번호" required><input className="input" aria-label="비밀번호" type="password" value={form.password} onChange={event => update('password', event.target.value)} maxLength={128} autoComplete="current-password" required disabled={pending}/></Field>
      </div>}
      <FormError message={error} />
      <button className="button button-primary auth-submit" type="submit" disabled={pending}>{pending && <span className="form-spinner" aria-hidden="true" />}{pending ? (signup ? '계정을 만드는 중…' : '확인하는 중…') : (signup ? '회원가입' : '로그인')}<Icon name="ArrowRight" size={17} /></button>
    </form>
    <p className="auth-switch">{signup ? '이미 계정이 있나요?' : '아직 계정이 없나요?'} <button type="button" onClick={() => onSwitch(signup ? 'login' : 'signup')} disabled={pending}>{signup ? '로그인' : '회원가입'}</button></p>
  </Modal>
}

export function ProfileEditModal({ user, onClose, onSave }) {
  const [form, setForm] = useState(() => {
    const account = (() => { try { return findAccount(readAccounts(), user?.username) } catch { return undefined } })() || user || {}
    return { currentPassword: '', password: '', confirmation: '', phone: account.phone || '', email: account.email || '', workplace: account.workplace || '', organization: account.organization || '', workType: account.workType || '', visibility: account.visibility || '' }
  })
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const update = (key, value) => setForm((previous) => ({ ...previous, [key]: value }))

  async function submit(event) {
    event.preventDefault()
    if (pending) return
    setPending(true)
    setError('')
    try {
      const accounts = readAccounts()
      const account = findAccount(accounts, user?.username)
      if (!account?.salt || !account?.hash) { setError('이 브라우저에 저장된 계정을 찾지 못했어요. 다시 로그인해 주세요.'); return }
      const error = profileUpdateError(form, accounts, account.username)
      if (error) { setError(error); return }
      const next = { ...account, phone: normalizePhone(form.phone), email: normalizeEmail(form.email), workplace: form.workplace.trim(), organization: form.organization.trim(), workType: form.workType, visibility: form.visibility }
      if (form.password) {
        const current = await hashPassword(form.currentPassword, base64ToBytes(account.salt), account.iterations || PBKDF2_ITERATIONS)
        if (current !== account.hash) { setError('현재 비밀번호가 맞지 않아요.'); return }
        const salt = crypto.getRandomValues(new Uint8Array(16))
        Object.assign(next, { salt: bytesToBase64(salt), hash: await hashPassword(form.password, salt), iterations: PBKDF2_ITERATIONS })
      }
      localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts.map(item => item === account ? next : item)))
      onSave(publicProfile(next), Boolean(form.password))
    } catch (cause) {
      setError(accountErrorMessage(cause))
    } finally {
      setPending(false)
    }
  }

  return <Modal title="내 정보 수정" subtitle={`${user?.name || ''}님의 계정 정보를 바꿀 수 있어요. 아이디와 이름은 바꿀 수 없어요.`} onClose={pending ? () => {} : onClose} wide>
    <form onSubmit={submit} className="app-form auth-form profile-form">
      <div className="form-grid">
        <Field label="아이디"><input className="input" value={user?.username || ''} readOnly disabled /></Field>
        <Field label="이름"><input className="input" value={user?.name || ''} readOnly disabled /></Field>
        <Field label="새 비밀번호" hint="바꿀 때만 입력 · 8자 이상"><input className="input" aria-label="새 비밀번호" type="password" value={form.password} onChange={event => update('password', event.target.value)} maxLength={128} autoComplete="new-password" disabled={pending}/></Field>
        <Field label="새 비밀번호 확인"><input className="input" aria-label="새 비밀번호 확인" type="password" value={form.confirmation} onChange={event => update('confirmation', event.target.value)} maxLength={128} autoComplete="new-password" disabled={pending}/></Field>
        {form.password && <Field label="현재 비밀번호" required full hint="비밀번호를 바꾸려면 현재 비밀번호를 확인해요."><input className="input" aria-label="현재 비밀번호" type="password" value={form.currentPassword} onChange={event => update('currentPassword', event.target.value)} maxLength={128} autoComplete="current-password" required disabled={pending}/></Field>}
        <Field label="전화번호" required hint="예: 010-1234-5678"><input className="input" aria-label="전화번호" type="tel" value={form.phone} onChange={event => update('phone', event.target.value)} maxLength={24} autoComplete="tel" required disabled={pending}/></Field>
        <Field label="이메일" required><input className="input" aria-label="이메일" type="email" value={form.email} onChange={event => update('email', event.target.value)} maxLength={254} autoComplete="email" required disabled={pending}/></Field>
        <WorkFields form={form} update={update} disabled={pending} />
      </div>
      <FormError message={error} />
      <div className="form-actions"><button className="button button-secondary" type="button" onClick={onClose} disabled={pending}>취소</button><button className="button button-primary" type="submit" disabled={pending}>{pending && <span className="form-spinner" aria-hidden="true" />}{pending ? '저장하는 중…' : '변경사항 저장'}</button></div>
    </form>
  </Modal>
}
