import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import { initialPeople, initialEvents, initialRecords } from './data.js';
import { daysUntil, formatMoney, toICS, normalizeAttendance } from './domain.js';
import { EventForm, PersonForm, RecordForm, AuthModal, ProfileEditModal } from './Forms.jsx';
import PeoplePage from './PeoplePage.jsx';
import LedgerPage from './LedgerPage.jsx';
import SchedulePage from './SchedulePage.jsx';
import AIPage from './IntegratedAIPage.jsx';
import EtiquettePage from './EtiquettePage.jsx';
import Notifications, { useSharedNoticeInbox, sharedNoticeId } from './Notifications.jsx';
import { materializeImport } from './ledgerCsv.js';
import { STORAGE_KEYS, readStored, writeStored, commitWorkspace } from './services/workspaceStorage.js';
import { normalizePerson } from './relationships.js';
import { occasionClass, attendanceClass } from './occasion.js';
import { DEMO_ACCOUNT_EVENT, getDemoAccount, setDemoAccount } from './services/demoAccount.js';

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

function useStored(key, initial, normalize = value => value) {
  const [value, setValue] = useState(() => readStored(key, initial, normalize));
  useEffect(() => { try { writeStored(key, value); } catch { /* Private mode can disable storage. The current session still works. */ } }, [key, value]);
  return [value, setValue];
}

export default function App() {
  const [people, setPeople] = useStored(STORAGE_KEYS.people, initialPeople, items => items.map(normalizePerson));
  const [events, setEvents] = useStored(STORAGE_KEYS.events, initialEvents, items => items.map(event => ({ ...event, attendance: normalizeAttendance(event.attendance) })));
  const [records, setRecords] = useStored(STORAGE_KEYS.records, initialRecords);
  const [themeMode, setThemeMode] = useStored(STORAGE_KEYS.theme, 'auto');
  const [user, setUser] = useStored(STORAGE_KEYS.session, null);
  const [readIds, setReadIds] = useStored(STORAGE_KEYS.readIds, []);
  const sharedInbox = useSharedNoticeInbox();
  const [notificationSettings, setNotificationSettings] = useStored(STORAGE_KEYS.notifications, { browser: false });
  const [demoUserId, setDemoUserId] = useState(getDemoAccount);
  useEffect(() => { const sync = () => setDemoUserId(getDemoAccount()); window.addEventListener(DEMO_ACCOUNT_EVENT, sync); return () => window.removeEventListener(DEMO_ACCOUNT_EVENT, sync); }, []);
  const [page, setPage] = useState(() => navigation.some(item => item.id === location.hash.slice(1)) ? location.hash.slice(1) : 'home');
  const [aiPersonId, setAiPersonId] = useState('');
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
  const allNoticeIds = [...notices.map(notice => notice.id), ...sharedInbox.items.map(item => sharedNoticeId(sharedInbox.userId, item.notice.id))];
  const unreadCount = allNoticeIds.filter(id => !readIds.includes(id)).length;

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

  function updatePerson(id, patch) { setPeople(current => current.map(person => person.id === id ? { ...person, ...patch } : person)); notify('관계 기록을 저장했어요.'); }
  function updateEvent(id, patch) { setEvents(current => current.map(event => event.id === id ? { ...event, ...patch } : event)); notify('일정을 업데이트했어요.'); }
  function saveEvent(values) {
    let personId = values.personId;
    if (!personId && values.personName) {
      const existing = people.find(person => person.name === values.personName.trim());
      personId = existing?.id || crypto.randomUUID();
      if (!existing) setPeople(current => [...current, { id: personId, name: values.personName.trim(), relation: '기타', group: '', importance: '보통', lastMet: '', memo: '', interactions: [] }]);
    }
    const { personName, ...event } = values;
    setEvents(current => [...current, { ...event, personId, id: crypto.randomUUID() }]);
    setModal(null);
    notify(values.type === '장례식' && themeMode === 'auto' && daysUntil(values.date, today) >= 0 && daysUntil(values.date, today) <= 3 ? '일정을 등록하고 차분한 분위기로 바꿨어요.' : '일정을 등록했어요. 알림함에서도 확인해 보세요.');
  }
  function savePerson(values) { setPeople(current => [...current, { ...values, id: crypto.randomUUID() }]); setModal(null); notify('새로운 인연을 등록했어요.'); }
  function storeFinancialRecords(nextRecords, nextPeople = people) {
    try {
      commitWorkspace({records:nextRecords, ...(nextPeople !== people ? {people:nextPeople} : {})});
    } catch {
      notify('브라우저 저장 공간을 확인해 주세요. 금액 기록을 저장하지 못했어요.'); return false;
    }
    if (nextPeople !== people) setPeople(nextPeople);
    setRecords(nextRecords); return true;
  }
  function saveRecord(values) {
    const id = modal?.recordId;
    if (id && !records.some(record => record.id === id)) { notify('수정할 기록을 찾을 수 없어요.'); return; }
    const next = id ? records.map(record => record.id === id ? {...values, id} : record) : [...records, {...values, id:crypto.randomUUID()}];
    if (!storeFinancialRecords(next)) return;
    setModal(null); notify(id ? '금액 기록을 수정했어요. 통계에도 반영했어요.' : '주고받은 마음을 기록했어요. 통계에도 반영했어요.');
  }
  function deleteRecord(id) {
    if (!storeFinancialRecords(records.filter(record => record.id !== id))) return false;
    notify('금액 기록을 삭제했어요. 통계에도 반영했어요.'); return true;
  }
  function importRecords(plan) {
    try {
      const added = materializeImport(plan, () => crypto.randomUUID(), records);
      if (!storeFinancialRecords([...records, ...added.records], added.people.length ? [...people, ...added.people] : people)) return false;
      notify(added.records.length + '건을 가져왔어요.' + (added.people.length ? ' 새 인맥 ' + added.people.length + '명도 등록했어요.' : ''));
      return true;
    } catch (error) { notify(error.message || 'CSV를 다시 확인해 주세요.'); return false; }
  }
  function openEvent(event) { setNotificationsOpen(false); setModal({ type: 'eventDetail', id: event.id }); }
  function downloadCalendar(event) { const blob = new Blob([toICS(event)], { type: 'text/calendar;charset=utf-8' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${event.title}.ics`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); notify('캘린더 파일을 저장했어요. 캘린더 앱에서 열어 주세요.'); }
  async function changeBrowserNotifications(enabled) {
    if (!enabled) { setNotificationSettings({ browser: false }); return; }
    if (typeof Notification === 'undefined') { notify('이 브라우저는 시스템 알림을 지원하지 않아요.'); return; }
    try { const permission = await Notification.requestPermission(); setNotificationSettings({ browser: permission === 'granted' }); notify(permission === 'granted' ? '앱이 열려 있을 때 행사 전 알림을 보내드릴게요.' : '브라우저 알림 권한을 허용하면 사용할 수 있어요.'); } catch { notify('브라우저 설정에서 알림 권한을 확인해 주세요.'); }
  }
  const selectedEvent = modal?.type === 'eventDetail' ? events.find(event => event.id === modal.id) : null;

  const renderNavigationItem = item => <button key={item.id} aria-label={item.label} title={item.label} className={`nav-item ${page === item.id ? 'active' : ''} ${item.id === 'ai' ? 'ai-nav' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} size={20} /><span>{item.label}</span>{item.id === 'ai' && <span className="nav-ai-label">AI</span>}{page === item.id && <span className="nav-active-dot" />}</button>;

  return <div className={`app ${dark ? 'is-somber' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    {menuOpen && <div className="sidebar-scrim" onClick={() => setMenuOpen(false)} />}
    <aside id="main-sidebar" className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`} inert={isMobile && !menuOpen ? true : undefined}>
      <div className="sidebar-header"><button className="brand" onClick={() => navigate('home')} aria-label="마음결 홈"><span className="brand-mark"><Icon name="HeartHandshake" size={24} /></span><span>마음결<small>마음과 마음을 잇다</small></span></button><button className="icon-button desktop-sidebar-toggle" aria-label={sidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기"} aria-controls="main-sidebar" aria-expanded={!sidebarCollapsed} onClick={() => setSidebarCollapsed(value => !value)}><Icon name="Menu" /></button><button className="icon-button sidebar-mobile-close" aria-label="메뉴 닫기" onClick={() => setMenuOpen(false)}><Icon name="X" size={18} /></button></div>
      <div className="sidebar-label">MY SPACE</div>
      <nav className="main-nav" aria-label="주 메뉴">{navigation.filter(item => item.id !== 'ai').map(renderNavigationItem)}</nav>
      <div className="sidebar-bottom"><nav className="ai-nav-group" aria-label="AI 메뉴">{navigation.filter(item => item.id === 'ai').map(renderNavigationItem)}</nav><div className="sidebar-footer">작은 기록으로 이어지는, 우리 사이</div></div>
    </aside>
    <div className="app-content">
      <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" aria-controls="main-sidebar" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)} aria-label="메뉴 열기"><Icon name="Menu" /></button></div><div className="topbar-actions"><span className="today-label"><span />마음을 챙기기 좋은 하루예요</span><div className="theme-control"><button className="theme-toggle" aria-label="화면 분위기 설정" aria-expanded={themeOpen} onClick={() => { setThemeOpen(!themeOpen); setAccountOpen(false); }}><Icon name={dark ? 'Moon' : 'Sun'} size={15} /><span>{themeMode === 'auto' ? '자동 분위기' : dark ? '차분한 분위기' : '따뜻한 분위기'}</span><Icon name="ChevronDown" size={12} /></button>{themeOpen && <><div className="popover-scrim" onClick={() => setThemeOpen(false)} /><div className="theme-popover"><strong>마음에 맞는 분위기</strong>{[{ value: 'auto', name: '상황에 따라 자동', icon: 'Monitor', text: '3일 이내 조사가 있으면 차분하게' }, { value: 'light', name: '따뜻한 마음', icon: 'Sun', text: '밝은 아이보리와 딥그린' }, { value: 'dark', name: '차분한 마음', icon: 'Moon', text: '깊은 숲빛으로 전하는 위로' }].map(item => <button key={item.value} onClick={() => { setThemeMode(item.value); setThemeOpen(false); }}><Icon name={item.icon} size={17} /><span>{item.name}<small>{item.text}</small></span>{themeMode === item.value && <Icon name="Check" size={16} />}</button>)}</div></>}</div><span className="topbar-divider" /><button className="notification-trigger icon-button" aria-label={`알림 ${unreadCount}개`} onClick={() => setNotificationsOpen(true)}><Icon name="Bell" size={20} />{unreadCount > 0 && <span className="notification-dot" />}</button><div className="account-control"><button className="topbar-avatar" aria-label="계정 관리" aria-expanded={accountOpen} onClick={() => { setAccountOpen(!accountOpen); setThemeOpen(false); }}><Icon name="UserRound" size={17} /></button>{accountOpen && <><div className="popover-scrim" onClick={() => setAccountOpen(false)} /><div className="account-popover">{user ? <><strong>{user.name}님</strong><small>@{user.username || user.email}{user.workplace ? ` · ${user.workplace}` : ''}</small><button onClick={() => { setAccountOpen(false); setModal({ type: 'profile' }); }}><Icon name="UserRound" size={16} />정보 수정</button><button onClick={() => { setUser(null); setAccountOpen(false); notify('로그아웃했어요.'); }}><Icon name="LogOut" size={16} />로그아웃</button></> : <><strong>나의 마음 기록</strong><button onClick={() => { setAccountOpen(false); setModal({type:'login'}); }}><Icon name="LogIn" size={16} />로그인</button><button onClick={() => { setAccountOpen(false); setModal({type:'signup'}); }}><Icon name="UserPlus" size={16} />회원가입</button></>}</div></>}</div></div></header>
      <main id="main" className={`main-content ${page === 'home' ? 'home-main' : ''}`} key={page}>
        {page === 'home' && <HomePage people={people} events={events} records={records} upcoming={upcoming} today={today} onAddEvent={() => setModal({ type: 'event' })} onOpenEvent={openEvent} navigate={navigate} notify={notify} />}
        {page === 'schedule' && <SchedulePage events={events} people={people} onAddEvent={() => setModal({ type: 'event' })} onOpenEvent={openEvent} onUpdateEvent={updateEvent} demoUserId={demoUserId} onDemoUserChange={setDemoAccount} />}
        {page === 'people' && <PeoplePage people={people} events={events} records={records} onAddPerson={() => setModal({ type: 'person' })} onUpdatePerson={updatePerson} onAddRecord={id => setModal({ type: 'record', personId: id })} />}
        {page === 'ledger' && <LedgerPage people={people} events={events} records={records} onAddRecord={() => setModal({ type: 'record' })} onEditRecord={id => setModal({type:'record', recordId:id})} onDeleteRecord={deleteRecord} onImportRecords={importRecords} notify={notify} />}
        {page === 'guide' && <EtiquettePage />}
        {page === 'ai' && <AIPage key={demoUserId || 'none'} />}
        {page !== 'home' && <footer className="page-footer"><span>마음결<span className="footer-separator">·</span>기억하고, 연결하고, 마음을 전해요.</span><span>해커톤 체험 버전</span></footer>}
      </main>
    </div>
    {modal?.type === 'event' && <EventForm people={people} onSave={saveEvent} onClose={() => setModal(null)} />}
    {modal?.type === 'person' && <PersonForm onSave={savePerson} onClose={() => setModal(null)} />}
    {modal?.type === 'record' && <RecordForm key={modal.recordId || 'new'} initialRecord={records.find(record => record.id === modal.recordId) || null} people={people} events={events} initialPersonId={modal.personId || ''} initialEventId={modal.eventId || ''} onSave={saveRecord} onClose={() => setModal(null)} />}
    {modal?.type === 'profile' && user && <ProfileEditModal user={user} onClose={() => setModal(null)} onSave={(profile, passwordChanged) => { setUser(profile); setModal(null); notify(passwordChanged ? '비밀번호와 내 정보를 저장했어요.' : '내 정보를 저장했어요.'); }} />}
    {(modal?.type === 'login' || modal?.type === 'signup') && <AuthModal key={modal.type} mode={modal.type} onClose={() => setModal(null)} onSwitch={type => setModal({ type })} onSuccess={profile => { setUser(profile); setModal(null); notify(`${profile.name}님, 마음결에 오신 걸 환영해요.`); }} />}
    {selectedEvent && <EventDetail event={selectedEvent} person={people.find(person => person.id === selectedEvent.personId)} today={today} onClose={() => setModal(null)} onUpdate={patch => updateEvent(selectedEvent.id, patch)} onDelete={() => { setEvents(current => current.filter(event => event.id !== selectedEvent.id)); setModal(null); notify('일정을 삭제했어요. 금액 기록은 보관했어요.'); }} onDownload={() => downloadCalendar(selectedEvent)} onRecord={() => setModal({ type: 'record', personId: selectedEvent.personId, eventId: selectedEvent.id })} onAI={() => { setAiPersonId(selectedEvent.personId); setModal(null); navigate('ai'); }} />}
    {notificationsOpen && <Notifications notices={notices} sharedInbox={sharedInbox} readIds={readIds} onRead={id => setReadIds(current => [...new Set([...current, id])])} onReadAll={() => setReadIds(current => [...new Set([...current, ...allNoticeIds])])} onClose={() => setNotificationsOpen(false)} onOpenEvent={openEvent} onOpenAI={() => { setNotificationsOpen(false); navigate('ai'); }} browserEnabled={notificationSettings.browser} onBrowserChange={changeBrowserNotifications} />}
    {toast && <div className="toast" role="status"><Icon name="CheckCircle2" size={18} />{toast}</div>}
  </div>;
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
  return <button className={`event-row ${occasionClass(event.type)}`} onClick={onClick}><span className={`event-date ${occasionClass(event.type)}`}><small>{Number(event.date.slice(5, 7))}월</small><strong>{event.date.slice(8)}</strong></span><span className="event-row-content"><span className="event-title">{event.title}<span className={`badge ${occasionClass(event.type)}`}>{event.type}</span></span><span className="event-meta"><Icon name="Clock3" size={12} />{new Date(`${event.date}T12:00:00`).toLocaleDateString('ko-KR', { weekday: 'short' })}요일 {event.time || '시간 미정'}<span className="event-meta-location"><i />{event.location || '장소 미정'}</span></span><span className="event-relationship">{person?.relation || '인연'} · {person?.group || '소속 미지정'}<i /><span className={`att-pill ${attendanceClass(event.attendance)}`}>{event.attendance || '참석 여부 선택'}</span></span></span><span className={`d-day ${days <= 3 ? 'urgent' : ''}`}>{ddLabel(days)}</span><Icon className="event-row-arrow" name="ChevronRight" size={15} /></button>;
}

function EventDetail({ event, person, today, onClose, onUpdate, onDelete, onDownload, onRecord, onAI }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ title: event.title, date: event.date, time: event.time, location: event.location, memo: event.memo || '' });
  const [confirmDelete, setConfirmDelete] = useState(false);
  return <Modal title="마음을 챙길 일정" subtitle="소중한 날을 위해 차근차근 준비해요." onClose={onClose}>
    <div className={`event-detail-summary ${occasionClass(event.type)}`}><span className={`detail-event-icon ${occasionClass(event.type)}`}><Icon name={eventIcon(event.type)} size={25} /></span><div><span className={`badge ${occasionClass(event.type)}`}>{event.type} · {ddLabel(daysUntil(event.date, today))}</span><h3>{event.title}</h3><p>{person?.name} · {person?.relation} · {person?.group || '소속 그룹 없음'}</p></div><button className="icon-button" aria-label="일정 정보 수정" onClick={() => setEditing(!editing)}><Icon name="Pencil" size={17} /></button></div>
    {editing ? <form className="detail-edit-form" onSubmit={e => { e.preventDefault(); onUpdate(draft); setEditing(false); }}><label className="field">일정 이름<input className="input" required value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label><div className="form-grid"><label className="field">날짜<input className="input" required type="date" value={draft.date} onChange={e => setDraft({ ...draft, date: e.target.value })} /></label><label className="field">시간<input className="input" type="time" value={draft.time} onChange={e => setDraft({ ...draft, time: e.target.value })} /></label></div><label className="field">장소<input className="input" value={draft.location} onChange={e => setDraft({ ...draft, location: e.target.value })} /></label><label className="field">기억할 메모<textarea className="input" rows={2} value={draft.memo} onChange={e => setDraft({ ...draft, memo: e.target.value })} /></label><button className="button button-primary" type="submit">변경사항 저장</button></form> : <div className="event-detail-info"><div><Icon name="CalendarDays" size={17} /><span>{fullDate(event.date)} · {event.time || '시간 미정'}</span></div><div><Icon name="MapPin" size={17} /><span>{event.location || '장소 미정'}</span></div>{event.memo && <div><Icon name="NotebookPen" size={17} /><span>{event.memo}</span></div>}</div>}
    <div className="event-detail-controls"><label className="field">참석 여부<select className="input" value={event.attendance} onChange={e => onUpdate({ attendance: e.target.value })}><option value="" disabled>참석 여부 선택</option>{['참석', '불참'].map(value => <option key={value}>{value}</option>)}</select></label><label className="field">행사 전 알림<select className="input" value={event.reminderDays} onChange={e => onUpdate({ reminderDays: Number(e.target.value) })}><option value={0}>행사 당일</option><option value={1}>1일 전부터</option><option value={3}>3일 전부터</option><option value={7}>7일 전부터</option></select></label></div>
    <div className="event-detail-ai"><Icon name="Sparkles" size={19} /><div><strong>어떤 마음을 전하면 좋을까요?</strong><p>지난 금액과 관계 기록을 함께 참고해 보세요.</p></div><button className="icon-button" aria-label="마음결 AI 열기" onClick={onAI}><Icon name="ArrowUpRight" size={19} /></button></div><div className="event-detail-actions"><button className="button button-secondary" onClick={onDownload}><Icon name="Download" size={16} />캘린더 저장</button><button className="button button-primary" onClick={onRecord}><Icon name="HandHeart" size={16} />금액 기록</button></div><button className={`delete-event ${confirmDelete ? 'confirm' : ''}`} onClick={() => confirmDelete ? onDelete() : setConfirmDelete(true)}>{confirmDelete ? '한 번 더 누르면 일정을 삭제해요' : '일정 삭제'}</button>
  </Modal>;
}
