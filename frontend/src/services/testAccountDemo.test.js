// 처음 접속한 브라우저가 빈 상태로 시작하는지 확인한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { initialEvents, initialPeople, initialRecords } from '../data.js';

test('처음 접속하면 인맥·일정·장부가 비어 있다', () => {
  assert.deepEqual(initialPeople, []);
  assert.deepEqual(initialEvents, []);
  assert.deepEqual(initialRecords, []);
});
