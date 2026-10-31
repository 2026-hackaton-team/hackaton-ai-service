import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeSocial, requestFriend, respondFriend, incomingRequests, upsertShare, setReceipt } from './socialStore.js';
import { buildReceivedItems, cleanText, itemToEvent, noticeToItem } from './receivedItems.js';

const notice = { relation_type: 'friend_of_friend', publisher_name: '김도윤', mutual_count: 2, notice: { id: 'N001', category: '장례', title: '동료 가족의 부고', start_date: '2026-10-30', end_date: '2026-11-01', region: '서울', venue: '가상 서울 마음빛 장례식장', room: '가상 1호실', visiting_hours: '가상 조문 시간 10:00~20:00', mourner: { name: '김도윤', affiliation: '해든기획팀', deceased_relation: '부친' } } };

test('server notices become clean funeral items', () => {
  const item = noticeToItem(notice, { profileId: 'U001' });
  assert.equal(item.kind, 'mutual');
  assert.equal(item.type, '장례식');
  assert.equal(item.location, '서울 마음빛 장례식장 · 1호실');
  assert.equal(item.time, '10:00');
  assert.equal(item.visitingHours, '조문 시간 10:00~20:00');
  assert.equal(cleanText('가상 주소: 서울 가상구'), '서울 구');
  const event = itemToEvent(item, 'p1');
  assert.equal(event.reminderDays, 0);
  assert.equal(event.source.key, 'notice:U001:N001');
});

test('received items track calendar status and hidden items', () => {
  let s = normalizeSocial(null);
  s = requestFriend(s, 'host', 'bob'); s = respondFriend(s, incomingRequests(s, 'bob')[0].id, 'bob', true);
  s = upsertShare(s, { owner: 'host', ownerName: '호스트', event: { id: 'e1', title: '호스트의 결혼식', type: '결혼식', date: '2026-11-21', time: '13:00', location: '홀' }, recipients: ['bob'], message: '와 주세요' });
  const base = { social: s, me: 'bob', notices: [notice], profileId: 'U001' };
  let items = buildReceivedItems(base);
  assert.deepEqual(items.map(item => [item.kind, item.status]), [['mutual', 'new'], ['friend', 'new']]);
  const added = items.find(item => item.kind === 'friend');
  items = buildReceivedItems({ ...base, events: [{ id: 'mine', source: { key: added.key } }] });
  assert.equal(items.find(item => item.kind === 'friend').addedEventId, 'mine');
  items = buildReceivedItems({ ...base, social: setReceipt(s, 'bob', 'notice:U001:N001', { status: 'hidden' }) });
  assert.equal(items.length, 1);
  assert.match(itemToEvent(added, 'p').memo, /와 주세요/);
});

test('received items are ordered by the importance I recorded, not only by date', () => {
  let s = normalizeSocial(null);
  for (const friend of ['early', 'late']) { s = requestFriend(s, friend, 'me'); s = respondFriend(s, incomingRequests(s, 'me')[0].id, 'me', true); }
  s = upsertShare(s, { owner: 'early', ownerName: '먼저', event: { id: 'a', title: '먼저 결혼식', type: '결혼식', date: '2026-11-03', time: '', location: '' }, recipients: ['me'] });
  s = upsertShare(s, { owner: 'late', ownerName: '나중', event: { id: 'b', title: '고모 칠순', type: '칠순', date: '2026-12-20', time: '', location: '' }, recipients: ['me'], group: 'family' });
  const base = { social: s, me: 'me', today: '2026-10-31' };
  assert.deepEqual(buildReceivedItems(base).map(item => item.title), ['먼저 결혼식', '고모 칠순']);
  const people = [{ id: 'p', name: '고모', relation: '가족', importance: '매우 중요', special: true, linkedUsername: 'late' }];
  const items = buildReceivedItems({ ...base, people });
  assert.deepEqual(items.map(item => item.title), ['고모 칠순', '먼저 결혼식']);
  assert.equal(items[0].group, 'family');
  assert.deepEqual(items[0].priority.reasons, ['‘매우 중요’로 기록한 가족', '특별히 챙길 사람']);
  assert.equal(items[0].linkedPersonId, 'p');
});

test('designated server notices arrive as items sent to me', () => {
  const entry = { relation_type: 'designated', recipient_group: 'family', publisher_name: '최다인', publisher_user_id: 'U009', priority_score: 0, priority_reasons: [], notice: { id: 'D001', category: '칠순', title: '어머니 칠순 잔치', start_date: '2026-11-05', end_date: '2026-11-05', time: '12:00', venue: '한정식 가온' } };
  const [item] = buildReceivedItems({ social: normalizeSocial(null), me: 'me', notices: [entry], profileId: 'U002', today: '2026-10-31' });
  assert.equal(item.kind, 'friend'); assert.equal(item.designated, true); assert.equal(item.time, '12:00');
  assert.equal(item.type, '칠순'); assert.equal(item.publisherUserId, 'U009');
  assert.deepEqual(item.priority.reasons, ['5일 남음']);
});
