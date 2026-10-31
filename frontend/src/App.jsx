import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import { daysUntil, formatMoney, toICS, normalizeAttendance } from './domain.js';
import { EventForm, PersonForm, RecordForm, AuthModal, ProfileEditModal } from './Forms.jsx';
import PeoplePage from './PeoplePage.jsx';
import LedgerPage from './LedgerPage.jsx';
import SchedulePage from './SchedulePage.jsx';
import AIPage from './IntegratedAIPage.jsx';
import EtiquettePage from './EtiquettePage.jsx';
import Notifications, { useSharedNoticeInbox, receivedReadId } from './Notifications.jsx';
import { SocialContext, ShareEventModal, ShareStatus, ReceivedScheduleDialog } from './Social.jsx';
import { setReceipt, updateSharedEvent, removeShare } from './services/socialStore.js';
import { buildReceivedItems, itemToEvent } from './services/receivedItems.js';
import { demoApi } from './services/demoApi.js';
import { materializeImport } from './ledgerCsv.js';
import { useServerWorkspace } from './services/serverWorkspace.js';
import { normalizePerson } from './relationships.js';
import { occasionClass, attendanceClass } from './occasion.js';

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

export default function App() {
  const [user, setUser] = useState(null);
  const [themeMode, setThemeMode] = useState('auto');
  const [readIds, setReadIds] = useState([]);
  const [identity, setIdentity] = useState({ username: '', userId: '', error: '' });
  const serverUserId = user?.username && identity.username === user.username ? identity.userId : '';
  const sharedInbox = useSharedNoticeInbox(serverUserId);
  const { state: workspace, commit: commitServer, initialize: initializeServer } = useServerWorkspace(serverUserId);
  const linked = Boolean(serverUserId);
  const workspaceReady = linked && workspace.owner === serverUserId && workspace.status === 'ready';
  const people = workspaceReady ? workspace.snapshot.people.map(normalizePerson) : [];
  const events = workspaceReady ? workspace.snapshot.events.map(event => ({ ...event, attendance: normalizeAttendance(event.attendance) })) : [];
  const records = workspaceReady ? workspace.snapshot.records : [];
  const [notificationSettings, setNotificationSettings] = useState({ browser: false });
  const [page, setPage] = useState(() => navigation.some(item => item.id === location.hash.slice(1)) ? location.hash.slice(1) : 'home');
  const [aiPersonId, setAiPersonId] = useState('');
  const [peopleTab, setPeopleTab] = useState({ tab: 'people', nonce: 0 });
  const [modal, setModal] = useState(null);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches);
  useEffect(() => { const media = window.matchMedia('(max-width: 760px)'); const sync = () => { setIsMobile(media.matches); setMenuOpen(false); }; media.addEventListener('change', sync); return () => media.removeEventListener('change', sync); }, []);
  useEffect(() => { const close = e => { if(e.key === 'Escape') { setMenuOpen(false); setThemeOpen(false); setAccountOpen(false); } }; document.addEventListener('keydown', close); return () => document.removeEventListener('keydown', close); }, []);
  const [toast, setToast] = useState('');
  const [today, setToday] = useState(koreanDate);
  const toastTimer = useRef(null);
  const workspaceInitialized = useRef(new Set());
  const socialSnapshot = useRef(null);
  const socialQueue = useRef(Promise.resolve());
  const upcoming = useMemo(() => events.filter(event => daysUntil(event.date, today) >= 0).sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time)), [events, today]);
  const hasUrgentFuneral = upcoming.some(event => event.type === '장례식' && daysUntil(event.date, today) <= 3);
  const dark = themeMode === 'dark' || themeMode === 'auto' && hasUrgentFuneral;
  const notices = useMemo(() => upcoming.filter(event => daysUntil(event.date, today) <= 30).map(event => ({ id: `event-${event.id}-${event.date}`, event, days: daysUntil(event.date, today) })).sort((a, b) => Number(b.event.type === '장례식') - Number(a.event.type === '장례식') || a.days - b.days), [upcoming, today]);

  function notify(message) { setToast(message); clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToast(''), 3500); }

  // 로그인 계정과 화면 설정은 브라우저 저장소가 아니라 서버 세션으로 복원한다.
  useEffect(() => {
    let active = true;
    demoApi('/auth/me').then(result => {
      if (!active) return;
      setUser(result.profile);
      setIdentity({ username: result.profile.username, userId: result.userId, error: '' });
    }).catch(error => { if (active && error.status !== 401) notify(error.message); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setReadIds([]);
    setThemeMode('auto');
    setNotificationSettings({ browser: false });
    setSidebarCollapsed(false);
    if (user) {
      demoApi('/account/preferences').then(pref => {
        if (!active) return;
        setReadIds(pref.readIds || []);
        setThemeMode(pref.theme || 'auto');
        setNotificationSettings(pref.notifications || { browser: false });
        setSidebarCollapsed(Boolean(pref.sidebarCollapsed));
      }).catch(error => { if (active) notify(error.message); });
    }
    return () => { active = false; };
  }, [user?.username]);

  async function savePreference(change) {
    if (!user) return;
    try { await demoApi('/account/preferences', { method: 'PATCH', body: change }); }
    catch (error) { notify(error.message || '설정을 서버에 저장하지 못했습니다.'); }
  }
  function changeTheme(mode) { setThemeMode(mode); savePreference({ theme: mode }); }
  function changeSidebar(value) {
    const next = typeof value === 'function' ? value(sidebarCollapsed) : value;
    setSidebarCollapsed(next);
    savePreference({ sidebarCollapsed: next });
  }
  async function markRead(keys) {
    if (!user || !keys.length) return;
    try {
      const result = await demoApi('/account/read', { method: 'POST', body: { keys } });
      setReadIds(result.readIds || []);
    } catch (error) { notify(error.message); }
  }
  useEffect(() => {
    if (!serverUserId || workspace.status !== 'migration' || workspace.owner !== serverUserId
        || workspaceInitialized.current.has(serverUserId)) return;
    workspaceInitialized.current.add(serverUserId);
    initializeServer({ people: [], events: [], records: [] })
      .catch(error => { workspaceInitialized.current.delete(serverUserId); notify(error.message); });
  }, [serverUserId, workspace.owner, workspace.status, initializeServer]);
  function navigate(id) { setPage(id); location.hash = id; setMenuOpen(false); setThemeOpen(false); setAccountOpen(false); window.scrollTo({ top: 0, behavior: 'instant' }); }
  useEffect(() => { const handler = () => { const id = location.hash.slice(1); if (navigation.some(item => item.id === id)) setPage(id); }; window.addEventListener('hashchange', handler); return () => window.removeEventListener('hashchange', handler); }, []);
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; }, [dark]);
  useEffect(() => { const timer = setInterval(() => setToday(koreanDate()), 30000); return () => { clearInterval(timer); clearTimeout(toastTimer.current); }; }, []);
  useEffect(() => {
    if (!user || !notificationSettings.browser || typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
    const sendReminders = () => {
      upcoming.filter(event => daysUntil(event.date, today) <= Number(event.reminderDays ?? 3)).forEach(event => {
        const key = `maeum-delivered-${event.id}-${event.date}-${today}`;
        demoApi('/account/delivered', { method: 'POST', body: { key } })
          .then(result => {
            if (result.send && Notification.permission === 'granted')
              new Notification(event.type === '장례식' ? '조심스럽게 전하는 소식' : '마음을 전할 날이 다가와요', { body: `${event.title} · ${event.date} ${event.time}`, tag: event.id, icon: '/favicon.svg' });
          }).catch(() => {});

      });
    };
    sendReminders(); const timer = setInterval(sendReminders, 60000); return () => clearInterval(timer);
  }, [user?.username, notificationSettings.browser, upcoming, today]);

  async function saveChanges(change) {
    if (!workspaceReady) {
      notify(linked ? '서버 기록을 불러오거나 이전한 뒤 저장할 수 있어요.' : '로그인 후 서버 계정 연결을 확인해 주세요.');
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

  async function updatePerson(id, patch) {
    const ok = await saveChanges(state => ({ people: state.people.map(person => person.id === id ? { ...person, ...patch } : person) }));
    if (ok) notify('관계 기록을 서버에 저장했어요.');
    return ok;
  }

  async function updateEvent(id, patch) {
    const target = events.find(event => event.id === id);
    const ok = await saveChanges(state => ({ events: state.events.map(event => event.id === id ? { ...event, ...patch } : event) }));
    if (ok) {
      if (target?.owner === 'me' && user) await mutate(state => updateSharedEvent(state, user.username, { ...target, ...patch }));
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
  // 서버 사용자 ID는 로그인·세션 복원 응답에서 받는다. 로그아웃하면 user가 비어 모든 기록이 화면에서 사라진다.
  // ---- 마음결 친구 · 일정 공유 ----
  const [social, setSocial] = useState({ friendships: [], shares: [], receipts: {} });
  const [members, setMembers] = useState([]);
  useEffect(() => {
    let active = true;
    socialSnapshot.current = null;
    socialQueue.current = Promise.resolve();
    setSocial({ friendships: [], shares: [], receipts: {} });
    setMembers([]);
    if (user) {
      demoApi('/account/social').then(result => {
        if (!active) return;
        socialSnapshot.current = { ...result, username: user.username };
        setSocial(result.social);
        setMembers(result.members);
      }).catch(error => { if (active) notify(error.message); });
    }
    return () => { active = false; };
  }, [user?.username]);

  function mutate(change, message, onError) {
    const owner = user?.username;
    const pending = socialQueue.current.then(async () => {
      if (!owner || !socialSnapshot.current || socialSnapshot.current.username !== owner)
        throw new Error('사회관계 서버 연결을 확인해 주세요.');
      const previous = socialSnapshot.current;
      const next = change(previous.social);
      const result = await demoApi('/account/social', {
        method: 'PUT', body: { ...next, revision: previous.revision },
      });
      if (socialSnapshot.current?.username !== owner) return false;
      socialSnapshot.current = { ...result, username: owner };
      setSocial(result.social);
      setMembers(result.members);
      if (message) notify(message);
      return true;
    });
    socialQueue.current = pending.catch(() => {});
    return pending.catch(async error => {
      if (error.message.includes('변경')) {
        try {
          const latest = await demoApi('/account/social');
          if (socialSnapshot.current?.username === owner) {
            socialSnapshot.current = { ...latest, username: owner };
            setSocial(latest.social);
            setMembers(latest.members);
          }
        } catch {}
      }
      const text = error.message || '사회관계 기록을 서버에 저장하지 못했습니다.';
      if (onError) onError(text); else notify(text);
      return false;
    });
  }
  // 받은 일정은 개인정보라 로그인한 사람에게만 보여 준다.
  const receivedItems = useMemo(() => !user || !serverUserId ? [] : buildReceivedItems({ social, me: user.username, notices: sharedInbox.userId === serverUserId ? sharedInbox.items : [], profileId: serverUserId, events, members, people, today }), [social, user, sharedInbox.items, sharedInbox.userId, serverUserId, events, members, people, today]);
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
    await mutate(state => setReceipt(state, user?.username, item.key, { status: 'added', eventId: id }));
    notify('받은 일정을 서버 달력에 추가했어요.');
  }
  async function hideItem(item) { await mutate(state => setReceipt(state, user?.username, item.key, { status: 'hidden' }), '받은 일정에서 숨겼어요.'); }
  // 프로필(서버)에서 다른 계정에 대해 기록한 중요도 — 받은 일정 순서에만 쓰인다.
  const [serverPriorities, setServerPriorities] = useState({});
  useEffect(() => {
    setServerPriorities({});
    if (!user || !serverUserId || sharedInbox.userId !== serverUserId) return;
    const controller = new AbortController();
    demoApi('/relationship-priorities', { userId: serverUserId, signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setServerPriorities(Object.fromEntries((result.items || []).map(item => [item.target_user_id, item]))); })
      .catch(() => {});
    return () => controller.abort();
  }, [user?.username, sharedInbox.userId, serverUserId]);
  async function saveServerPriority(targetUserId, body) {
    try {
      if (!workspaceReady) throw new Error('서버 계정 연결 후 저장할 수 있습니다.');
      const saved = await demoApi(`/relationship-priorities/${encodeURIComponent(targetUserId)}`, { userId: serverUserId, method: 'PUT', body });
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
    if (!enabled) { setNotificationSettings({ browser: false }); savePreference({ notifications: { browser: false } }); return; }
    if (typeof Notification === 'undefined') { notify('이 브라우저는 시스템 알림을 지원하지 않아요.'); return; }
    try { const permission = await Notification.requestPermission(); setNotificationSettings({ browser: permission === 'granted' }); savePreference({ notifications: { browser: permission === 'granted' } }); notify(permission === 'granted' ? '앱이 열려 있을 때 행사 전 알림을 보내드릴게요.' : '브라우저 알림 권한을 허용하면 사용할 수 있어요.'); } catch { notify('브라우저 설정에서 알림 권한을 확인해 주세요.'); }
  }
  const selectedEvent = modal?.type === 'eventDetail' ? events.find(event => event.id === modal.id) : null;
  const shareEvent = modal?.type === 'share' ? events.find(event => event.id === modal.id) || modal.event : null;
  const allNoticeIds = [...notices.map(notice => notice.id), ...receivedItems.map(item => receivedReadId(item, sharedInbox.userId))];
  const unreadCount = allNoticeIds.filter(id => !readIds.includes(id)).length;

  const renderNavigationItem = item => <button key={item.id} aria-label={item.label} title={item.label} className={`nav-item ${page === item.id ? 'active' : ''} ${item.id === 'ai' ? 'ai-nav' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} size={20} /><span>{item.label}</span>{item.id === 'ai' && <span className="nav-ai-label">AI</span>}{page === item.id && <span className="nav-active-dot" />}</button>;

  return <SocialContext.Provider value={socialValue}><div className={`app ${dark ? 'is-somber' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    {menuOpen && <div className="sidebar-scrim" onClick={() => setMenuOpen(false)} />}
    <aside id="main-sidebar" className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`} inert={isMobile && !menuOpen ? true : undefined}>
      <div className="sidebar-header"><button className="brand" onClick={() => navigate('home')} aria-label="마음결 홈"><span className="brand-mark"><Icon name="HeartHandshake" size={24} /></span><span>마음결<small>마음과 마음을 잇다</small></span></button><button className="icon-button desktop-sidebar-toggle" aria-label={sidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기"} aria-controls="main-sidebar" aria-expanded={!sidebarCollapsed} onClick={() => changeSidebar(value => !value)}><Icon name="Menu" /></button><button className="icon-button sidebar-mobile-close" aria-label="메뉴 닫기" onClick={() => setMenuOpen(false)}><Icon name="X" size={18} /></button></div>
      <div className="sidebar-label">나의 공간</div>
      <nav className="main-nav" aria-label="주 메뉴">{navigation.filter(item => item.id !== 'ai').map(renderNavigationItem)}</nav>
      <div className="sidebar-bottom"><nav className="ai-nav-group" aria-label="AI 메뉴">{navigation.filter(item => item.id === 'ai').map(renderNavigationItem)}</nav><div className="sidebar-footer">기록으로 이어지는 우리 사이</div></div>
    </aside>
    <div className="app-content">
      <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" aria-controls="main-sidebar" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)} aria-label="메뉴 열기"><Icon name="Menu" /></button></div><div className="topbar-actions"><span className="today-label"><span />{hasUrgentFuneral ? '조용히 위로를 전할 때예요' : dark ? '차분하게 마음을 살피는 하루예요' : '마음을 챙기기 좋은 하루예요'}</span><div className="theme-control"><button className="theme-toggle" aria-label="화면 분위기 설정" aria-expanded={themeOpen} onClick={() => { setThemeOpen(!themeOpen); setAccountOpen(false); }}><Icon name={dark ? 'Moon' : 'Sun'} size={15} /><span>{themeMode === 'auto' ? '자동 분위기' : dark ? '차분한 분위기' : '따뜻한 분위기'}</span><Icon name="ChevronDown" size={12} /></button>{themeOpen && <><div className="popover-scrim" onClick={() => setThemeOpen(false)} /><div className="theme-popover"><strong>마음에 맞는 분위기</strong>{[{ value: 'auto', name: '상황에 따라 자동', icon: 'Monitor', text: '3일 이내 조사가 있으면 차분하게' }, { value: 'light', name: '따뜻한 마음', icon: 'Sun', text: '한지 아이보리와 쪽빛' }, { value: 'dark', name: '차분한 마음', icon: 'Moon', text: '깊은 먹빛으로 전하는 위로' }].map(item => <button key={item.value} onClick={() => { changeTheme(item.value); setThemeOpen(false); }}><Icon name={item.icon} size={17} /><span>{item.name}<small>{item.text}</small></span>{themeMode === item.value && <Icon name="Check" size={16} />}</button>)}</div></>}</div><span className="topbar-divider" /><button className="notification-trigger icon-button" aria-label={`알림 ${unreadCount}개`} onClick={() => setNotificationsOpen(true)}><Icon name="Bell" size={20} />{unreadCount > 0 && <span className="notification-dot" />}</button><div className="account-control"><button className="topbar-avatar" aria-label="계정 관리" aria-expanded={accountOpen} onClick={() => { setAccountOpen(!accountOpen); setThemeOpen(false); }}><Icon name="UserRound" size={17} /></button>{accountOpen && <><div className="popover-scrim" onClick={() => setAccountOpen(false)} /><div className="account-popover">{user ? <><strong>{user.name}님</strong><small>@{user.username || user.email}{user.workplace ? ` · ${user.workplace}` : ''}</small><button onClick={() => { setAccountOpen(false); setModal({ type: 'profile' }); }}><Icon name="UserRound" size={16} />정보 수정</button><button onClick={async () => {
        try { await demoApi('/auth/logout', { method: 'POST' }); setUser(null); setIdentity({ username: '', userId: '', error: '' }); setAccountOpen(false); notify('로그아웃했어요.'); }
        catch (error) { notify(error.message); }
      }}><Icon name="LogOut" size={16} />로그아웃</button></> : <><strong>나의 마음 기록</strong><button onClick={() => { setAccountOpen(false); setModal({type:'login'}); }}><Icon name="LogIn" size={16} />로그인</button><button onClick={() => { setAccountOpen(false); setModal({type:'signup'}); }}><Icon name="UserPlus" size={16} />회원가입</button></>}</div></>}</div></div></header>
      <main id="main" className={`main-content ${page === 'home' ? 'home-main' : ''}`} key={page}>
        {user && workspace.owner === serverUserId && workspace.status === 'error' && <section className="card" role="alert" style={{ marginBottom: 12, padding: 12 }}>
          <p>서버 기록 조회 실패: {workspace.error}. 저장하지 말고 서버 연결을 확인해 주세요.</p>
        </section>}
        {page === 'home' && <HomePage people={people} events={events} records={records} upcoming={upcoming} today={today} onAddEvent={() => setModal({ type: 'event' })} onOpenEvent={openEvent} navigate={navigate} notify={notify} />}
        {page === 'schedule' && <SchedulePage events={events} people={people} onAddEvent={() => setModal({ type: 'event' })} onOpenEvent={openEvent} onUpdateEvent={updateEvent} onOpenReceived={() => setModal({ type: 'received' })} receivedCount={newReceivedCount} />}
        {page === 'people' && <PeoplePage key={peopleTab.nonce} initialTab={peopleTab.tab} people={people} events={events} records={records} onAddPerson={() => setModal({ type: 'person' })} onUpdatePerson={updatePerson} onAddRecord={id => setModal({ type: 'record', personId: id })} />}
        {page === 'ledger' && <LedgerPage people={people} events={events} records={records} onAddRecord={() => setModal({ type: 'record' })} onEditRecord={id => setModal({type:'record', recordId:id})} onDeleteRecord={deleteRecord} onImportRecords={importRecords} notify={notify} />}
        {page === 'guide' && <EtiquettePage />}
        {page === 'ai' && <AIPage key={serverUserId || 'signed-out'} userId={serverUserId} />}
        {page !== 'home' && <footer className="page-footer"><span>마음결<span className="footer-separator">·</span>기억하고, 연결하고, 마음을 전해요.</span></footer>}
      </main>
    </div>
    {modal?.type === 'event' && <EventForm people={people} user={user} onSave={saveEvent} onClose={() => setModal(null)} />}
    {shareEvent && <ShareEventModal key={shareEvent.id} event={shareEvent} initialScope={modal.scope} initialMessage={modal.message} onClose={() => setModal(modal.back ? { type: 'eventDetail', id: shareEvent.id } : null)} />}
    {modal?.type === 'received' && <ReceivedScheduleDialog initialTab={modal.tab || 'friend'} onClose={() => setModal(null)} />}
    {modal?.type === 'person' && <PersonForm onSave={savePerson} onClose={() => setModal(null)} />}
    {modal?.type === 'record' && <RecordForm key={modal.recordId || 'new'} initialRecord={records.find(record => record.id === modal.recordId) || null} people={people} events={events} initialPersonId={modal.personId || ''} initialEventId={modal.eventId || ''} onSave={saveRecord} onClose={() => setModal(null)} />}
    {modal?.type === 'profile' && user && <ProfileEditModal user={user} onClose={() => setModal(null)} onSave={(profile, passwordChanged) => { setUser(profile); setModal(null); notify(passwordChanged ? '비밀번호와 내 정보를 저장했어요.' : '내 정보를 저장했어요.'); }} />}
    {(modal?.type === 'login' || modal?.type === 'signup') && <AuthModal key={modal.type} mode={modal.type} onClose={() => setModal(null)} onSwitch={type => setModal({ type })} onSuccess={(profile, userId) => {
        setIdentity({ username: profile.username, userId, error: '' });
        setUser(profile); setModal(null); notify(`${profile.name}님, 마음결에 오신 걸 환영해요.`);
      }} />}
    {selectedEvent && <EventDetail event={selectedEvent} person={people.find(person => person.id === selectedEvent.personId)} today={today} onClose={() => setModal(null)} onUpdate={patch => updateEvent(selectedEvent.id, patch)} onShare={() => user ? setModal({ type: 'share', id: selectedEvent.id, back: true }) : setModal({ type: 'login' })} onDelete={async () => { const ok = await saveChanges(state => ({ events: state.events.filter(event => event.id !== selectedEvent.id), records: state.records.map(record => record.eventId === selectedEvent.id ? { ...record, eventId: '' } : record) })); if (!ok) return; if (selectedEvent.owner === 'me' && user) await mutate(state => removeShare(state, user.username, selectedEvent.id)); setModal(null); notify('일정을 서버에서 삭제했어요. 금액 기록은 유지했어요.'); }} onDownload={() => downloadCalendar(selectedEvent)} onRecord={() => setModal({ type: 'record', personId: selectedEvent.personId, eventId: selectedEvent.id })} onAI={() => { setAiPersonId(selectedEvent.personId); setModal(null); navigate('ai'); }} />}
    {notificationsOpen && <Notifications notices={notices} sharedInbox={sharedInbox} receivedItems={receivedItems} loggedIn={!!user} onLogin={mode => { setNotificationsOpen(false); setModal({ type: mode === 'signup' ? 'signup' : 'login' }); }} onAddToCalendar={addToCalendar} onOpenReceived={() => { setNotificationsOpen(false); setModal({ type: 'received' }); }} readIds={readIds} onRead={id => markRead([id])} onReadAll={() => markRead(allNoticeIds)} onClose={() => setNotificationsOpen(false)} onOpenEvent={openEvent} onOpenAI={() => { setNotificationsOpen(false); navigate('ai'); }} browserEnabled={notificationSettings.browser} onBrowserChange={changeBrowserNotifications} />}
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
