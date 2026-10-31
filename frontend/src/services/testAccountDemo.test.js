// 시연 계정의 로그인 검증을 확인한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { matchesTestLogin } from './testAccountDemo.js';
import { initialEvents, initialPeople, initialRecords } from '../data.js';

test('시연 계정은 지정된 아이디와 비밀번호만 허용한다', () => {
  assert.equal(matchesTestLogin('test1234', 'test1234'), true);
  assert.equal(matchesTestLogin('TEST1234', 'test1234'), true);
  assert.equal(matchesTestLogin('test1234', 'wrong1234'), false);
  assert.equal(matchesTestLogin('other', 'test1234'), false);
});

test('처음 접속하면 인맥·일정·장부가 비어 있다', () => {
  assert.deepEqual(initialPeople, []);
  assert.deepEqual(initialEvents, []);
  assert.deepEqual(initialRecords, []);
});
