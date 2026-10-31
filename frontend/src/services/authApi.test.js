// 서버 로그인 결과를 브라우저에 남기는 범위를 확인한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { AUTH_TOKEN_KEY, getAuthToken, memberWorkspace, rememberMember } from './authApi.js';

function storage() {
  const data = new Map();
  return {
    getItem(key) { return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { data.set(key, String(value)); },
    removeItem(key) { data.delete(key); },
  };
}

test('회원 작업공간 ID는 서버와 같은 규칙을 쓴다', () => {
  assert.equal(memberWorkspace(' Hong_GD '), 'ACC:hong_gd');
});

test('친구 찾기 목록에는 공개 정보만 남기고 같은 아이디는 갱신한다', () => {
  const store = storage();
  store.setItem('maeum-demo-accounts-v1', JSON.stringify([{ username: 'hong_gd', name: '예전 이름', salt: 's', hash: 'h' }, { username: 'kim' }]));
  rememberMember({ username: 'hong_gd', name: '홍길동', phone: '01012345678', email: 'hong@example.com', workplace: '마음전자', visibility: '전체 공개' }, store);
  const members = JSON.parse(store.getItem('maeum-demo-accounts-v1'));
  assert.equal(members.length, 2);
  const hong = members.find(item => item.username === 'hong_gd');
  assert.equal(hong.name, '홍길동');
  assert.equal(hong.workplace, '마음전자');
  for (const field of ['phone', 'email', 'salt', 'hash', 'password']) assert.equal(field in hong, false);
});

test('토큰을 읽지 못해도 오류 없이 로그아웃 상태로 본다', () => {
  assert.equal(getAuthToken(storage()), '');
  assert.equal(getAuthToken({ getItem() { throw new Error('blocked'); } }), '');
  const store = storage();
  store.setItem(AUTH_TOKEN_KEY, 'abc');
  assert.equal(getAuthToken(store), 'abc');
});
