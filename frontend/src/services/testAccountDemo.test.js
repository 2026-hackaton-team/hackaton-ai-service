// 시연 계정의 로그인 검증과 친구 연결이 반복해도 안전한지 확인한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { matchesTestLogin, seedTestSocial } from './testAccountDemo.js';
import { ACCOUNTS_KEY, SOCIAL_KEY, friendsOf, receivedShares } from './socialStore.js';

function storage() {
  const data = new Map();
  return {
    getItem(key) { return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { data.set(key, String(value)); },
  };
}

test('시연 계정은 지정된 아이디와 비밀번호만 허용한다', () => {
  assert.equal(matchesTestLogin('test1234', 'test1234'), true);
  assert.equal(matchesTestLogin('TEST1234', 'test1234'), true);
  assert.equal(matchesTestLogin('test1234', 'wrong1234'), false);
  assert.equal(matchesTestLogin('other', 'test1234'), false);
});

test('다른 로컬 계정을 보존하고 테스트 친구와 비친구 소식을 시드한다', () => {
  const store = storage();
  store.setItem(ACCOUNTS_KEY, JSON.stringify([{ username: 'original', name: '기존 회원' }]));
  const events = { dispatchEvent() {} };
  seedTestSocial(store, events);
  const members = JSON.parse(store.getItem(ACCOUNTS_KEY));
  assert.equal(members.length, 13);
  assert.equal(members[0].username, 'original');
  const social = JSON.parse(store.getItem(SOCIAL_KEY));
  assert.equal(friendsOf(social, 'test1234').length, 9);
  const received = receivedShares(social, 'test1234');
  assert.equal(received.filter(item => item.kind === 'friend').length, 2);
  assert.equal(received.filter(item => item.kind === 'mutual').length, 1);
  assert.equal(friendsOf(social, 'test1234').includes('test_friend10'), false);

  const first = store.getItem(SOCIAL_KEY);
  seedTestSocial(store, events);
  assert.equal(store.getItem(SOCIAL_KEY), first);
  assert.equal(JSON.parse(store.getItem(ACCOUNTS_KEY)).length, 13);
});
