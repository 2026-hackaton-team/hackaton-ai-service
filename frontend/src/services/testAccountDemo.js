// 테스트 계정으로 로그인했을 때만 브라우저 친구·받은 일정을 채운다.
import { ACCOUNTS_KEY, SOCIAL_KEY, SOCIAL_EVENT, normalizeSocial } from './socialStore.js';

export const TEST_USERNAME = 'test1234';
export const TEST_PROFILE_ID = 'TEST1234';

const names = ['윤서진', '김도윤', '이수빈', '박하은', '정유림', '한소민', '최유정', '오지훈', '서예린', '강민혁', '윤지아', '송재현'];
const username = index => 'test_friend' + String(index + 1).padStart(2, '0');
const dateFromNow = days => {
  const day = new Date();
  day.setDate(day.getDate() + days);
  return day.toISOString().slice(0, 10);
};

export function seedTestSocial(storage = globalThis.localStorage, events = globalThis.window) {
  const accounts = JSON.parse(storage.getItem(ACCOUNTS_KEY) || '[]');
  if (!Array.isArray(accounts)) throw new Error('invalid-storage');
  const members = names.map((name, i) => ({
    username: username(i), name,
    email: username(i) + '@example.invalid',
    workplace: '가상 마음결 모임', organization: '시연팀',
    workType: '민간 기업 임직원', visibility: '전체 공개',
  }));
  const existing = new Set(accounts.map(item => String(item.username || '').toLowerCase()));
  const added = members.filter(item => !existing.has(item.username));
  if (added.length) storage.setItem(ACCOUNTS_KEY, JSON.stringify([...accounts, ...added]));

  const social = normalizeSocial(JSON.parse(storage.getItem(SOCIAL_KEY) || 'null'));
  const links = [
    ...Array.from({ length: 9 }, (_, i) => ['test1234', username(i)]),
    [username(0), username(9)],
    [username(1), username(10)],
    [username(2), username(11)],
  ];
  const pairs = new Set(social.friendships.map(item => [item.from, item.to].sort().join(':')));
  const friendships = [...social.friendships];
  for (const [from, to] of links) {
    const key = [from, to].sort().join(':');
    if (pairs.has(key)) continue;
    friendships.push({ id: 'test-link-' + key, from, to, status: 'accepted', createdAt: '2026-10-31T00:00:00Z' });
    pairs.add(key);
  }

  const shares = [...social.shares];
  const demoShares = [
    { id: 'test-share-01', owner: username(0), ownerName: names[0], scope: 'friends',
      recipients: [TEST_USERNAME], title: '윤서진 결혼식', type: '결혼식', days: 10 },
    { id: 'test-share-02', owner: username(1), ownerName: names[1], scope: 'friends',
      recipients: [TEST_USERNAME], title: '김도윤 가족 환갑잔치', type: '환갑', days: 24 },
    { id: 'test-share-03', owner: username(9), ownerName: names[9], scope: 'friends_of_friends',
      recipients: [], title: '강민혁 돌잔치', type: '돌잔치', days: 31 },
  ];
  for (const item of demoShares) {
    if (shares.some(existing => existing.id === item.id)) continue;
    shares.push({
      id: item.id, owner: item.owner, ownerName: item.ownerName,
      eventId: item.id + '-event', scope: item.scope, recipients: item.recipients,
      event: { title: item.title, type: item.type, date: dateFromNow(item.days),
        time: '12:00', location: '가상 서울 행사장', memo: '합성 테스트 소식' },
      message: '마음결 시연용 일정입니다.', group: null,
      createdAt: '2026-10-31T00:00:00Z', updatedAt: '2026-10-31T00:00:00Z',
    });
  }
  if (friendships.length !== social.friendships.length || shares.length !== social.shares.length) {
    storage.setItem(SOCIAL_KEY, JSON.stringify({ ...social, friendships, shares }));
  }
  events?.dispatchEvent?.(new Event(SOCIAL_EVENT));
}
