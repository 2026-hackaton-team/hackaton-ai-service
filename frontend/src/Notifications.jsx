import { useEffect, useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import { demoApi } from './services/demoApi.js';
import { DEMO_ACCOUNT_EVENT, getDemoAccount, setDemoAccount } from './services/demoAccount.js';
import { loadSharedNotices, sharedNoticeId } from './services/noticeInbox.js';
import './notice-inbox.css';
import { occasionClass } from './occasion.js';

export { sharedNoticeId };

export function useSharedNoticeInbox() {
  const [userId, setUserId] = useState(() => getDemoAccount());
  const [users, setUsers] = useState([]);
  const [usersError, setUsersError] = useState('');
  const [reload, setReload] = useState(0);
  const [snapshot, setSnapshot] = useState({ userId: '', items: [], status: 'idle', error: '' });
  useEffect(() => {
    const sync = () => setUserId(getDemoAccount());
    window.addEventListener(DEMO_ACCOUNT_EVENT, sync);
    return () => window.removeEventListener(DEMO_ACCOUNT_EVENT, sync);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setUsersError('');
    demoApi('/demo/users', { signal: controller.signal }).then(result => {
      if (!Array.isArray(result.items)) throw new Error('프로필 목록을 불러오지 못했어요.');
      if (!controller.signal.aborted) setUsers(result.items);
    }).catch(error => { if (!controller.signal.aborted) setUsersError(error.message); });
    return () => controller.abort();
  }, [reload]);
  useEffect(() => {
    if (!userId) { setSnapshot({ userId: '', items: [], status: 'idle', error: '' }); return; }
    const controller = new AbortController();
    setSnapshot({ userId, items: [], status: 'loading', error: '' });
    loadSharedNotices(userId, { signal: controller.signal }).then(items => {
      if (!controller.signal.aborted) setSnapshot({ userId, items, status: 'ready', error: '' });
    }).catch(error => {
      if (!controller.signal.aborted) setSnapshot({ userId, items: [], status: 'error', error: error.message });
    });
    return () => controller.abort();
  }, [userId, reload]);
  const current = snapshot.userId === userId ? snapshot : { items: [], status: userId ? 'loading' : 'idle', error: '' };
  return { ...current, userId, users, usersError,
    selectUser: id => { setDemoAccount(id); setUserId(id); },
    refresh: () => setReload(value => value + 1),
  };
}

const dateLabel = value => value ? String(value).replaceAll('-', '.') : '날짜 확인 필요';
const iconFor = type => type === '장례식' ? 'Flower2' : type === '돌잔치' || type === '생일' ? 'Cake' : 'Heart';
const viaLabel = item => item.kind === 'friend' ? `${item.senderName}님이 보낸 일정`
  : item.mutualNames?.length ? `${item.mutualNames.slice(0, 2).join(', ')}님을 통해 알게 된 소식` : `함께 아는 친구 ${item.mutualCount}명의 소식`;

/** 받은 일정의 읽음 표시 키 (서버 소식은 기존 키 형식을 유지) */
export function receivedReadId(item, profileId) {
  return item.source === 'server' ? sharedNoticeId(profileId, item.raw?.notice?.id) : `received:${item.key}`;
}

export default function Notifications({ notices, sharedInbox, receivedItems = [], readIds, onRead, onReadAll, onClose, onOpenEvent, onOpenAI, onOpenReceived, onAddToCalendar, browserEnabled, onBrowserChange }) {
  const [tab, setTab] = useState('전체');
  const [selectedKey, setSelectedKey] = useState('');
  useEffect(() => setSelectedKey(''), [sharedInbox.userId]);
  const selected = receivedItems.find(item => item.key === selectedKey);
  const readId = item => receivedReadId(item, sharedInbox.userId);
  const eventUnread = notices.filter(item => !readIds.includes(item.id));
  const receivedUnread = receivedItems.filter(item => !readIds.includes(readId(item)));
  const unreadCount = eventUnread.length + receivedUnread.length;
  const eventItems = tab === '받은 일정' ? [] : tab === '읽지 않음' ? eventUnread : notices;
  const sharedItems = tab === '읽지 않음' ? receivedUnread : receivedItems;
  const hasItems = eventItems.length + sharedItems.length > 0;
  return <Modal title="마음을 챙기는 알림" subtitle="다가오는 일정과 받은 일정을 카드로 확인해요." onClose={onClose} wide>
    <div className="notice-center">
      {selected ? <>
        <button type="button" className="text-button notice-back" onClick={() => setSelectedKey('')}><Icon name="ArrowLeft" size={17} />알림 목록으로</button>
        <article className="notice-detail"><span className="notice-kind">{selected.kind === 'friend' ? '친구가 보낸 일정' : '함께 아는 사람 소식'} · {selected.type}</span><h3>{selected.title}</h3><p>{viaLabel(selected)}</p>
          <dl><div><dt>일정</dt><dd>{dateLabel(selected.date)}{selected.time ? ` ${selected.time}` : ''}{selected.endDate && selected.endDate !== selected.date ? ` ~ ${dateLabel(selected.endDate)}` : ''}</dd></div>
            <div><dt>장소</dt><dd>{selected.location || '장소 미정'}</dd></div>
            {selected.visitingHours && <div><dt>조문 시간</dt><dd>{selected.visitingHours}</dd></div>}
            {selected.message && <div><dt>{selected.source === 'local' ? '전한 말' : '상주'}</dt><dd>{selected.message}</dd></div>}
          </dl>
          <div className="notice-detail-actions">
            {selected.status === 'added'
              ? <button type="button" className="button button-secondary" onClick={() => onOpenEvent({ id: selected.addedEventId })}><Icon name="CalendarCheck" size={17} />달력에서 보기</button>
              : <button type="button" className="button button-primary" onClick={() => onAddToCalendar(selected)}><Icon name="CalendarPlus" size={17} />내 달력에 추가</button>}
            <button type="button" className="button button-secondary" onClick={onOpenAI}><Icon name="Sparkles" size={17} />마음결 AI에 물어보기</button>
          </div>
        </article>
      </> : <>
        {sharedInbox.users.length > 0 && <div className="notice-account"><label>프로필<select className="input" aria-label="소식을 받을 프로필" value={sharedInbox.userId} onChange={event => sharedInbox.selectUser(event.target.value)}><option value="">프로필 선택</option>{sharedInbox.users.map(user => <option key={user.id} value={user.id}>{user.name} · {user.affiliation || user.id}</option>)}</select></label><button type="button" className="button button-secondary" onClick={sharedInbox.refresh}><Icon name="RefreshCw" size={16} />새로고침</button></div>}
        <div className="notification-toolbar"><div className="notification-tabs">{['전체', '받은 일정', '읽지 않음'].map(item => <button type="button" aria-pressed={tab === item} className={tab === item ? 'active' : ''} key={item} onClick={() => setTab(item)}>{item}{item === '읽지 않음' && <span>{unreadCount}</span>}</button>)}</div><button type="button" className="text-button" disabled={!unreadCount} onClick={onReadAll}><Icon name="CheckCheck" size={16} />모두 읽음</button></div>
        {sharedInbox.status === 'loading' && <p className="notice-status" role="status">받은 일정을 불러오고 있어요.</p>}
        {sharedInbox.error && <p className="notice-status notice-error" role="alert">{sharedInbox.error} <button type="button" className="text-button" onClick={sharedInbox.refresh}>다시 시도</button></p>}
        <div className="notification-list notice-card-list">
          {sharedItems.map(item => {
            const id = readId(item);
            const unread = !readIds.includes(id);
            return <article className={`notice-shared-card ${occasionClass(item.type)} ${unread ? 'unread' : ''}`} key={item.key}>
              <div className="notice-card-top"><span className="notice-kind"><Icon name={item.kind === 'friend' ? 'Send' : 'UsersRound'} size={16} />{item.kind === 'friend' ? '친구가 보낸 일정' : '함께 아는 사람 소식'}</span><span className="notice-read-label">{item.status === 'added' ? '달력에 추가됨' : unread ? '새 소식' : '읽음'}</span></div>
              <h3><Icon name={iconFor(item.type)} size={17} />{item.title}</h3><p>{dateLabel(item.date)}{item.time ? ` ${item.time}` : ''} · {item.location || '장소 미정'}</p><p>{viaLabel(item)}</p>
              <div className="notice-card-bottom"><span>{item.type}</span><button type="button" className="button button-secondary" aria-label={`${item.title} 확인`} onClick={() => { onRead(id); setSelectedKey(item.key); }}>확인하기<Icon name="ArrowUpRight" size={16} /></button></div>
            </article>;
          })}
          {tab === '받은 일정' && receivedItems.length > 0 && <button type="button" className="text-button notice-open-received" onClick={onOpenReceived}>받은 일정 전체 보기<Icon name="ChevronRight" size={15} /></button>}
          {eventItems.map(notice => <button type="button" key={notice.id} className={`notification-item ${!readIds.includes(notice.id) ? 'unread' : ''}`} onClick={() => { onRead(notice.id); onOpenEvent(notice.event); }}><span className={`notification-type-icon ${occasionClass(notice.event.type)}`}><Icon name={iconFor(notice.event.type)} size={20} /></span><span className="notification-item-body"><strong>{notice.event.type === '장례식' ? '조심스럽게 전해 드리는 소식' : `${notice.event.title}${notice.days === 0 ? '이 오늘이에요' : `까지 ${notice.days}일`}`}</strong><span>{notice.event.type === '장례식' ? `${notice.event.title} · 빈소와 조문 시간을 확인해 주세요.` : `${dateLabel(notice.event.date)} ${notice.event.time || ''} · ${!notice.event.attendance ? '참석 여부를 알려 주세요.' : '준비할 마음을 확인해 보세요.'}`}</span><small>{notice.event.location || '장소를 확인해 주세요'}{notice.event.reminderDays > 0 ? ` · ${notice.event.reminderDays}일 전부터 알림` : ' · 당일 알림'}</small></span>{!readIds.includes(notice.id) && <span className="unread-dot" />}</button>)}
          {!hasItems && sharedInbox.status !== 'loading' && !sharedInbox.error && <EmptyState icon="CheckCheck" title={tab === '읽지 않음' ? '새로 확인할 알림이 없어요' : tab === '받은 일정' ? '아직 받은 일정이 없어요' : '아직 도착한 알림이 없어요'} description="새로운 일정과 받은 일정이 있으면 이곳에 표시돼요." />}
        </div>
      </>}
      <div className="notification-preferences"><div><span className="notification-pref-icon"><Icon name="Bell" size={18} /></span><div><strong>브라우저 알림 받기</strong><p>앱이 열려 있을 때, 설정한 날짜부터 알려드려요.</p></div><button className={`switch ${browserEnabled ? 'on' : ''}`} role="switch" aria-checked={browserEnabled} aria-label="브라우저 알림" onClick={() => onBrowserChange(!browserEnabled)}><span /></button></div></div>
    </div>
  </Modal>;
}
