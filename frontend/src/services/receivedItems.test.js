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
