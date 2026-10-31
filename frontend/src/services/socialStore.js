// 마음결 친구 · 일정 공유 저장소
// 백엔드 API가 준비되기 전까지 같은 브라우저의 localStorage 에 친구 관계와 공유 일정을 보관한다.
// 모든 함수는 (state → 새 state) 순수 함수로 두고, 저장/구독은 아래 store 함수가 담당한다.
// 나중에 서버로 옮길 때는 load/save 부분만 API 호출로 바꾸면 된다.

export const SOCIAL_KEY = 'maeum-social-v1';
export const ACCOUNTS_KEY = 'maeum-demo-accounts-v1';
export const SOCIAL_EVENT = 'maeum-social-change';
export const SHARE_SCOPES = Object.freeze({ friends: '친구에게 보내기', friends_of_friends: '친구의 친구까지 알리기' });

const emptyState = () => ({ friendships: [], shares: [], receipts: {} });
const key = value => String(value || '').trim().toLowerCase();
const newId = prefix => `${prefix}-${globalThis.crypto?.randomUUID?.() || Date.now().toString(36) + Math.random().toString(36).slice(2)}`;
const now = () => new Date().toISOString();

export function normalizeSocial(raw) {
  const base = emptyState();
  if (!raw || typeof raw !== 'object') return base;
  return {
    friendships: Array.isArray(raw.friendships) ? raw.friendships.filter(item => item?.from && item?.to) : base.friendships,
    shares: Array.isArray(raw.shares) ? raw.shares.filter(item => item?.owner && item?.event) : base.shares,
    receipts: raw.receipts && typeof raw.receipts === 'object' ? raw.receipts : base.receipts,
  };
}

/* ---------- 친구 관계 ---------- */
const pairOf = (a, b) => item => (key(item.from) === key(a) && key(item.to) === key(b)) || (key(item.from) === key(b) && key(item.to) === key(a));

export function friendsOf(state, username) {
  const me = key(username);
  if (!me) return [];
  return state.friendships.filter(item => item.status === 'accepted' && (key(item.from) === me || key(item.to) === me))
    .map(item => key(item.from) === me ? key(item.to) : key(item.from));
}

export function relationStatus(state, me, other) {
  const link = state.friendships.find(pairOf(me, other));
  if (!link || link.status === 'declined') return 'none';
  if (link.status === 'accepted') return 'friend';
  return key(link.from) === key(me) ? 'requested' : 'incoming';
}

export function mutualFriends(state, a, b) {
  const others = new Set(friendsOf(state, b));
  return friendsOf(state, a).filter(name => others.has(name) && name !== key(a) && name !== key(b));
}

export function requestFriend(state, from, to) {
  if (!key(from) || !key(to) || key(from) === key(to)) throw new Error('친구로 추가할 회원을 다시 확인해 주세요.');
  const existing = state.friendships.find(pairOf(from, to));
  if (existing?.status === 'accepted') return state;
  // 상대가 먼저 요청했다면 바로 친구가 된다.
  if (existing?.status === 'pending' && key(existing.to) === key(from)) return respondFriend(state, existing.id, key(from), true);
  const rest = state.friendships.filter(item => item !== existing);
  return { ...state, friendships: [...rest, { id: newId('friend'), from: key(from), to: key(to), status: 'pending', createdAt: now() }] };
}

export function cancelFriendRequest(state, from, to) {
  return { ...state, friendships: state.friendships.filter(item => !(item.status === 'pending' && key(item.from) === key(from) && key(item.to) === key(to))) };
}

export function respondFriend(state, id, me, accept) {
  return { ...state, friendships: state.friendships.map(item => item.id === id && key(item.to) === key(me) && item.status === 'pending'
    ? { ...item, status: accept ? 'accepted' : 'declined', respondedAt: now() } : item) };
}

export function incomingRequests(state, me) {
  return state.friendships.filter(item => item.status === 'pending' && key(item.to) === key(me));
}
export function outgoingRequests(state, me) {
  return state.friendships.filter(item => item.status === 'pending' && key(item.from) === key(me));
}

/* ---------- 일정 공유 ---------- */
export function eventSnapshot(event) {
  const { title, type, date, time, location, memo } = event;
  return { title, type, date, time: time || '', location: location || '', memo: memo || '' };
}

export function shareForEvent(state, owner, eventId) {
  return state.shares.find(item => key(item.owner) === key(owner) && item.eventId === eventId);
}

export function upsertShare(state, { owner, ownerName, event, scope = 'friends', message = '', recipients = [] }) {
  if (!key(owner)) throw new Error('로그인한 뒤 일정을 보낼 수 있어요.');
  if (!SHARE_SCOPES[scope]) throw new Error('공유 범위를 선택해 주세요.');
  const friends = new Set(friendsOf(state, owner));
  const targets = [...new Set(recipients.map(key))].filter(name => friends.has(name));
  if (!targets.length && scope === 'friends') throw new Error('일정을 받을 친구를 한 명 이상 선택해 주세요.');
  const existing = shareForEvent(state, owner, event.id);
  const next = {
    id: existing?.id || newId('share'), owner: key(owner), ownerName: ownerName || owner, eventId: event.id,
    event: eventSnapshot(event), scope, message: String(message || '').trim().slice(0, 300),
    recipients: [...new Set([...(existing?.recipients || []), ...targets])],
    createdAt: existing?.createdAt || now(), updatedAt: now(),
  };
  return { ...state, shares: existing ? state.shares.map(item => item === existing ? next : item) : [...state.shares, next] };
}

export function updateSharedEvent(state, owner, event) {
  const existing = shareForEvent(state, owner, event.id);
  if (!existing) return state;
  return { ...state, shares: state.shares.map(item => item === existing ? { ...item, event: eventSnapshot(event), updatedAt: now() } : item) };
}

export function removeShare(state, owner, eventId) {
  return { ...state, shares: state.shares.filter(item => !(key(item.owner) === key(owner) && item.eventId === eventId)) };
}

/** 받는 사람 기준으로 보이는 공유 일정: 직접 받은 일정(friend) + 친구의 친구 소식(mutual) */
export function receivedShares(state, me) {
  const viewer = key(me);
  if (!viewer) return [];
  const myFriends = new Set(friendsOf(state, viewer));
  const result = [];
  for (const share of state.shares) {
    if (key(share.owner) === viewer) continue;
    if (share.recipients.map(key).includes(viewer)) { result.push({ share, kind: 'friend', mutual: [] }); continue; }
    if (share.scope !== 'friends_of_friends') continue;
    if (myFriends.has(key(share.owner))) continue; // 직접 친구에게는 보낸 사람이 고른 경우에만 보인다.
    const mutual = mutualFriends(state, viewer, share.owner);
    if (mutual.length) result.push({ share, kind: 'mutual', mutual });
  }
  return result;
}

/* ---------- 받은 일정 처리 상태 (달력 추가 · 숨김) ---------- */
export function receiptOf(state, me, itemKey) {
  return state.receipts?.[key(me) || 'guest']?.[itemKey];
}
export function setReceipt(state, me, itemKey, patch) {
  const owner = key(me) || 'guest';
  const mine = state.receipts?.[owner] || {};
  return { ...state, receipts: { ...state.receipts, [owner]: { ...mine, [itemKey]: { ...mine[itemKey], ...patch, at: now() } } } };
}

/** 보낸 사람이 보는 받은 사람별 상태 */
export function shareResponses(state, share) {
  const itemKey = `share:${share.id}`;
  return share.recipients.map(name => ({ username: name, status: receiptOf(state, name, itemKey)?.status || 'sent' }));
}

/* ---------- 회원 목록 (같은 브라우저의 가입 계정) ---------- */
export function readMembers(storage = globalThis.localStorage) {
  try {
    const raw = JSON.parse(storage.getItem(ACCOUNTS_KEY) || '[]');
    return Array.isArray(raw) ? raw.filter(item => item?.username) : [];
  } catch { return []; }
}

export function visibleMember(account, { isFriend = false } = {}) {
  const open = account.visibility === '전체 공개' || (isFriend && account.visibility === '친구에게만 공개');
  return {
    username: key(account.username), name: account.name || account.username,
    workplace: open ? account.workplace || '' : '', organization: open ? account.organization || '' : '',
    workType: open ? account.workType || '' : '', visibility: account.visibility || '',
  };
}

/** 친구 찾기 목록: 비공개 회원은 아이디를 정확히 입력했을 때만 보인다. */
export function searchMembers(state, accounts, me, query = '') {
  const viewer = key(me);
  const q = String(query || '').trim().toLowerCase();
  return accounts.filter(account => key(account.username) !== viewer).map(account => {
    const status = relationStatus(state, viewer, account.username);
    return { ...visibleMember(account, { isFriend: status === 'friend' }), status, mutual: mutualFriends(state, viewer, account.username) };
  }).filter(member => {
    if (member.visibility === '비공개' && member.status !== 'friend') return q && member.username === q;
    if (!q) return true;
    return `${member.name} ${member.username} ${member.workplace} ${member.organization}`.toLowerCase().includes(q);
  }).sort((a, b) => b.mutual.length - a.mutual.length || a.name.localeCompare(b.name, 'ko'));
}

/* ---------- 저장 · 구독 ---------- */
export function loadSocial(storage = globalThis.localStorage) {
  try { return normalizeSocial(JSON.parse(storage.getItem(SOCIAL_KEY) || 'null')); } catch { return emptyState(); }
}
export function saveSocial(state, storage = globalThis.localStorage, events = globalThis.window) {
  storage.setItem(SOCIAL_KEY, JSON.stringify(state));
  events?.dispatchEvent?.(new Event(SOCIAL_EVENT));
  return state;
}
/** 최신 저장 상태를 읽어 변경한 뒤 저장한다. (다른 탭에서 바뀐 내용도 덮어쓰지 않도록) */
export function mutateSocial(change, storage = globalThis.localStorage, events = globalThis.window) {
  return saveSocial(change(loadSocial(storage)), storage, events);
}
