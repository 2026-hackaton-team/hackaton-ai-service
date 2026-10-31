import { createContext, useContext, useMemo, useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import { SectionTabs } from './FeaturePreview.jsx';
import { occasionClass } from './occasion.js';
import { SHARE_SCOPES, friendsOf, incomingRequests, outgoingRequests, searchMembers, visibleMember, relationStatus, shareForEvent, shareResponses, requestFriend, respondFriend, cancelFriendRequest, upsertShare } from './services/socialStore.js';
import './feature-preview.css';
import { RELATION_OPTIONS, IMPORTANCE_OPTIONS, normalizeImportance, relationDraft } from './relationships.js';
import { PRIORITY_RELATIONS } from './services/relationshipPriority.js';
import { recommendFriends, FRIEND_RECOMMENDATION_WEIGHTS } from './services/friendRecommendations.js';
import './social.css';

/*
  value = {
    user, social, members, mutate(change, successMessage), requireLogin(mode),
    receivedItems, addToCalendar(item), hideItem(item), openEvent(id), goFindFriends(),
    sharedInbox, notify
  }
*/
export const SocialContext = createContext(null);
export const useSocial = () => useContext(SocialContext);

const iconFor = type => type === '장례식' ? 'Flower2' : type === '돌잔치' || type === '생일' ? 'Cake' : 'Heart';
const dateText = (date, time) => {
  if (!date) return '날짜 확인 필요';
  const day = new Date(`${date}T12:00:00+09:00`).toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short', timeZone: 'Asia/Seoul' });
  return `${day}${time ? ` ${time}` : ''}`;
};
const workLine = member => [member.workplace, member.organization].filter(Boolean).join(' · ') || '소속 비공개';

function LoginNeeded({ title, description }) {
  const { requireLogin } = useSocial();
  return <div className="card feature-empty social-login-needed"><EmptyState icon="LockKeyhole" title={title} description={description} />
    <div className="social-login-actions"><button type="button" className="button button-secondary" onClick={() => requireLogin('signup')}><Icon name="UserPlus" size={16} />회원가입</button><button type="button" className="button button-primary" onClick={() => requireLogin('login')}><Icon name="LogIn" size={16} />로그인</button></div>
  </div>;
}

function MemberCard({ member, children, note }) {
  return <article className="card feature-member-card social-member-card">
    <div className="feature-member-top"><span className="avatar">{member.name.slice(0, 1)}</span><div><h3>{member.name}</h3><p>@{member.username} · {workLine(member)}</p></div></div>
    <p className="feature-mutual"><Icon name="UsersRound" size={17} />{member.mutual?.length ? `함께 아는 친구 ${member.mutual.length}명` : '함께 아는 친구 없음'}</p>
    {note && <p className="feature-member-description">{note}</p>}
    <div className="feature-member-actions">{children}</div>
  </article>;
}

/* ---------- 인맥 관리 › 친구 찾기 ---------- */
export function FriendFinder() {
  const { user, social, members, mutate, people = [] } = useSocial();
  const [query, setQuery] = useState('');
  if (!user) return <LoginNeeded title="로그인하고 마음결 친구를 찾아보세요" description="친구가 되면 서로의 경조사 일정을 주고받을 수 있어요." />;
  const me = user.username;
  const searching = Boolean(query.trim());
  const minimumScore = FRIEND_RECOMMENDATION_WEIGHTS.threshold;
  const list = searchMembers(social, members, me, query);
  const recommendations = recommendFriends(social, members, me, people);
  const recommendedByUsername = new Map(recommendations.map(member => [member.username, member.recommendation]));
  const friends = list.filter(member => member.status === 'friend');
  // 직접 검색은 추천 점수와 별개로 유지해 친구 요청·취소·수락 동작을 보존한다.
  const others = searching ? list.filter(member => member.status !== 'friend').map(member => ({
    ...member, recommendation: recommendedByUsername.get(member.username),
  })) : recommendations;
  const nameOf = username => members.find(item => String(item.username).trim().toLowerCase() === username)?.name || username;
  const noteFor = member => {
    const bridge = member.recommendation?.connections[0];
    if (bridge) return `${nameOf(bridge.username)}님(${bridge.relation} · ${bridge.importance})을 통해 연결돼 있어요.`;
    return member.mutual.length ? `${member.mutual.map(nameOf).slice(0, 2).join(', ')}님과 함께 아는 사이예요.` : '새로운 인연을 이어 보세요.';
  };
  return <div className="social-panel">
    <div className="feature-section-heading"><div><h2>함께 아는 인연에서 시작해요</h2><p>내가 기록한 관계·중요도와 함께 아는 친구를 반영해, 추천 점수가 {minimumScore}점 이상인 회원만 보여 드려요.</p></div></div>
    <label className="pl-search feature-search"><Icon name="Search" size={18} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="이름, 아이디, 소속으로 회원 검색" aria-label="회원 검색" />{query && <button type="button" aria-label="검색어 지우기" onClick={() => setQuery('')}><Icon name="X" size={16} /></button>}</label>
    <p className="friend-recommendation-help">친구 카드의 ‘내 인맥과 연결’에서 연결한 인맥의 관계·중요도를 추천에 반영해요. 회원을 직접 검색할 때는 점수와 관계없이 찾을 수 있고, 비공개 회원은 정확한 아이디로만 검색돼요.</p>
    {friends.length > 0 && <section className="social-section"><h3>내 친구 <span>{friends.length}</span></h3><div className="feature-member-grid">{friends.map(member => <MemberCard key={member.username} member={member} note="일정을 보내고 받을 수 있는 친구예요."><span className="social-status friend"><Icon name="Check" size={15} />친구</span><PersonLinker member={member} /></MemberCard>)}</div></section>}
    <section className="social-section"><h3>{searching ? '회원 검색 결과' : '추천 친구'} <span>{others.length}</span></h3>
      {others.length ? <div className="feature-member-grid">{others.map(member => <MemberCard key={member.username} member={member} note={noteFor(member)}>
        {member.recommendation && <span className="friend-recommendation-score"><Icon name="Sparkles" size={14} />추천 {member.recommendation.score}점</span>}
        {member.status === 'none' && <button type="button" className="button button-primary" onClick={() => mutate(state => requestFriend(state, me, member.username), `${member.name}님에게 친구 요청을 보냈어요.`)}><Icon name="UserPlus" size={16} />친구 요청</button>}
        {member.status === 'requested' && <><span className="social-status">요청을 보냈어요</span><button type="button" className="button button-secondary" onClick={() => mutate(state => cancelFriendRequest(state, me, member.username), '친구 요청을 취소했어요.')}>요청 취소</button></>}
        {member.status === 'incoming' && <button type="button" className="button button-primary" onClick={() => mutate(state => requestFriend(state, me, member.username), `${member.name}님과 친구가 되었어요.`)}><Icon name="Check" size={16} />요청 수락</button>}
      </MemberCard>)}</div> : <div className="card feature-empty"><EmptyState icon="UsersRound" title={searching ? '검색에 맞는 회원이 없어요' : '아직 추천할 친구가 없어요'} description={searching ? '이름이나 아이디를 다시 확인해 주세요.' : `추천 점수가 ${minimumScore}점 이상인 회원이 생기면 보여 드려요. 내 친구를 인맥과 연결하고 관계·중요도를 설정해 보세요.`} /></div>}
    </section>
  </div>;
}

/* ---------- 인맥 관리 › 받은 요청 ---------- */
export function FriendRequests() {
  const { user, social, members, mutate } = useSocial();
  if (!user) return <LoginNeeded title="로그인하고 받은 친구 요청을 확인하세요" description="나에게 친구를 요청한 사람을 확인하고 수락할 수 있어요." />;
  const me = user.username;
  const profile = username => {
    const account = members.find(item => item.username === username);
    const isFriend = relationStatus(social, me, username) === 'friend';
    return { ...(account ? visibleMember(account, { isFriend }) : { username, name: username, workplace: '', organization: '' }), mutual: searchMembers(social, members, me, username).find(item => item.username === username)?.mutual || [] };
  };
  const incoming = incomingRequests(social, me);
  const outgoing = outgoingRequests(social, me);
  return <div className="social-panel">
    <div className="feature-section-heading"><div><h2>새로운 인연의 시작</h2><p>나에게 친구를 요청한 사람을 확인하고 결정할 수 있어요.</p></div></div>
    {incoming.length ? <div className="feature-member-grid">{incoming.map(request => {
      const member = profile(request.from);
      return <MemberCard key={request.id} member={member} note="나에게 친구 연결을 요청했어요.">
        <button type="button" className="button button-secondary" onClick={() => mutate(state => respondFriend(state, request.id, me, false), '요청을 거절했어요.')}>거절</button>
        <button type="button" className="button button-primary" onClick={() => mutate(state => respondFriend(state, request.id, me, true), `${member.name}님과 친구가 되었어요.`)}><Icon name="Check" size={16} />수락</button>
      </MemberCard>;
    })}</div> : <div className="card feature-empty"><EmptyState icon="Mail" title="새로 받은 친구 요청이 없어요" description="친구 찾기에서 먼저 요청을 보내 보세요." /></div>}
    {outgoing.length > 0 && <section className="social-section"><h3>내가 보낸 요청 <span>{outgoing.length}</span></h3><ul className="social-outgoing">{outgoing.map(request => { const member = profile(request.to); return <li key={request.id}><span className="avatar">{member.name.slice(0, 1)}</span><span><strong>{member.name}</strong><small>@{member.username} · 수락을 기다리고 있어요</small></span><button type="button" className="text-button" onClick={() => mutate(state => cancelFriendRequest(state, me, member.username), '친구 요청을 취소했어요.')}>요청 취소</button></li>; })}</ul></section>}
  </div>;
}

/* ---------- 일정 보내기 ---------- */
export function ShareEventModal({ event, initialScope, initialMessage, onClose }) {
  const { user, social, members, mutate, goFindFriends, people = [] } = useSocial();
  const existing = user ? shareForEvent(social, user.username, event.id) : null;
  const friends = user ? friendsOf(social, user.username).map(username => {
    const account = members.find(item => item.username === username);
    return account ? visibleMember(account, { isFriend: true }) : { username, name: username, workplace: '', organization: '' };
  }) : [];
  const already = new Set(existing?.recipients || []);
  const [scope, setScope] = useState(initialScope || existing?.scope || 'friends');
  const [message, setMessage] = useState(initialMessage ?? existing?.message ?? '');
  const [selected, setSelected] = useState(() => new Set(friends.filter(friend => !already.has(friend.username)).length === 1 ? friends.map(friend => friend.username) : []));
  const [consent, setConsent] = useState(Boolean(existing) || event.type !== '장례식');
  const [error, setError] = useState('');
  const toggle = username => setSelected(current => { const next = new Set(current); next.has(username) ? next.delete(username) : next.add(username); return next; });
  const pending = friends.filter(friend => !already.has(friend.username));
  // 내 인맥에서 '가족'으로 연결한 친구 = 가족 그룹
  const familySet = new Set(people.filter(entry => entry.linkedUsername && relationDraft(entry.relation).relation === '가족').map(entry => entry.linkedUsername));
  const family = pending.filter(friend => familySet.has(friend.username));

  function submit(e, mode = '') {
    e?.preventDefault();
    const targets = mode === 'all' ? new Set(pending.map(friend => friend.username)) : mode === 'family' ? new Set(family.map(friend => friend.username)) : selected;
    if (event.type === '장례식' && !consent) { setError('장례 소식은 유족(가족)의 공유 동의를 확인한 뒤 보낼 수 있어요.'); return; }
    if (scope === 'friends' && !targets.size && !already.size) { setError('일정을 받을 친구를 한 명 이상 선택해 주세요.'); return; }
    const names = friends.filter(friend => targets.has(friend.username)).map(friend => friend.name);
    const ok = mutate(state => upsertShare(state, { owner: user.username, ownerName: user.name, event, scope, message, recipients: [...targets], group: mode === 'family' ? 'family' : null }),
      names.length ? `${names[0]}님${names.length > 1 ? ` 외 ${names.length - 1}명` : ''}에게 일정을 보냈어요.` : scope === 'friends_of_friends' ? '친구의 친구에게도 소식을 알렸어요.' : '공유 설정을 저장했어요.', setError);
    if (ok) onClose(true);
  }

  return <Modal title="친구에게 일정 보내기" subtitle="보낸 일정은 친구의 '받은 일정'에 도착하고, 친구가 바로 달력에 추가할 수 있어요." onClose={() => onClose(false)} wide>
    <form className="app-form social-share-form" onSubmit={submit}>
      <div className={`social-share-event ${occasionClass(event.type)}`}><span className={`detail-event-icon ${occasionClass(event.type)}`}><Icon name={iconFor(event.type)} size={22} /></span><div><span className={`badge ${occasionClass(event.type)}`}>{event.type}</span><strong>{event.title}</strong><small>{dateText(event.date, event.time)} · {event.location || '장소 미정'}</small></div></div>
      <fieldset className="social-fieldset"><legend>받을 친구</legend>
        {friends.length ? <div className="social-friend-pick">{friends.map(friend => {
          const sent = already.has(friend.username);
          return <label key={friend.username} className={`social-pick ${sent ? 'sent' : ''} ${selected.has(friend.username) ? 'on' : ''}`}><input type="checkbox" checked={sent || selected.has(friend.username)} disabled={sent} onChange={() => toggle(friend.username)} /><span className="avatar">{friend.name.slice(0, 1)}</span><span><strong>{friend.name}{familySet.has(friend.username) && <em className="social-family-tag">가족</em>}</strong><small>{sent ? '이미 보냈어요' : `@${friend.username}`}</small></span></label>;
        })}</div> : <div className="social-no-friends"><p>아직 마음결 친구가 없어요. 친구를 추가하면 일정을 보낼 수 있어요.</p><button type="button" className="button button-secondary" onClick={() => { onClose(false); goFindFriends(); }}><Icon name="UserPlus" size={16} />친구 찾으러 가기</button></div>}
        {pending.length > 1 && <button type="button" className="text-button social-select-all" onClick={() => setSelected(selected.size === pending.length ? new Set() : new Set(pending.map(friend => friend.username)))}>{selected.size === pending.length ? '선택 해제' : '모두 선택'}</button>}
      </fieldset>
      <label className="field"><span className="field-label">공유 범위</span><select className="input" value={scope} onChange={e => setScope(e.target.value)}>{Object.entries(SHARE_SCOPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><span className="field-hint">{scope === 'friends_of_friends' ? '선택한 친구 외에, 내 친구와 친구인 사람들의 "함께 아는 사람 소식"에도 보여요.' : '선택한 친구에게만 보여요.'}</span></label>
      <label className="field"><span className="field-label">전할 말</span><textarea className="input" rows={3} maxLength={300} value={message} onChange={e => setMessage(e.target.value)} placeholder={event.type === '장례식' ? '예) 갑작스러운 소식 전합니다. 마음으로 함께해 주세요.' : '예) 소중한 날에 함께해 주시면 기쁘겠습니다.'} /></label>
      {event.type === '장례식' && <label className="social-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span>유족(가족)에게 소식 공유 동의를 받았어요.</span></label>}
      {error && <p className="form-error" role="alert"><Icon name="CircleAlert" size={16} />{error}</p>}
      <div className="form-actions"><button type="button" className="button button-secondary" onClick={() => onClose(false)}>나중에 보내기</button>{family.length > 0 && <button type="button" className="button button-secondary social-send-all" onClick={() => submit(null, 'family')}><Icon name="HeartHandshake" size={16} />가족 모두에게 보내기 ({family.length}명)</button>}{pending.length > 1 && <button type="button" className="button button-secondary social-send-all" onClick={() => submit(null, 'all')}><Icon name="UsersRound" size={16} />친구 모두에게 보내기 ({pending.length}명)</button>}<button type="submit" className="button button-primary" disabled={!friends.length && scope === 'friends'}><Icon name="Send" size={16} />{selected.size ? `선택한 ${selected.size}명에게 보내기` : '보내기'}</button></div>
    </form>
  </Modal>;
}

/* 일정 상세 › 내가 보낸 현황 */
export function ShareStatus({ event, onShare }) {
  const { user, social, members } = useSocial();
  if (!user) return null;
  const share = shareForEvent(social, user.username, event.id);
  const nameOf = username => members.find(item => item.username === username)?.name || username;
  const responses = share ? shareResponses(social, share) : [];
  const label = { sent: '확인 전', added: '달력에 추가함', hidden: '확인함' };
  return <div className="social-share-status">
    <div className="social-share-status-head"><div><strong>{share ? `${responses.length}명에게 보냈어요` : '아직 친구에게 보내지 않았어요'}</strong><small>{share ? SHARE_SCOPES[share.scope] : '친구가 받은 일정에서 바로 달력에 추가할 수 있어요.'}</small></div><button type="button" className="button button-secondary" onClick={onShare}><Icon name="Send" size={15} />{share ? '더 보내기' : '친구에게 보내기'}</button></div>
    {responses.length > 0 && <ul>{responses.map(item => <li key={item.username}><span className="avatar">{nameOf(item.username).slice(0, 1)}</span>{nameOf(item.username)}<span className={`social-response ${item.status}`}>{label[item.status] || '확인 전'}</span></li>)}</ul>}
  </div>;
}

/* ---------- 일정 관리 › 받은 일정 ---------- */
function ReceivedCard({ item }) {
  const { addToCalendar, hideItem, openEvent } = useSocial();
  const [editing, setEditing] = useState(false);
  const added = item.status === 'added';
  const via = item.kind === 'friend'
    ? item.group === 'family' ? `${item.senderName}님이 가족에게 보낸 일정` : item.designated ? `${item.senderName}님이 나를 지정해 보낸 소식` : `${item.senderName}님이 보낸 일정`
    : item.mutualNames.length ? `${item.mutualNames.slice(0, 2).join(', ')}님을 통해 알게 된 소식` : `함께 아는 친구 ${item.mutualCount}명`;
  return <article className={`social-received-card ${occasionClass(item.type)} ${added ? 'added' : ''}`}>
    <span className={`feature-invitation-icon social-received-icon ${occasionClass(item.type)}`}><Icon name={iconFor(item.type)} size={22} /></span>
    <div className="social-received-body">
      <div className="social-received-tags"><span className={`badge ${occasionClass(item.type)}`}>{item.type}</span><span className="social-via"><Icon name={item.kind === 'friend' ? 'Send' : 'UsersRound'} size={13} />{via}</span>{item.kind === 'mutual' && item.senderName && item.source === 'local' && <span className="social-via">보낸 사람 · {item.senderName}</span>}</div>
      <h3>{item.title}</h3>
      {item.priority?.reasons?.length > 0 && <p className={`priority-reasons ${item.priority.score >= 30 ? 'strong' : ''}`}><Icon name="Star" size={13} />{item.priority.reasons.join(' · ')}</p>}
      <p className="social-received-meta"><span><Icon name="CalendarDays" size={14} />{dateText(item.date, item.time)}{item.endDate && item.endDate !== item.date ? ` ~ ${dateText(item.endDate)}` : ''}</span><span><Icon name="MapPin" size={14} />{item.location || '장소 미정'}</span></p>
      {item.visitingHours && <p className="social-received-note">조문 시간 · {item.visitingHours}</p>}
      {item.message && <blockquote>{item.message}</blockquote>}
      {editing ? (item.source === 'server' ? <ServerPriorityEditor item={item} onDone={() => setEditing(false)} /> : <LocalPriorityEditor item={item} onDone={() => setEditing(false)} />)
        : <button type="button" className="text-button priority-toggle" onClick={() => setEditing(true)}><Icon name="SlidersHorizontal" size={13} />얼마나 챙길지 설정</button>}
    </div>
    <div className="social-received-actions">
      {added ? <><span className="social-status friend"><Icon name="CalendarCheck" size={15} />달력에 추가됨</span><button type="button" className="button button-secondary" onClick={() => openEvent(item.addedEventId)}>달력에서 보기</button></>
        : <><button type="button" className="button button-primary" onClick={() => addToCalendar(item)}><Icon name="CalendarPlus" size={16} />달력에 추가</button><button type="button" className="text-button" onClick={() => hideItem(item)}>숨기기</button></>}
    </div>
  </article>;
}

export function ReceivedScheduleDialog({ initialTab = 'friend', onClose }) {
  const { user, receivedItems, sharedInbox, requireLogin } = useSocial();
  const [tab, setTab] = useState(initialTab);
  const groups = useMemo(() => ({ friend: receivedItems.filter(item => item.kind === 'friend'), mutual: receivedItems.filter(item => item.kind === 'mutual') }), [receivedItems]);
  const items = groups[tab];
  const fresh = list => list.filter(item => item.status === 'new').length;
  if (!user) return <Modal title="받은 일정" subtitle="친구가 보낸 일정과 함께 아는 사람의 소식을 확인하고, 바로 내 달력에 추가해요." onClose={onClose} wide>
    <div className="feature-empty social-login-needed"><EmptyState icon="LockKeyhole" title="로그인하면 받은 일정을 확인할 수 있어요" description="받은 일정에는 보낸 사람과 장소 같은 개인정보가 담겨 있어, 본인 확인 후에만 보여 드려요." />
      <div className="social-login-actions"><button type="button" className="button button-secondary" onClick={() => { onClose(); requireLogin('signup'); }}><Icon name="UserPlus" size={16} />회원가입</button><button type="button" className="button button-primary" onClick={() => { onClose(); requireLogin('login'); }}><Icon name="LogIn" size={16} />로그인</button></div></div>
  </Modal>;
  return <Modal title="받은 일정" subtitle="친구가 보낸 일정과 함께 아는 사람의 소식을 확인하고, 바로 내 달력에 추가해요." onClose={onClose} wide>
    <div className="feature-preview-panel social-received">
      <SectionTabs prefix="received" label="받은 일정 종류" value={tab} onChange={setTab} tabs={[
        { id: 'friend', label: `친구가 보낸 일정${fresh(groups.friend) ? ` ${fresh(groups.friend)}` : ''}`, icon: 'Send' },
        { id: 'mutual', label: `함께 아는 사람 소식${fresh(groups.mutual) ? ` ${fresh(groups.mutual)}` : ''}`, icon: 'UsersRound' },
      ]} />
      <p className="social-received-intro">{tab === 'friend' ? '친구나 가족이 나에게 직접 보낸 경조사예요. 내가 중요하게 기록한 사람의 소식이 먼저 보여요.' : '친구의 친구가 "친구의 친구까지" 알린 소식이에요. 장례 소식은 유족이 공유에 동의한 경우에만 보여요.'}</p>
      {tab === 'mutual' && sharedInbox.status === 'loading' && <p className="notice-status" role="status">소식을 불러오고 있어요.</p>}
      {items.length ? <div className="social-received-list">{items.map(item => <ReceivedCard key={item.key} item={item} />)}</div>
        : <div className="feature-empty"><EmptyState icon={tab === 'friend' ? 'Mail' : 'UsersRound'} title={tab === 'friend' ? '아직 친구가 보낸 일정이 없어요' : '함께 아는 사람의 소식이 없어요'} description={!user && tab === 'friend' ? '로그인하면 친구가 보낸 일정을 확인할 수 있어요.' : '새 소식이 도착하면 이곳과 알림함에 표시돼요.'} />
          {!user && tab === 'friend' && <div className="social-login-actions"><button type="button" className="button button-primary" onClick={() => { onClose(); requireLogin('login'); }}><Icon name="LogIn" size={16} />로그인</button></div>}</div>}
    </div>
  </Modal>;
}

/* ---------- 관계 중요도 (받은 일정 순서에만 쓰임 · 상대에게 공개되지 않음) ---------- */
function PriorityFields({ draft, setDraft, relationOptions }) {
  return <div className="priority-fields">
    <label>중요도<select className="input" value={draft.importance} onChange={e => setDraft({ ...draft, importance: e.target.value })}>{IMPORTANCE_OPTIONS.map(item => <option key={item}>{item}</option>)}</select></label>
    {relationOptions && <label>관계<select className="input" value={draft.relation} onChange={e => setDraft({ ...draft, relation: e.target.value })}><option value="">선택 안 함</option>{relationOptions.map(item => <option key={item}>{item}</option>)}</select></label>}
    <label className="priority-special"><input type="checkbox" checked={draft.special} onChange={e => setDraft({ ...draft, special: e.target.checked })} /><Icon name="Star" size={14} />특별히 챙길 사람</label>
  </div>;
}

function LocalPriorityEditor({ item, onDone }) {
  const { people, updatePerson, addLinkedPerson } = useSocial();
  const person = people.find(entry => entry.id === item.linkedPersonId);
  const [choice, setChoice] = useState('');
  const [relation, setRelation] = useState('친구');
  const [draft, setDraft] = useState({ importance: normalizeImportance(person?.importance), special: person?.special === true });
  if (!person) return <div className="priority-editor">
    <p className="priority-note">먼저 <strong>{item.senderName}</strong>님이 내 인맥의 누구인지 연결해 주세요. 이름이 같아도 자동으로 연결하지 않아요.</p>
    <div className="priority-fields">
      <label>내 인맥<select className="input" value={choice} onChange={e => setChoice(e.target.value)}><option value="">선택해 주세요</option><option value="__new">새 인맥으로 추가</option>{people.map(entry => <option key={entry.id} value={entry.id}>{entry.name} · {entry.relation}</option>)}</select></label>
      {choice === '__new' && <label>관계<select className="input" value={relation} onChange={e => setRelation(e.target.value)}>{RELATION_OPTIONS.map(entry => <option key={entry}>{entry}</option>)}</select></label>}
    </div>
    <div className="priority-actions"><button type="button" className="text-button" onClick={onDone}>취소</button><button type="button" className="button button-primary" disabled={!choice} onClick={async () => {
      const ok = choice === '__new'
        ? await addLinkedPerson({ name: item.senderName, relation, linkedUsername: item.senderUsername })
        : await updatePerson(choice, { linkedUsername: item.senderUsername });
      if (ok) onDone();
    }}>연결하기</button></div>
  </div>;
  return <div className="priority-editor">
    <p className="priority-note">내 인맥 <strong>{person.name}</strong>({person.relation})과 연결돼 있어요. 중요도는 나만 볼 수 있어요.</p>
    <PriorityFields draft={draft} setDraft={setDraft} />
    <div className="priority-actions"><button type="button" className="text-button" onClick={onDone}>닫기</button><button type="button" className="button button-primary" onClick={async () => { if (await updatePerson(person.id, { importance: draft.importance, special: draft.special })) onDone(); }}>저장</button></div>
  </div>;
}

function ServerPriorityEditor({ item, onDone }) {
  const { serverPriorities, saveServerPriority } = useSocial();
  const current = serverPriorities[item.publisherUserId] || {};
  const [draft, setDraft] = useState({ importance: current.importance || '보통', special: current.special === true, relation: current.relation || '' });
  const [saving, setSaving] = useState(false);
  if (!item.publisherUserId) return <div className="priority-editor"><p className="priority-note">보낸 사람이 공개되지 않은 소식이라 중요도를 기록할 수 없어요.</p><div className="priority-actions"><button type="button" className="text-button" onClick={onDone}>닫기</button></div></div>;
  return <div className="priority-editor">
    <p className="priority-note"><strong>{item.senderName}</strong>님을 얼마나 챙길지 기록해요. 받은 일정 순서에만 쓰이고 상대에게 알리지 않아요.</p>
    <PriorityFields draft={draft} setDraft={setDraft} relationOptions={PRIORITY_RELATIONS} />
    <div className="priority-actions"><button type="button" className="text-button" onClick={onDone}>닫기</button><button type="button" className="button button-primary" disabled={saving} onClick={async () => { setSaving(true); const ok = await saveServerPriority(item.publisherUserId, { importance: draft.importance, special: draft.special, relation: draft.relation || null }); setSaving(false); if (ok) onDone(); }}>{saving ? '저장하는 중…' : '저장'}</button></div>
  </div>;
}

/* 친구 카드 › 내 인맥과 연결 */
function PersonLinker({ member }) {
  const { people, updatePerson, addLinkedPerson } = useSocial();
  const linked = people.find(entry => entry.linkedUsername === member.username);
  const [choice, setChoice] = useState('');
  if (linked) return <p className="priority-linked"><Icon name="UserRound" size={14} />내 인맥 · {linked.name} ({linked.relation}{normalizeImportance(linked.importance) !== '보통' ? ` · ${normalizeImportance(linked.importance)}` : ''}{linked.special ? ' · 특별' : ''})</p>;
  return <div className="priority-link-row"><select className="input" aria-label={`${member.name}님과 연결할 내 인맥`} value={choice} onChange={e => setChoice(e.target.value)}><option value="">내 인맥과 연결</option><option value="__new">새 인맥으로 추가</option>{people.map(entry => <option key={entry.id} value={entry.id}>{entry.name} · {entry.relation}</option>)}</select>
    <button type="button" className="button button-secondary" disabled={!choice} onClick={() => choice === '__new' ? addLinkedPerson({ name: member.name, relation: '친구', linkedUsername: member.username }) : updatePerson(choice, { linkedUsername: member.username })}>연결</button></div>;
}
