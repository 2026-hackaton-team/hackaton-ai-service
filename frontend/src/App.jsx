import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import { initialPeople, initialEvents, initialRecords } from './data.js';
import { daysUntil, formatMoney, toICS, normalizeAttendance } from './domain.js';
import { EventForm, PersonForm, RecordForm, AuthModal, ProfileEditModal } from './Forms.jsx';
import PeoplePage from './PeoplePage.jsx';
import LedgerPage from './LedgerPage.jsx';
import SchedulePage from './SchedulePage.jsx';
import AIPage from './IntegratedAIPage.jsx';
import EtiquettePage from './EtiquettePage.jsx';
import Notifications, { useSharedNoticeInbox, receivedReadId } from './Notifications.jsx';
import { SocialContext, ShareEventModal, ShareStatus, ReceivedScheduleDialog } from './Social.jsx';
import { SOCIAL_EVENT, SOCIAL_KEY, ACCOUNTS_KEY, loadSocial, mutateSocial, readMembers, setReceipt, updateSharedEvent, removeShare } from './services/socialStore.js';
import { buildReceivedItems, itemToEvent } from './services/receivedItems.js';
import { demoApi } from './services/demoApi.js';
import { materializeImport } from './ledgerCsv.js';
import { STORAGE_KEYS, readStored, writeStored } from './services/workspaceStorage.js';
import { useServerWorkspace } from './services/serverWorkspace.js';
import { setDemoAccount } from './services/demoAccount.js';
import { seedTestSocial, TEST_USERNAME, TEST_PROFILE_ID } from './services/testAccountDemo.js';
import { normalizePerson } from './relationships.js';
import { occasionClass, attendanceClass } from './occasion.js';

const PROFILE_LINKS_KEY = 'maeum-profile-links-v1';
const navigation = [
  { id: 'home', label: '홈', icon: 'LayoutGrid' },
  { id: 'schedule', label: '일정 관리', icon: 'CalendarDays' },
  { id: 'people', label: '인맥 관리', icon: 'UsersRound' },
  { id: 'ledger', label: '금액 · 통계', icon: 'ChartNoAxesCombined' },
  { id: 'ai', label: '마음결 AI', icon: 'Sparkles' },
  { id: 'guide', label: '경조사 예절', icon: 'Bookmark' },
];
const koreanDate = () => {
  const p = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  return ['year', 'month', 'day'].map(key => p.find(part => part.type === key).value).join('-');
};
const fullDate = date => new Date(`${date}T12:00:00+09:00`).toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
const eventIcon = type => type === '장례식' ? 'Flower2' : type === '돌잔치' || type === '생일' ? 'Cake' : 'Heart';
const ddLabel = days => days === 0 ? '오늘' : days > 0 ? `D-${days}` : '지난 일정';

// key 가 바뀌면(로그인 계정 전환) 해당 계정의 저장값을 다시 읽는다.
function useStored(key, initial, normalize = value => value) {
  const [store, setStore] = useState(() => ({ key, value: readStored(key, initial, normalize) }));
  const current = store.key === key ? store : { key, value: readStored(key, initial, normalize) };
  if (store.key !== key) setStore(current);
  useEffect(() => { try { writeStored(current.key, current.value); } catch { /* Private mode can disable storage. The current session still works. */ } }, [current.key, current.value]);
  const setValue = useCallback(update => setStore(previous => ({ key: previous.key, value: typeof update === 'function' ? update(previous.value) : update })), []);
  return [current.value, setValue];
}

export default function App() {
  const [user, setUser] = useStored(STORAGE_KEYS.session, null);
  // 로그인한 계정마다 인맥 · 일정 · 금액 기록을 따로 보관한다. (로그아웃 상태는 기본 공간)
  const scope = user?.username ? `:${user.username}` : '';
  const workspaceKeys = useMemo(() => ({ ...STORAGE_KEYS, people: STORAGE_KEYS.people + scope, events: STORAGE_KEYS.events + scope, records: STORAGE_KEYS.records + scope, readIds: STORAGE_KEYS.readIds + scope }), [scope]);
  const [localPeople] = useStored(workspaceKeys.people, initialPeople, items => items.map(normalizePerson));
  const [localEvents] = useStored(workspaceKeys.events, initialEvents, items => items.map(event => ({ ...event, attendance: normalizeAttendance(event.attendance) })));
  const [localRecords] = useStored(workspaceKeys.records, initialRecords);
  const [themeMode, setThemeMode] = useStored(STORAGE_KEYS.theme, 'auto');
  const [readIds, setReadIds] = useStored(workspaceKeys.readIds, []);
  const sharedInbox = useSharedNoticeInbox();
  const { state: workspace, commit: commitServer, initialize: initializeServer } = useServerWorkspace(sharedInbox.userId);
  const linked = Boolean(sharedInbox.userId);
  const workspaceReady = linked && workspace.owner === sharedInbox.userId && workspace.status === 'ready';
  const people = linked ? (workspaceReady ? workspace.snapshot.people.map(normalizePerson) : []) : localPeople;
  const events = linked ? (workspaceReady ? workspace.snapshot.events.map(event => ({ ...event, attendance: normalizeAttendance(event.attendance) })) : []) : localEvents;
  const records = linked ? (workspaceReady ? workspace.snapshot.records : []) : localRecords;
  const [notificationSettings, setNotificationSettings] = useStored(STORAGE_KEYS.notifications, { browser: false });
  const [page, setPage] = useState(() => navigation.some(item => item.id === location.hash.slice(1)) ? location.hash.slice(1) : 'home');
  const [aiPersonId, setAiPersonId] = useState('');
  const [peopleTab, setPeopleTab] = useState({ tab: 'people', nonce: 0 });
  const [modal, setModal] = useState(null);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useStored(STORAGE_KEYS.sidebarCollapsed, false);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches);
  useEffect(() => { const media = window.matchMedia('(max-width: 760px)'); const sync = () => { setIsMobile(media.matches); setMenuOpen(false); }; media.addEventListener('change', sync); return () => media.removeEventListener('change', sync); }, []);
  useEffect(() => { const close = e => { if(e.key === 'Escape') { setMenuOpen(false); setThemeOpen(false); setAccountOpen(false); } }; document.addEventListener('keydown', close); return () => document.removeEventListener('keydown', close); }, []);
  const [toast, setToast] = useState('');
  const [today, setToday] = useState(koreanDate);
  const toastTimer = useRef(null);
  const upcoming = useMemo(() => events.filter(event => daysUntil(event.date, today) >= 0).sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time)), [events, today]);
  const hasUrgentFuneral = upcoming.some(event => event.type === '장례식' && daysUntil(event.date, today) <= 3);
  const dark = themeMode === 'dark' || themeMode === 'auto' && hasUrgentFuneral;
  const notices = useMemo(() => upcoming.filter(event => daysUntil(event.date, today) <= 30).map(event => ({ id: `event-${event.id}-${event.date}`, event, days: daysUntil(event.date, today) })).sort((a, b) => Number(b.event.type === '장례식') - Number(a.event.type === '장례식') || a.days - b.days), [upcoming, today]);

  function notify(message) { setToast(message); clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToast(''), 3500); }
  function navigate(id) { setPage(id); location.hash = id; setMenuOpen(false); setThemeOpen(false); setAccountOpen(false); window.scrollTo({ top: 0, behavior: 'instant' }); }
  useEffect(() => { const handler = () => { const id = location.hash.slice(1); if (navigation.some(item => item.id === id)) setPage(id); }; window.addEventListener('hashchange', handler); return () => window.removeEventListener('hashchange', handler); }, []);
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; }, [dark]);
  useEffect(() => { const timer = setInterval(() => setToday(koreanDate()), 30000); return () => { clearInterval(timer); clearTimeout(toastTimer.current); }; }, []);
  useEffect(() => {
    if (!notificationSettings.browser || typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
    const sendReminders = () => {
      upcoming.filter(event => daysUntil(event.date, today) <= Number(event.reminderDays ?? 3)).forEach(event => {
        const key = `maeum-delivered-${event.id}-${event.date}-${today}`;
        if (localStorage.getItem(key)) return;
        new Notification(event.type === '장례식' ? '조심스럽게 전하는 소식' : '마음을 전할 날이 다가와요', { body: `${event.title} · ${event.date} ${event.time}`, tag: event.id, icon: '/favicon.svg' });
        localStorage.setItem(key, '1');
      });
    };
    sendReminders(); const timer = setInterval(sendReminders, 60000); return () => clearInterval(timer);
  }, [notificationSettings.browser, upcoming, today]);

  async function saveChanges(change) {
    if (!workspaceReady) {
      notify(linked ? '서버 기록을 불러오거나 이전한 뒤 저장할 수 있어요.' : 'AI에서 가상 계정을 선택한 뒤 서버에 기록해 주세요.');
      return false;
    }
    try {
      await commitServer(change);
      return true;
    } catch (error) {
      notify(error.message || '서버에 저장하지 못했습니다. 다시 확인해 주세요.');
      return false;
    }
  }

  async function initializeWorkspace(importLocal) {
    try {
      await initializeServer(importLocal
        ? { people: localPeople, events: localEvents, records: localRecords }
        : { people: [], events: [], records: [] });
      notify(importLocal ? '기존 브라우저 기록을 서버에 이전했어요.' : '빈 서버 작업공간을 시작했어요.');
    } catch (error) {
      notify(error.message || '서버 이전에 실패했습니다. 브라우저 기록은 유지됩니다.');
    }
  }

  async function updatePerson(id, patch) {
    const ok = await saveChanges(state => ({ people: state.people.map(person => person.id === id ? { ...person, ...patch } : person) }));
    if (ok) notify('관계 기록을 서버에 저장했어요.');
    return ok;
  }

  async function updateEvent(id, patch) {
    const target = events.find(event => event.id === id);
    const ok = await saveChanges(state => ({ events: state.events.map(event => event.id === id ? { ...event, ...patch } : event) }));
    if (ok) {
      if (target?.owner === 'me' && user) mutate(state => updateSharedEvent(state, user.username, { ...target, ...patch }));
      notify('일정을 서버에 저장했어요.');
    }
    return ok;
  }

  async function saveEvent(values) {
    if (values.owner === 'me') {
      const { shareScope, shareMessage, ...rest } = values;
      const created = { ...rest, id: crypto.randomUUID() };
      if (!await saveChanges(state => ({ events: [...state.events, created] }))) return;
      if (shareScope && shareScope !== 'private' && user) {
        setModal({ type: 'share', id: created.id, event: created, scope: shareScope, message: shareMessage });
        notify('내 경조사를 등록했어요. 이제 보낼 친구를 골라 주세요.');
      } else {
        setModal(null);
        notify('내 경조사를 서버에 등록했어요.');
      }
      return;
    }
    let personId = values.personId;
    let createdPerson = null;
    if (!personId && values.personName) {
      const existing = people.find(person => person.name === values.personName.trim());
      personId = existing?.id || crypto.randomUUID();
      if (!existing) createdPerson = { id: personId, name: values.personName.trim(), relation: '기타', group: '', importance: '보통', lastMet: '', memo: '', interactions: [] };
    }
    const { personName, ...event } = values;
    const created = { ...event, personId, id: crypto.randomUUID() };
    if (!await saveChanges(state => ({
      people: createdPerson ? [...state.people, createdPerson] : state.people,
      events: [...state.events, created],
    }))) return;
    setModal(null);
    notify('일정을 서버에 등록했어요.');
  }

  async function savePerson(values) {
    const created = { ...values, id: crypto.randomUUID() };
    if (!await saveChanges(state => ({ people: [...state.people, created] }))) return;
    setModal(null);
    notify('새로운 인연을 서버에 등록했어요.');
  }

  async function saveRecord(values) {
    const id = modal?.recordId;
    if (id && !records.some(record => record.id === id)) { notify('수정할 기록을 찾을 수 없어요.'); return; }
    const newId = id || crypto.randomUUID();
    if (!await saveChanges(state => ({
      records: id
        ? state.records.map(record => record.id === id ? { ...values, id } : record)
        : [...state.records, { ...values, id: newId }],
    }))) return;
    setModal(null);
    notify(id ? '금액 기록을 서버에서 수정했어요.' : '주고받은 마음을 서버에 기록했어요.');
  }

  async function deleteRecord(id) {
    const ok = await saveChanges(state => ({ records: state.records.filter(record => record.id !== id) }));
    if (ok) notify('금액 기록을 서버에서 삭제했어요.');
    return ok;
  }

  async function importRecords(plan) {
    try {
      const added = materializeImport(plan, () => crypto.randomUUID(), records);
      if (!await saveChanges(state => ({
        records: [...state.records, ...added.records],
        people: added.people.length ? [...state.people, ...added.people] : state.people,
      }))) return false;
      notify(added.records.length + '건을 서버에 가져왔어요.' + (added.people.length ? ' 새 인맥 ' + added.people.length + '명도 등록했어요.' : ''));
      return true;
    } catch (error) {
      notify(error.message || 'CSV를 다시 확인해 주세요.');
      return false;
    }
  }
  // 로그인 계정마다 마지막으로 고른 AI 프로필을 기억했다가 로그인하면 자동으로 선택한다.
  const profileSync = useRef({ user: '', target: null });
  useEffect(() => {
    const name = user?.username || '';
    const previous = profileSync.current.user;
    const linked = name ? (readStored(PROFILE_LINKS_KEY, {})[name] || '') : '';
    profileSync.current = { user: name, target: name ? linked : null };
    if (name && linked !== sharedInbox.userId) sharedInbox.selectUser(linked);
    if (!name && previous && sharedInbox.userId) sharedInbox.selectUser('');
  }, [user?.username]);
  useEffect(() => {
    const { user: name, target } = profileSync.current;
    if (!name || name !== user?.username) return;
    if (target !== null && sharedInbox.userId !== target) return; // 전환 중
    profileSync.current.target = null;
    if (!sharedInbox.userId) return;
    try { const links = readStored(PROFILE_LINKS_KEY, {}); if (links[name] !== sharedInbox.userId) writeStored(PROFILE_LINKS_KEY, { ...links, [name]: sharedInbox.userId }); } catch { /* 저장 공간이 없으면 연결만 생략 */ }
  }, [sharedInbox.userId, user?.username]);
  // ---- 마음결 친구 · 일정 공유 ----
  const [social, setSocial] = useState(loadSocial);
  const [members, setMembers] = useState(readMembers);
  useEffect(() => {
    const sync = () => { setSocial(loadSocial()); setMembers(readMembers()); };
    const onStorage = event => { if (!event.key || event.key === SOCIAL_KEY || event.key === ACCOUNTS_KEY) sync(); };
    window.addEventListener(SOCIAL_EVENT, sync); window.addEventListener('storage', onStorage);
    return () => { window.removeEventListener(SOCIAL_EVENT, sync); window.removeEventListener('storage', onStorage); };
  }, []);
  useEffect(() => { setMembers(readMembers()); }, [user, modal?.type]);
  function mutate(change, message, onError) {
    try { mutateSocial(change); if (message) notify(message); return true; }
    catch (error) { const text = error?.message || '저장하지 못했어요. 브라우저 저장 공간을 확인해 주세요.'; if (onError) onError(text); else notify(text); return false; }
  }
  // 받은 일정은 개인정보라 로그인한 사람에게만 보여 준다.
  const receivedItems = useMemo(() => !user ? [] : buildReceivedItems({ social, me: user?.username || '', notices: sharedInbox.items, profileId: sharedInbox.userId, events, members, people, today }), [social, user, sharedInbox.items, sharedInbox.userId, events, members, people, today]);
  const newReceivedCount = receivedItems.filter(item => item.status === 'new').length;
  async function addToCalendar(item) {
    const existing = events.find(event => event.source?.key === item.key);
    if (existing) { openEvent(existing); return; }
    const person = people.find(entry => item.person.linkedUsername && entry.linkedUsername === item.person.linkedUsername)
      || people.find(entry => entry.name === item.person.name);
    const personId = person?.id || crypto.randomUUID();
    const createdPerson = !person ? {
      id: personId, name: item.person.name, relation: item.person.relation || '기타',
      group: item.person.group || '', importance: '보통', lastMet: '',
      memo: item.kind === 'friend' ? '마음결 친구' : '', interactions: [],
      ...(item.person.linkedUsername ? { linkedUsername: item.person.linkedUsername } : {}),
    } : null;
    const id = crypto.randomUUID();
    if (!await saveChanges(state => ({
      people: createdPerson ? [...state.people, createdPerson] : state.people,
      events: [...state.events, { ...itemToEvent(item, personId), id }],
    }))) return;
    mutate(state => setReceipt(state, user?.username, item.key, { status: 'added', eventId: id }));
    notify('받은 일정을 서버 달력에 추가했어요.');
  }
  function hideItem(item) { mutate(state => setReceipt(state, user?.username, item.key, { status: 'hidden' }), '받은 일정에서 숨겼어요.'); }
  // 프로필(서버)에서 다른 계정에 대해 기록한 중요도 — 받은 일정 순서에만 쓰인다.
  const [serverPriorities, setServerPriorities] = useState({});
  useEffect(() => {
    setServerPriorities({});
    if (!user || !sharedInbox.userId) return;
    const controller = new AbortController();
    demoApi('/relationship-priorities', { userId: sharedInbox.userId, signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setServerPriorities(Object.fromEntries((result.items || []).map(item => [item.target_user_id, item]))); })
      .catch(() => {});
    return () => controller.abort();
  }, [user?.username, sharedInbox.userId]);
  async function saveServerPriority(targetUserId, body) {
    try {
      const saved = await demoApi(`/relationship-priorities/${encodeURIComponent(targetUserId)}`, { userId: sharedInbox.userId, method: 'PUT', body });
      setServerPriorities(current => ({ ...current, [targetUserId]: saved }));
      sharedInbox.refresh();
      notify('중요도를 저장했어요. 받은 일정 순서에 반영했어요.');
      return true;
    } catch (error) { notify(error.message || '중요도를 저장하지 못했어요.'); return false; }
  }
  async function addLinkedPerson({ name, relation, linkedUsername }) {
    const created = { id: crypto.randomUUID(), name, relation: relation || '친구', group: '마음결 친구', importance: '보통', lastMet: '', memo: '', interactions: [], linkedUsername };
    const ok = await saveChanges(state => ({ people: [...state.people, created] }));
    if (ok) notify(`${name}님을 서버 인맥에 추가했어요.`);
    return ok;
  }
  const socialValue = {
    user, social, members, mutate, notify, receivedItems, sharedInbox, addToCalendar, hideItem,
    people, updatePerson, addLinkedPerson, serverPriorities, saveServerPriority,
    requireLogin: mode => setModal({ type: mode === 'signup' ? 'signup' : 'login' }),
    openEvent: id => { setNotificationsOpen(false); setModal({ type: 'eventDetail', id }); },
    goFindFriends: () => { setModal(null); setPeopleTab({ tab: 'find', nonce: Date.now() }); navigate('people'); },
  };
  function openEvent(event) { setNotificationsOpen(false); setModal({ type: 'eventDetail', id: event.id }); }
  function downloadCalendar(event) { const blob = new Blob([toICS(event)], { type: 'text/calendar;charset=utf-8' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${event.title}.ics`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); notify('캘린더 파일을 저장했어요. 캘린더 앱에서 열어 주세요.'); }
  async function changeBrowserNotifications(enabled) {
    if (!enabled) { setNotificationSettings({ browser: false }); return; }
    if (typeof Notification === 'undefined') { notify('이 브라우저는 시스템 알림을 지원하지 않아요.'); return; }
    try { const permission = await Notification.requestPermission(); setNotificationSettings({ browser: permission === 'granted' }); notify(permission === 'granted' ? '앱이 열려 있을 때 행사 전 알림을 보내드릴게요.' : '브라우저 알림 권한을 허용하면 사용할 수 있어요.'); } catch { notify('브라우저 설정에서 알림 권한을 확인해 주세요.'); }
  }
  const selectedEvent = modal?.type === 'eventDetail' ? events.find(event => event.id === modal.id) : null;
  const shareEvent = modal?.type === 'share' ? events.find(event => event.id === modal.id) || modal.event : null;
  const allNoticeIds = [...notices.map(notice => notice.id), ...receivedItems.map(item => receivedReadId(item, sharedInbox.userId))];
  const unreadCount = allNoticeIds.filter(id => !readIds.includes(id)).length;

  const renderNavigationItem = item => <button key={item.id} aria-label={item.label} title={item.label} className={`nav-item ${page === item.id ? 'active' : ''} ${item.id === 'ai' ? 'ai-nav' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} size={20} /><span>{item.label}</span>{item.id === 'ai' && <span className="nav-ai-label">AI</span>}{page === item.id && <span className="nav-active-dot" />}</button>;

  return <SocialContext.Provider value={socialValue}><div className={`app ${dark ? 'is-somber' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    {menuOpen && <div className="sidebar-scrim" onClick={() => setMenuOpen(false)} />}
    <aside id="main-sidebar" className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`} inert={isMobile && !menuOpen ? true : undefined}>
      <div className="sidebar-header"><button className="brand" onClick={() => navigate('home')} aria-label="마음결 홈"><span className="brand-mark"><Icon name="HeartHandshake" size={24} /></span><span>마음결<small>마음과 마음을 잇다</small></span></button><button className="icon-button desktop-sidebar-toggle" aria-label={sidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기"} aria-controls="main-sidebar" aria-expanded={!sidebarCollapsed} onClick={() => setSidebarCollapsed(value => !value)}><Icon name="Menu" /></button><button className="icon-button sidebar-mobile-close" aria-label="메뉴 닫기" onClick={() => setMenuOpen(false)}><Icon name="X" size={18} /></button></div>
      <div className="sidebar-label">나의 공간</div>
      <nav className="main-nav" aria-label="주 메뉴">{navigation.filter(item => item.id !== 'ai').map(renderNavigationItem)}</nav>
      <div className="sidebar-bottom"><nav className="ai-nav-group" aria-label="AI 메뉴">{navigation.filter(item => item.id === 'ai').map(renderNavigationItem)}</nav><div className="sidebar-footer">기록으로 이어지는 우리 사이</div></div>
    </aside>
    <div className="app-content">
      <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" aria-controls="main-sidebar" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)} aria-label="메뉴 열기"><Icon name="Menu" /></button></div><div className="topbar-actions"><span className="today-label"><span />{hasUrgentFuneral ? '조용히 위로를 전할 때예요' : dark ? '차분하게 마음을 살피는 하루예요' : '마음을 챙기기 좋은 하루예요'}</span><div className="theme-control"><button className="theme-toggle" aria-label="화면 분위기 설정" aria-expanded={themeOpen} onClick={() => { setThemeOpen(!themeOpen); setAccountOpen(false); }}><Icon name={dark ? 'Moon' : 'Sun'} size={15} /><span>{themeMode === 'auto' ? '자동 분위기' : dark ? '차분한 분위기' : '따뜻한 분위기'}</span><Icon name="ChevronDown" size={12} /></button>{themeOpen && <><div className="popover-scrim" onClick={() => setThemeOpen(false)} /><div className="theme-popover"><strong>마음에 맞는 분위기</strong>{[{ value: 'auto', name: '상황에 따라 자동', icon: 'Monitor', text: '3일 이내 조사가 있으면 차분하게' }, { value: 'light', name: '따뜻한 마음', icon: 'Sun', text: '한지 아이보리와 쪽빛' }, { value: 'dark', name: '차분한 마음', icon: 'Moon', text: '깊은 먹빛으로 전하는 위로' }].map(item => <button key={item.value} onClick={() => { setThemeMode(item.value); setThemeOpen(false); }}><Icon name={item.icon} size={17} /><span>{item.name}<small>{item.text}</small></span>{themeMode === item.value && <Icon name="Check" size={16} />}</button>)}</div></>}</div><span className="topbar-divider" /><button className="notification-trigger icon-button" aria-label={`알림 ${unreadCount}개`} onClick={() => setNotificationsOpen(true)}><Icon name="Bell" size={20} />{unreadCount > 0 && <span className="notification-dot" />}</button><div className="account-control"><button className="topbar-avatar" aria-label="계정 관리" aria-expanded={accountOpen} onClick={() => { setAccountOpen(!accountOpen); setThemeOpen(false); }}><Icon name="UserRound" size={17} /></button>{accountOpen && <><div className="popover-scrim" onClick={() => setAccountOpen(false)} /><div className="account-popover">{user ? <><strong>{user.name}님</strong><small>@{user.username || user.email}{user.workplace ? ` · ${user.workplace}` : ''}</small><button onClick={() => { setAccountOpen(false); setModal({ type: 'profile' }); }}><Icon name="UserRound" size={16} />정보 수정</button><button onClick={() => { setUser(null); setAccountOpen(false); notify('로그아웃했어요.'); }}><Icon name="LogOut" size={16} />로그아웃</button></> : <><strong>나의 마음 기록</strong><button onClick={() => { setAccountOpen(false); setModal({type:'login'}); }}><Icon name="LogIn" size={16} />로그인</button><button onClick={() => { setAccountOpen(false); setModal({type:'signup'}); }}><Icon name="UserPlus" size={16} />회원가입</button></>}</div></>}</div></div></header>
      <main id="main" className={`main-content ${page === 'home' ? 'home-main' : ''}`} key={page}>
        <section className="card" aria-live="polite" style={{ marginBottom: 12, padding: 12 }}>
          {!linked
            ? <p>서버 기록을 사용하려면 마음결 AI에서 가상 계정을 선택해 주세요. 현재 인맥·장부는 기존 브라우저 백업 보기이며 새 기록은 저장되지 않습니다.</p>
            : workspace.owner !== sharedInbox.userId || workspace.status === 'loading'
              ? <p>서버 인맥·일정·장부를 불러오는 중입니다.</p>
              : workspace.status === 'migration'
              ? <><p>선택한 가상 계정의 서버 기록이 비어 있습니다. 브라우저 자료를 이전하거나 빈 공간에서 시작하세요. 브라우저 원본은 삭제하지 않습니다.</p>
                <button className="button button-primary" onClick={() => initializeWorkspace(true)}>기존 브라우저 기록 서버로 이전</button>
                <button className="button button-secondary" onClick={() => initializeWorkspace(false)}>빈 서버 공간 시작</button></>
              : workspace.status === 'error'
                  ? <p role="alert">서버 기록 조회 실패: {workspace.error}. 저장하지 말고 서버 연결을 확인해 주세요.</p>
                  : <p>서버 작업공간 연결됨 · 가상 계정 {sharedInbox.userId} · 친밀도·장부는 AI 추천과 같은 SQLite 기록을 사용합니다.</p>}
        </section>
        {page === 'home' && <HomePage people={people} events={events} records={records} upcoming={upcoming} today={today} onAddEvent={() => setModal({ type: 'event' })} onOpenEvent={openEvent} navigate={navigate} notify={notify} />}
        {page === 'schedule' && <SchedulePage events={events} people={people} onAddEvent={() => setModal({ type: 'event' })} onOpenEvent={openEvent} onUpdateEvent={updateEvent} onOpenReceived={() => setModal({ type: 'received' })} receivedCount={newReceivedCount} />}
        {page === 'people' && <PeoplePage key={peopleTab.nonce} initialTab={peopleTab.tab} people={people} events={events} records={records} onAddPerson={() => setModal({ type: 'person' })} onUpdatePerson={updatePerson} onAddRecord={id => setModal({ type: 'record', personId: id })} />}
        {page === 'ledger' && <LedgerPage people={people} events={events} records={records} onAddRecord={() => setModal({ type: 'record' })} onEditRecord={id => setModal({type:'record', recordId:id})} onDeleteRecord={deleteRecord} onImportRecords={importRecords} notify={notify} />}
        {page === 'guide' && <EtiquettePage />}
        {page === 'ai' && <AIPage />}
        {page !== 'home' && <footer className="page-footer"><span>마음결<span className="footer-separator">·</span>기억하고, 연결하고, 마음을 전해요.</span></footer>}
      </main>
    </div>
    {modal?.type === 'event' && <EventForm people={people} user={user} onSave={saveEvent} onClose={() => setModal(null)} />}
    {shareEvent && <ShareEventModal key={shareEvent.id} event={shareEvent} initialScope={modal.scope} initialMessage={modal.message} onClose={() => setModal(modal.back ? { type: 'eventDetail', id: shareEvent.id } : null)} />}
    {modal?.type === 'received' && <ReceivedScheduleDialog initialTab={modal.tab || 'friend'} onClose={() => setModal(null)} />}
    {modal?.type === 'person' && <PersonForm onSave={savePerson} onClose={() => setModal(null)} />}
    {modal?.type === 'record' && <RecordForm key={modal.recordId || 'new'} initialRecord={records.find(record => record.id === modal.recordId) || null} people={people} events={events} initialPersonId={modal.personId || ''} initialEventId={modal.eventId || ''} onSave={saveRecord} onClose={() => setModal(null)} />}
    {modal?.type === 'profile' && user && <ProfileEditModal user={user} onClose={() => setModal(null)} onSave={(profile, passwordChanged) => { setUser(profile); setModal(null); notify(passwordChanged ? '비밀번호와 내 정보를 저장했어요.' : '내 정보를 저장했어요.'); }} />}
    {(modal?.type === 'login' || modal?.type === 'signup') && <AuthModal key={modal.type} mode={modal.type} onClose={() => setModal(null)} onSwitch={type => setModal({ type })} onSuccess={profile => {
        if (profile.username === TEST_USERNAME) {
          seedTestSocial();
          writeStored(PROFILE_LINKS_KEY, { ...readStored(PROFILE_LINKS_KEY, {}), [TEST_USERNAME]: TEST_PROFILE_ID });
          setDemoAccount(TEST_PROFILE_ID);
        }
        setUser(profile); setModal(null); notify(`${profile.name}님, 마음결에 오신 걸 환영해요.`);
      }} />}
    {selectedEvent && <EventDetail event={selectedEvent} person={people.find(person => person.id === selectedEvent.personId)} today={today} onClose={() => setModal(null)} onUpdate={patch => updateEvent(selectedEvent.id, patch)} onShare={() => user ? setModal({ type: 'share', id: selectedEvent.id, back: true }) : setModal({ type: 'login' })} onDelete={async () => { const ok = await saveChanges(state => ({ events: state.events.filter(event => event.id !== selectedEvent.id), records: state.records.map(record => record.eventId === selectedEvent.id ? { ...record, eventId: '' } : record) })); if (!ok) return; if (selectedEvent.owner === 'me' && user) mutate(state => removeShare(state, user.username, selectedEvent.id)); setModal(null); notify('일정을 서버에서 삭제했어요. 금액 기록은 유지했어요.'); }} onDownload={() => downloadCalendar(selectedEvent)} onRecord={() => setModal({ type: 'record', personId: selectedEvent.personId, eventId: selectedEvent.id })} onAI={() => { setAiPersonId(selectedEvent.personId); setModal(null); navigate('ai'); }} />}
    {notificationsOpen && <Notifications notices={notices} sharedInbox={sharedInbox} receivedItems={receivedItems} loggedIn={!!user} onLogin={mode => { setNotificationsOpen(false); setModal({ type: mode === 'signup' ? 'signup' : 'login' }); }} onAddToCalendar={addToCalendar} onOpenReceived={() => { setNotificationsOpen(false); setModal({ type: 'received' }); }} readIds={readIds} onRead={id => setReadIds(current => [...new Set([...current, id])])} onReadAll={() => setReadIds(current => [...new Set([...current, ...allNoticeIds])])} onClose={() => setNotificationsOpen(false)} onOpenEvent={openEvent} onOpenAI={() => { setNotificationsOpen(false); navigate('ai'); }} browserEnabled={notificationSettings.browser} onBrowserChange={changeBrowserNotifications} />}
    {toast && <div className="toast" role="status"><Icon name="CheckCircle2" size={18} />{toast}</div>}
  </div></SocialContext.Provider>;
}

function HomePage({ people, events, records, upcoming, today, onAddEvent, onOpenEvent, navigate, notify }) {
  const [filter, setFilter] = useState('전체');
  const visible = upcoming.filter(event => filter === '전체' || (filter === '조사' ? event.type === '장례식' : event.type !== '장례식')).slice(0, 2);
  return <div className={`home-page ${filter === '조사' ? 'mood-somber' : ''}`}>
    <div className="page-heading"><div><span className="eyebrow"><span className="tiny-dot" />{fullDate(today)}</span><h1>챙길 마음을, 한눈에.</h1><p>일정부터 인연, 주고받은 마음까지 함께 기억해요.</p></div><div className="page-heading-actions"><button className="button button-primary" onClick={onAddEvent}><Icon name="Plus" size={17} />일정 등록</button></div></div>
    <div className="home-overview"><section className="card upcoming-card"><div className="section-heading"><h2>다가오는 소중한 날<span className="count-badge">{upcoming.length}</span></h2><button className="text-button" onClick={() => navigate('schedule')}>전체 보기<Icon name="ChevronRight" size={14} /></button></div><div className="upcoming-filters">{['전체', '경사', '조사'].map(item => <button className={`filter-chip ${filter === item ? 'active' : ''}`} key={item} onClick={() => setFilter(item)}>{item}</button>)}<span><i className="legend-dot" />{filter === '조사' ? '조용히, 정중하게 마음을 전해요' : '잊지 않도록 함께 챙겨요'}</span></div><div className="event-list">{visible.length ? visible.map(event => <EventRow key={event.id} event={event} person={people.find(person => person.id === event.personId)} today={today} onClick={() => onOpenEvent(event)} />) : <EmptyState icon="CalendarCheck" title={filter === '조사' ? '예정된 조사가 없어요' : '다가오는 일정이 없어요'} description="소중한 사람의 특별한 날을 등록해 보세요." />}</div></section>
    <AIPage people={people} events={events} records={records} today={today} notify={notify} embedded /></div>
  </div>;
}

function EventRow({ event, person, today, onClick }) {
  const days = daysUntil(event.date, today);
  const sorrow = event.type === '장례식';
  return <button className={`event-row ${occasionClass(event.type)}`} onClick={onClick}><span className={`event-date ${occasionClass(event.type)}`}><small>{Number(event.date.slice(5, 7))}월</small><strong>{event.date.slice(8)}</strong></span><span className="event-row-content"><span className="event-title">{event.title}<span className={`badge ${occasionClass(event.type)}`}>{event.type}</span></span><span className="event-meta"><Icon name="Clock3" size={12} />{new Date(`${event.date}T12:00:00`).toLocaleDateString('ko-KR', { weekday: 'short' })}요일 {event.time || '시간 미정'}<span className="event-meta-location"><i />{event.location || '장소 미정'}</span></span><span className="event-relationship">{event.owner === 'me' ? <>내 경조사</> : <>{person?.relation || '인연'} · {person?.group || '소속 미지정'}<i /><span className={`att-pill ${attendanceClass(event.attendance)}`}>{event.attendance || '참석 여부 선택'}</span></>}</span></span><span className={`d-day ${days <= 3 ? 'urgent' : ''}`}>{ddLabel(days)}</span><Icon className="event-row-arrow" name="ChevronRight" size={15} /></button>;
}

function EventDetail({ event, person, today, onClose, onUpdate, onDelete, onDownload, onRecord, onAI, onShare }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ title: event.title, date: event.date, time: event.time, location: event.location, memo: event.memo || '' });
  const [confirmDelete, setConfirmDelete] = useState(false);
  return <Modal title="마음을 챙길 일정" subtitle="소중한 날을 위해 차근차근 준비해요." onClose={onClose}>
    <div className={`event-detail-summary ${occasionClass(event.type)}`}><span className={`detail-event-icon ${occasionClass(event.type)}`}><Icon name={eventIcon(event.type)} size={25} /></span><div><span className={`badge ${occasionClass(event.type)}`}>{event.type} · {ddLabel(daysUntil(event.date, today))}</span><h3>{event.title}</h3><p>{event.owner === 'me' ? '내 경조사' : `${person?.name} · ${person?.relation} · ${person?.group || '소속 그룹 없음'}`}{event.source?.from ? ` · ${event.source.from}님이 보낸 일정` : ''}</p></div><button className="icon-button" aria-label="일정 정보 수정" onClick={() => setEditing(!editing)}><Icon name="Pencil" size={17} /></button></div>
    {editing ? <form className="detail-edit-form" onSubmit={async e => { e.preventDefault(); if (await onUpdate(draft)) setEditing(false); }}><label className="field">일정 이름<input className="input" required value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label><div className="form-grid"><label className="field">날짜<input className="input" required type="date" value={draft.date} onChange={e => setDraft({ ...draft, date: e.target.value })} /></label><label className="field">시간<input className="input" type="time" value={draft.time} onChange={e => setDraft({ ...draft, time: e.target.value })} /></label></div><label className="field">장소<input className="input" value={draft.location} onChange={e => setDraft({ ...draft, location: e.target.value })} /></label><label className="field">기억할 메모<textarea className="input" rows={2} value={draft.memo} onChange={e => setDraft({ ...draft, memo: e.target.value })} /></label><button className="button button-primary" type="submit">변경사항 저장</button></form> : <div className="event-detail-info"><div><Icon name="CalendarDays" size={17} /><span>{fullDate(event.date)} · {event.time || '시간 미정'}</span></div><div><Icon name="MapPin" size={17} /><span>{event.location || '장소 미정'}</span></div>{event.memo && <div><Icon name="NotebookPen" size={17} /><span>{event.memo}</span></div>}</div>}
    {event.owner === 'me' && <ShareStatus event={event} onShare={onShare} />}
    <div className="event-detail-controls">{event.owner !== 'me' && <label className="field">참석 여부<select className="input" value={event.attendance} onChange={e => onUpdate({ attendance: e.target.value })}><option value="" disabled>참석 여부 선택</option>{['참석', '불참'].map(value => <option key={value}>{value}</option>)}</select></label>}<label className="field">행사 전 알림<select className="input" value={event.reminderDays} onChange={e => onUpdate({ reminderDays: Number(e.target.value) })}><option value={0}>행사 당일</option><option value={1}>1일 전부터</option><option value={3}>3일 전부터</option><option value={7}>7일 전부터</option></select></label></div>
    <div className="event-detail-ai"><Icon name="Sparkles" size={19} /><div><strong>어떤 마음을 전하면 좋을까요?</strong><p>지난 금액과 관계 기록을 함께 참고해 보세요.</p></div><button className="icon-button" aria-label="마음결 AI 열기" onClick={onAI}><Icon name="ArrowUpRight" size={19} /></button></div><div className="event-detail-actions"><button className="button button-secondary" onClick={onDownload}><Icon name="Download" size={16} />캘린더 저장</button><button className="button button-primary" onClick={onRecord}><Icon name="HandHeart" size={16} />금액 기록</button></div><button className={`delete-event ${confirmDelete ? 'confirm' : ''}`} onClick={() => confirmDelete ? onDelete() : setConfirmDelete(true)}>{confirmDelete ? '한 번 더 누르면 일정을 삭제해요' : '일정 삭제'}</button>
  </Modal>;
}
