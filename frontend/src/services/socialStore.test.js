import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeSocial, requestFriend, respondFriend, relationStatus, friendsOf, mutualFriends, incomingRequests, upsertShare, receivedShares, setReceipt, receiptOf, shareResponses, searchMembers, cancelFriendRequest, updateSharedEvent } from './socialStore.js';

const befriend = (state, a, b) => { const s = requestFriend(state, a, b); return respondFriend(s, incomingRequests(s, b)[0].id, b, true); };
const event = { id: 'e1', title: '채해커 결혼식', type: '결혼식', date: '2026-11-21', time: '13:00', location: '라온 웨딩홀', memo: '' };

test('friend requests become friendships only after acceptance', () => {
  let s = normalizeSocial(null);
  s = requestFriend(s, 'Alice', 'bob');
  assert.equal(relationStatus(s, 'alice', 'bob'), 'requested');
  assert.equal(relationStatus(s, 'bob', 'alice'), 'incoming');
  assert.deepEqual(friendsOf(s, 'alice'), []);
  s = respondFriend(s, incomingRequests(s, 'bob')[0].id, 'bob', true);
  assert.deepEqual(friendsOf(s, 'alice'), ['bob']);
  assert.throws(() => requestFriend(s, 'alice', 'ALICE'));
  const pending = requestFriend(s, 'carol', 'alice');
  const declined = respondFriend(pending, incomingRequests(pending, 'alice')[0].id, 'alice', false);
  assert.equal(relationStatus(declined, 'alice', 'carol'), 'none');
  assert.equal(relationStatus(cancelFriendRequest(requestFriend(s, 'carol', 'dan'), 'carol', 'dan'), 'carol', 'dan'), 'none');
});

test('a reverse request accepts the pending one', () => {
  const s = requestFriend(requestFriend(normalizeSocial(null), 'a', 'b'), 'b', 'a');
  assert.equal(relationStatus(s, 'a', 'b'), 'friend');
});

test('shares reach chosen friends, and friends of friends only when the scope allows it', () => {
  let s = befriend(befriend(befriend(normalizeSocial(null), 'host', 'bob'), 'bob', 'carol'), 'host', 'dan');
  assert.throws(() => upsertShare(s, { owner: 'host', event, scope: 'friends', recipients: ['carol'] }), /친구/);
  s = upsertShare(s, { owner: 'host', ownerName: '호스트', event, scope: 'friends', recipients: ['bob', 'carol'] });
  assert.deepEqual(s.shares[0].recipients, ['bob']);
  assert.equal(receivedShares(s, 'bob')[0].kind, 'friend');
  assert.equal(receivedShares(s, 'carol').length, 0);
  assert.equal(receivedShares(s, 'dan').length, 0);
  s = upsertShare(s, { owner: 'host', event, scope: 'friends_of_friends', recipients: [] });
  assert.equal(s.shares.length, 1);
  const carol = receivedShares(s, 'carol');
  assert.equal(carol[0].kind, 'mutual');
  assert.deepEqual(carol[0].mutual, ['bob']);
  assert.equal(receivedShares(s, 'dan').length, 0, 'direct friends who were not chosen do not see it');
  assert.equal(receivedShares(s, 'host').length, 0);
  assert.deepEqual(mutualFriends(s, 'carol', 'host'), ['bob']);
  s = updateSharedEvent(s, 'host', { ...event, location: '새 장소' });
  assert.equal(s.shares[0].event.location, '새 장소');
});

test('receipts are kept per user and reported back to the sender', () => {
  let s = befriend(normalizeSocial(null), 'host', 'bob');
  s = upsertShare(s, { owner: 'host', event, recipients: ['bob'] });
  const itemKey = `share:${s.shares[0].id}`;
  s = setReceipt(s, 'bob', itemKey, { status: 'added', eventId: 'x' });
  assert.equal(receiptOf(s, 'bob', itemKey).status, 'added');
  assert.equal(receiptOf(s, 'host', itemKey), undefined);
  assert.deepEqual(shareResponses(s, s.shares[0]), [{ username: 'bob', status: 'added' }]);
});

test('member search hides private profiles and private work details', () => {
  const accounts = [
    { username: 'me', name: '나', visibility: '전체 공개' },
    { username: 'open', name: '공개', workplace: '마음전자', visibility: '전체 공개' },
    { username: 'friendsonly', name: '친구공개', workplace: '비밀회사', visibility: '친구에게만 공개' },
    { username: 'hidden', name: '숨김', visibility: '비공개' },
  ];
  const s = normalizeSocial(null);
  const list = searchMembers(s, accounts, 'me');
  assert.deepEqual(list.map(m => m.username).sort(), ['friendsonly', 'open']);
  assert.equal(list.find(m => m.username === 'friendsonly').workplace, '');
  assert.equal(list.find(m => m.username === 'open').workplace, '마음전자');
  assert.deepEqual(searchMembers(s, accounts, 'me', 'hidden').map(m => m.username), ['hidden']);
  assert.deepEqual(searchMembers(s, accounts, 'me', 'hid').map(m => m.username), []);
});
