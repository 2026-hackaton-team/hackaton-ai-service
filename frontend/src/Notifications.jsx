import { useEffect, useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import { demoApi } from './services/demoApi.js';
import { DEMO_ACCOUNT_EVENT, getDemoAccount, setDemoAccount } from './services/demoAccount.js';
import { loadSharedNotices, sharedNoticeId } from './services/noticeInbox.js';
import './notice-inbox.css';

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
      if (!Array.isArray(result.items)) throw new Error('시연 계정을 불러오지 못했어요.');
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
const relationLabel = item => item.relation_type === 'direct_friend' ? '친구가 공유한 소식' : '친구의 친구가 공유한 소식';
const iconFor = type => type === '장례식' ? 'Flower2' : type === '돌잔치' || type === '생일' ? 'Cake' : 'Heart';

export default function Notifications({ notices, sharedInbox, readIds, onRead, onReadAll, onClose, onOpenEvent, onOpenAI, browserEnabled, onBrowserChange }) {
  const [tab, setTab] = useState('전체');
  const [selected, setSelected] = useState(null);
  useEffect(() => setSelected(null), [sharedInbox.userId]);
  const eventUnread = notices.filter(item => !readIds.includes(item.id));
  const sharedUnread = sharedInbox.items.filter(item => !readIds.includes(sharedNoticeId(sharedInbox.userId, item.notice.id)));
  const unreadCount = eventUnread.length + sharedUnread.length;
  const eventItems = tab === '공유 소식' ? [] : tab === '읽지 않음' ? eventUnread : notices;
  const sharedItems = tab === '읽지 않음' ? sharedUnread : sharedInbox.items;
  const hasItems = eventItems.length + sharedItems.length > 0;
  return <Modal title="마음을 챙기는 알림" subtitle="일정 알림과 공유된 소식을 카드로 확인해요." onClose={onClose} wide>
    <div className="notice-center">
      {selected ? <>
        <button type="button" className="text-button notice-back" onClick={() => setSelected(null)}><Icon name="ArrowLeft" size={17} />알림 목록으로</button>
        <article className="notice-detail"><span className="notice-kind">공유 부고 · 시연 자료</span><h3>{selected.notice.title}</h3><p>{relationLabel(selected)}</p>
          <dl><div><dt>일정</dt><dd>{dateLabel(selected.notice.start_date)} ~ {dateLabel(selected.notice.end_date)}</dd></div><div><dt>지역</dt><dd>{selected.notice.region || '지역 미기록'}</dd></div>
            {selected.notice.venue && <div><dt>장소</dt><dd>{selected.notice.venue}{selected.notice.room ? ` · ${selected.notice.room}` : ''}</dd></div>}
            {selected.notice.visiting_hours && <div><dt>조문 시간</dt><dd>{selected.notice.visiting_hours}</dd></div>}
          </dl><p className="notice-context-note">공유 범위에 따라 표시된 가상 소식이에요. 내 일정에 자동으로 추가되지 않아요.</p>
          <button type="button" className="button button-primary" onClick={onOpenAI}><Icon name="Sparkles" size={17} />마음결 AI에 물어보기</button>
        </article>
      </> : <>
        <div className="notice-account"><label>시연 계정<select className="input" aria-label="알림 시연 계정" value={sharedInbox.userId} onChange={event => sharedInbox.selectUser(event.target.value)}><option value="">계정 선택</option>{sharedInbox.users.map(user => <option key={user.id} value={user.id}>{user.name} · {user.affiliation || user.id}</option>)}</select></label><button type="button" className="button button-secondary" onClick={sharedInbox.refresh}><Icon name="RefreshCw" size={16} />새로고침</button></div>
        <div className="notification-toolbar"><div className="notification-tabs">{['전체', '공유 소식', '읽지 않음'].map(item => <button type="button" aria-pressed={tab === item} className={tab === item ? 'active' : ''} key={item} onClick={() => setTab(item)}>{item}{item === '읽지 않음' && <span>{unreadCount}</span>}</button>)}</div><button type="button" className="text-button" disabled={!unreadCount} onClick={onReadAll}><Icon name="CheckCheck" size={16} />모두 읽음</button></div>
        {sharedInbox.status === 'loading' && <p className="notice-status" role="status">공유 소식을 불러오고 있어요.</p>}
        {(sharedInbox.error || sharedInbox.usersError) && <p className="notice-status notice-error" role="alert">{sharedInbox.error || sharedInbox.usersError} <button type="button" className="text-button" onClick={sharedInbox.refresh}>다시 시도</button></p>}
        {tab === '공유 소식' && !sharedInbox.userId && <p className="notice-status">위에서 시연 계정을 선택해 공유 소식을 확인해 보세요.</p>}
        <div className="notification-list notice-card-list">
          {sharedItems.map(item => {
            const id = sharedNoticeId(sharedInbox.userId, item.notice.id);
            const unread = !readIds.includes(id);
            return <article className={`notice-shared-card ${unread ? 'unread' : ''}`} key={id}>
              <div className="notice-card-top"><span className="notice-kind"><Icon name="Flower2" size={16} />공유 부고</span><span className="notice-read-label">{unread ? '새 소식' : '읽음'}</span></div>
              <h3>{item.notice.title}</h3><p>{dateLabel(item.notice.start_date)} ~ {dateLabel(item.notice.end_date)} · {item.notice.region || '지역 미기록'}</p><p>{relationLabel(item)}</p>
              <div className="notice-card-bottom"><span>가상 시연 자료</span><button type="button" className="button button-secondary" aria-label={`${item.notice.title} 소식 확인`} onClick={() => { onRead(id); setSelected(item); }}>소식 확인<Icon name="ArrowUpRight" size={16} /></button></div>
            </article>;
          })}
          {eventItems.map(notice => <button type="button" key={notice.id} className={`notification-item ${!readIds.includes(notice.id) ? 'unread' : ''}`} onClick={() => { onRead(notice.id); onOpenEvent(notice.event); }}><span className={`notification-type-icon ${notice.event.type === '장례식' ? 'slate' : ''}`}><Icon name={iconFor(notice.event.type)} size={20} /></span><span className="notification-item-body"><strong>{notice.event.type === '장례식' ? '조심스럽게 전해 드리는 소식' : `${notice.event.title}${notice.days === 0 ? '이 오늘이에요' : `까지 ${notice.days}일`}`}</strong><span>{notice.event.type === '장례식' ? `${notice.event.title} · 빈소와 조문 시간을 확인해 주세요.` : `${dateLabel(notice.event.date)} ${notice.event.time || ''} · ${!notice.event.attendance ? '참석 여부를 알려 주세요.' : '준비할 마음을 확인해 보세요.'}`}</span><small>{notice.event.location || '장소를 확인해 주세요'}{notice.event.reminderDays > 0 ? ` · ${notice.event.reminderDays}일 전부터 알림` : ' · 당일 알림'}</small></span>{!readIds.includes(notice.id) && <span className="unread-dot" />}</button>)}
          {!hasItems && sharedInbox.status !== 'loading' && !sharedInbox.error && !sharedInbox.usersError && <EmptyState icon="CheckCheck" title={tab === '읽지 않음' ? '새로 확인할 알림이 없어요' : tab === '공유 소식' ? '표시할 공유 소식이 없어요' : '아직 도착한 알림이 없어요'} description="새로운 일정과 공유 소식이 있으면 이곳에 표시돼요." />}
        </div>
      </>}
      <div className="notification-preferences"><div><span className="notification-pref-icon"><Icon name="Bell" size={18} /></span><div><strong>브라우저 알림 받기</strong><p>앱이 열려 있을 때, 설정한 날짜부터 알려드려요.</p></div><button className={`switch ${browserEnabled ? 'on' : ''}`} role="switch" aria-checked={browserEnabled} aria-label="브라우저 알림" onClick={() => onBrowserChange(!browserEnabled)}><span /></button></div><p className="notification-footnote"><Icon name="Info" size={12} />앱을 닫은 후의 자동 발송은 서버 연동 후 지원돼요.</p></div>
    </div>
  </Modal>;
}
