import { useEffect, useRef, useState } from 'react';
import { Icon, Modal } from './ui.jsx';
import { demoApi } from './IntegratedAIPage.jsx';
import { SHARED_EVENT_CATEGORIES, prepareSharedEvent, sharedReasonLabel, sharedScopeLabel } from './sharedEvents.js';
import './forms.css';

const ATTENDANCE = [
  ['unknown', '미확인'], ['allowed', '참석 허용'], ['not_allowed', '참석 불허'],
];

function SharedEventForm({ userId, today, onClose, onSaved }) {
  const [form, setForm] = useState({
    category: '결혼', title: '', start_date: today, end_date: today, region: '', venue: '',
    audience_scope: 'private', sharing_confirmed: false, direct_friend_attendance: 'unknown',
    friend_of_friend_attendance: 'unknown', publisher_name_visible: false,
    related_role: '', related_user_recommendation_allowed: false,
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const update = (key, value) => setForm(previous => ({ ...previous, [key]: value }));

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    try {
      const body = prepareSharedEvent(form);
      setSaving(true);
      setError('');
      await demoApi('/shared-events', { userId, method: 'POST', body });
      if (mounted.current) onSaved();
    } catch (problem) {
      if (mounted.current) setError(problem.message);
    } finally {
      if (mounted.current) setSaving(false);
    }
  }

  return <Modal title="공유 경조사 등록" subtitle="가상의 소식과 공유 범위를 선택해 주세요." onClose={() => { if (!saving) onClose(); }} wide>
    <form className="app-form" onSubmit={submit}>
      <div className="form-grid">
        <label className="field"><span className="field-label">행사 유형</span>
          <select className="input" aria-label="공유 행사 유형" value={form.category} onChange={event => setForm(previous => ({ ...previous, category: event.target.value, related_role: '', related_user_recommendation_allowed: false }))}>
            {SHARED_EVENT_CATEGORIES.map(category => <option key={category}>{category}</option>)}
          </select>
        </label>
        <label className="field"><span className="field-label">소식 제목</span>
          <input className="input" aria-label="소식 제목" value={form.title} onChange={event => update('title', event.target.value)} maxLength={100} required />
        </label>
        <label className="field"><span className="field-label">시작일</span>
          <input className="input" aria-label="공유 시작일" type="date" value={form.start_date} onChange={event => update('start_date', event.target.value)} required />
        </label>
        <label className="field"><span className="field-label">종료일</span>
          <input className="input" aria-label="공유 종료일" type="date" value={form.end_date} onChange={event => update('end_date', event.target.value)} required />
        </label>
        <label className="field"><span className="field-label">지역 <small>선택</small></span>
          <input className="input" aria-label="공유 지역" value={form.region} onChange={event => update('region', event.target.value)} maxLength={100} />
        </label>
        <label className="field"><span className="field-label">장소 <small>선택</small></span>
          <input className="input" aria-label="공유 장소" value={form.venue} onChange={event => update('venue', event.target.value)} maxLength={200} />
        </label>
        <label className="field field-full"><span className="field-label">공유 범위</span>
          <select className="input" aria-label="공유 범위" value={form.audience_scope} onChange={event => update('audience_scope', event.target.value)}>
            <option value="private">나만 보기</option><option value="friends_only">직접 친구</option>
            <option value="friends_and_friends_of_friends">직접 친구와 친구의 친구</option>
          </select>
        </label>
        {form.audience_scope !== 'private' && <>
          <label className="field"><span className="field-label">직접 친구의 참석</span>
            <select className="input" aria-label="직접 친구 참석 허용" value={form.direct_friend_attendance} onChange={event => update('direct_friend_attendance', event.target.value)}>
              {ATTENDANCE.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          {form.audience_scope === 'friends_and_friends_of_friends' && <label className="field"><span className="field-label">친구의 친구 참석</span>
            <select className="input" aria-label="친구의 친구 참석 허용" value={form.friend_of_friend_attendance} onChange={event => update('friend_of_friend_attendance', event.target.value)}>
              {ATTENDANCE.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>}
          <label className="shared-check field-full"><input type="checkbox" checked={form.sharing_confirmed} onChange={event => update('sharing_confirmed', event.target.checked)} />이 가상 소식을 선택한 범위에 공유할 수 있음을 확인했어요.</label>
        </>}
        <label className="field field-full"><span className="field-label">소식과 나의 관계</span>
          <select className="input" aria-label="소식과 나의 관계" value={form.related_role} onChange={event => setForm(previous => ({ ...previous, related_role: event.target.value, related_user_recommendation_allowed: false }))}>
            <option value="">관련 인물 지정 안 함</option>
            {form.category === '장례' ? <option value="mourner">내가 상주인 부고</option> : <option value="subject">나의 행사</option>}
          </select>
        </label>
        <label className="shared-check field-full"><input type="checkbox" checked={form.publisher_name_visible} onChange={event => update('publisher_name_visible', event.target.checked)} />공유자 이름을 표시해도 돼요.</label>
        {form.related_role && <label className="shared-check field-full"><input type="checkbox" checked={form.related_user_recommendation_allowed} onChange={event => update('related_user_recommendation_allowed', event.target.checked)} />확인된 인맥 관계를 추천 이유에 사용해도 돼요.</label>}
      </div>
      <p className="form-note">이름을 숨겨도 제목이나 장소에 적힌 내용으로 누구인지 알 수 있습니다. 실제 개인정보는 입력하지 마세요.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-actions"><button type="button" className="button button-secondary" onClick={onClose} disabled={saving}>취소</button><button type="submit" className="button button-primary" disabled={saving}>{saving ? '저장 중' : '소식 저장'}</button></div>
    </form>
  </Modal>;
}

export default function SharedEventsPanel({ userId, onUserIdChange, today }) {
  const [users, setUsers] = useState([]);
  const [usersError, setUsersError] = useState('');
  const [revision, setRevision] = useState(0);
  const [snapshot, setSnapshot] = useState({ userId: '', items: [], mine: [], loading: false, error: '' });
  const [formUser, setFormUser] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [action, setAction] = useState(null);
  const [message, setMessage] = useState(null);
  const activeUser = useRef(userId);
  const detailRequest = useRef(null);
  activeUser.current = userId;

  useEffect(() => {
    const controller = new AbortController();
    demoApi('/demo/users', { signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) setUsers(result.items || []);
    }).catch(error => { if (error.name !== 'AbortError') setUsersError(error.message); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    detailRequest.current?.abort();
    setDetail(null);
    setSnapshot({ userId, items: [], mine: [], loading: Boolean(userId), error: '' });
    if (userId) {
      Promise.all([
        demoApi('/shared-events/recommendations', { userId, signal: controller.signal }),
        demoApi('/shared-events/mine', { userId, signal: controller.signal }),
      ]).then(([recommended, mine]) => {
        if (!controller.signal.aborted) setSnapshot({ userId, items: recommended.items || [], mine: mine.items || [], referenceDate: recommended.reference_date, loading: false, error: '' });
      }).catch(error => {
        if (error.name !== 'AbortError') setSnapshot({ userId, items: [], mine: [], loading: false, error: error.message });
      });
    }
    return () => controller.abort();
  }, [userId, revision]);

  useEffect(() => { setFormUser(''); setDetailError(null); setAction(null); setMessage(null); }, [userId]);

  useEffect(() => {
    if (!userId) return;
    const refresh = () => { if (document.visibilityState === 'visible') setRevision(value => value + 1); };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => { window.removeEventListener('focus', refresh); document.removeEventListener('visibilitychange', refresh); };
  }, [userId]);

  useEffect(() => () => detailRequest.current?.abort(), []);

  async function openDetail(id) {
    detailRequest.current?.abort();
    const controller = new AbortController();
    detailRequest.current = controller;
    setDetail(null);
    setDetailError(null);
    try {
      const response = await demoApi(`/shared-events/${encodeURIComponent(id)}`, { userId, signal: controller.signal });
      if (!controller.signal.aborted && activeUser.current === userId) setDetail({ userId, item: response.item });
    } catch (error) {
      if (error.name !== 'AbortError' && activeUser.current === userId) {
        setDetailError({ userId, text: error.message });
        setRevision(value => value + 1);
      }
    }
  }

  async function revoke(id) {
    if (action?.userId === userId) return;
    setAction({ userId, id });
    setMessage(null);
    try {
      await demoApi(`/shared-events/${encodeURIComponent(id)}`, { userId, method: 'PATCH', body: { audience_scope: 'private' } });
      if (activeUser.current === userId) {
        setMessage({ userId, text: '공유를 철회하고 나만 보기로 바꿨어요.' });
        setRevision(value => value + 1);
      }
    } catch (error) {
      if (activeUser.current === userId) setMessage({ userId, text: error.message, error: true });
    } finally {
      if (activeUser.current === userId) setAction(null);
    }
  }

  const current = snapshot.userId === userId ? snapshot : { items: [], mine: [], loading: Boolean(userId), error: '' };
  const selected = detail?.userId === userId ? detail.item : null;
  return <section className="card shared-events" aria-label="공유된 경조사 추천">
    <div className="shared-events-heading"><div><h2>공유된 경조사</h2><p>친구와 친구의 친구가 공유한 가상 소식을 확인해요.</p></div>
      <button type="button" className="button button-secondary" disabled={!userId} onClick={() => setFormUser(userId)}><Icon name="Plus" size={15} />공유 소식 등록</button>
    </div>
    <div className="shared-events-toolbar"><label>가상 계정 <select className="input" aria-label="일정 화면 가상 계정" value={userId} onChange={event => onUserIdChange(event.target.value)}>
      <option value="">계정 선택</option>{users.map(user => <option key={user.id} value={user.id}>{user.name} · {user.affiliation || user.id} ({user.id})</option>)}
    </select></label>{current.referenceDate && <small>조회 기준일 {current.referenceDate}</small>}</div>
    <p className="shared-events-note">가상 계정과 합성 데이터로만 시연합니다. 개인 일정과는 별도로 표시돼요.</p>
    {usersError && <p className="shared-events-error" role="alert">계정 목록을 불러오지 못했어요: {usersError}</p>}
    {message?.userId === userId && <p role={message.error ? 'alert' : 'status'} className={message.error ? 'shared-events-error' : 'shared-events-success'}>{message.text}</p>}
    {detailError?.userId === userId && <p className="shared-events-error" role="alert">{detailError.text}</p>}
    {!userId ? <p className="shared-events-empty">가상 계정을 선택하면 공유된 소식을 볼 수 있어요.</p>
      : current.loading ? <p className="shared-events-empty" role="status">공유된 소식을 불러오고 있어요.</p>
        : current.error ? <p className="shared-events-error" role="alert">소식을 불러오지 못했어요: {current.error}</p>
          : <>
            <div className="shared-events-list" aria-label="추천 소식 목록">
              {current.items.length ? current.items.map(item => <article className="shared-event" key={item.id}>
                <div><span className="shared-event-category">{item.category}</span><h3>{item.title}</h3>
                  <p>{item.start_date}{item.end_date !== item.start_date ? ` ~ ${item.end_date}` : ''} · {item.region || '지역 미기록'}</p>
                  <p>{sharedReasonLabel(item.reason_code)}{item.publisher_name ? ` · ${item.publisher_name} 님 공유` : ''}</p>
                </div><button type="button" className="button button-secondary" onClick={() => openDetail(item.id)}>상세 보기</button>
              </article>) : <p className="shared-events-empty">현재 추천할 수 있는 공유 소식이 없어요.</p>}
            </div>
            <details className="shared-mine"><summary>내가 등록한 공유 소식 ({current.mine.length})</summary>
              {current.mine.length ? current.mine.map(item => <div className="shared-mine-item" key={item.id}>
                <span><strong>{item.title}</strong><small>{sharedScopeLabel(item.audience_scope)} · {item.start_date}</small></span>
                <div><button type="button" className="button button-secondary" onClick={() => openDetail(item.id)}>상세 보기</button>
                  {item.audience_scope !== 'private' && <button type="button" className="button button-secondary" disabled={action?.userId === userId} onClick={() => revoke(item.id)}>공유 철회</button>}</div>
              </div>) : <p className="shared-events-empty">등록한 공유 소식이 없어요.</p>}
            </details>
          </>}
    {formUser && formUser === userId && <SharedEventForm key={formUser} userId={userId} today={today} onClose={() => setFormUser('')} onSaved={() => { setFormUser(''); setMessage({ userId, text: '가상 소식을 저장했어요.' }); setRevision(value => value + 1); }} />}
    {selected && <Modal title={selected.title} subtitle="공유된 가상 경조사" onClose={() => setDetail(null)}>
      <div className="shared-detail"><p>{selected.category} · {selected.start_date}{selected.end_date !== selected.start_date ? ` ~ ${selected.end_date}` : ''}</p>
        <p>지역: {selected.region || '미기록'} · 장소: {selected.venue || '미기록'}</p>
        {selected.reason_code && <p>추천 이유: {sharedReasonLabel(selected.reason_code)}</p>}
        {selected.publisher_name && <p>공유자: {selected.publisher_name}</p>}
        {selected.mourner && <p>상주: {selected.mourner.name || '미기록'} · 관계: {selected.mourner.deceased_relation || '미기록'}</p>}
        {selected.room && <p>빈소: {selected.room}</p>}{selected.visiting_hours && <p>조문 시간: {selected.visiting_hours}</p>}
        {selected.audience_scope && <p>공유 범위: {sharedScopeLabel(selected.audience_scope)}</p>}
      </div>
    </Modal>}
  </section>;
}
