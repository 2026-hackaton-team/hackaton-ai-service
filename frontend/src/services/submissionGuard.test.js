import test from 'node:test';
import assert from 'node:assert/strict';
import { createSubmissionGuard } from './submissionGuard.js';

test('same-tick clicks and Enter submissions create one record while saving', async () => {
  const states = [];
  const submit = createSubmissionGuard(value => states.push(value));
  const records = [];
  let finish;
  const waiting = new Promise(resolve => { finish = resolve; });
  const save = async () => { await waiting; records.push({ id: records.length + 1 }); return true; };
  const first = submit(save);
  const second = submit(save);
  const third = submit(save);
  assert.deepEqual(states, [true]);
  assert.equal(await second, false);
  assert.equal(await third, false);
  assert.deepEqual(records, []);
  finish();
  assert.equal(await first, true);
  assert.equal(records.length, 1);
  assert.deepEqual(states, [true, false]);
  assert.equal(await submit(save), true);
  assert.equal(records.length, 2);
});

test('false save result unlocks the same form so it can be retried', async () => {
  const states = [];
  const submit = createSubmissionGuard(value => states.push(value));
  assert.equal(await submit(() => false), false);
  assert.equal(await submit(() => 'saved'), 'saved');
  assert.deepEqual(states, [true, false, true, false]);
});

test('synchronous exceptions and rejected saves both unlock the form', async () => {
  const states = [];
  const submit = createSubmissionGuard(value => states.push(value));
  const failure = new Error('저장 실패');
  await assert.rejects(submit(() => { throw failure; }), error => error === failure);
  await assert.rejects(submit(() => Promise.reject(failure)), error => error === failure);
  assert.equal(await submit(() => true), true);
  assert.deepEqual(states, [true, false, true, false, true, false]);
});

test('separate open forms do not block each other', async () => {
  const first = createSubmissionGuard();
  const second = createSubmissionGuard();
  let finish;
  const saving = first(() => new Promise(resolve => { finish = resolve; }));
  assert.equal(await second(() => true), true);
  finish(true);
  assert.equal(await saving, true);
});
