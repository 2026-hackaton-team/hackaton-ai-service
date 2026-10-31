import test from 'node:test';
import assert from 'node:assert/strict';
import { loadSharedNotices, sharedNoticeId } from './noticeInbox.js';
import { DEMO_ACCOUNT_EVENT, getDemoAccount, setDemoAccount } from './demoAccount.js';

test('no account never queries a shared inbox', async () => {
  assert.deepEqual(await loadSharedNotices('', { request: () => { throw new Error('must not query'); } }), []);
});

test('shared inbox carries the selected account and cancellation signal and deduplicates cards', async () => {
  const controller = new AbortController();
  const item = { notice: { id: 'N001', title: '공유 소식' }, relation_type: 'friend_of_friend' };
  const result = await loadSharedNotices('U001', { signal: controller.signal, request: async (path, options) => {
    assert.equal(path, '/notices');
    assert.equal(options.userId, 'U001');
    assert.equal(options.signal, controller.signal);
    return { items: [item, item] };
  } });
  assert.equal(result.length, 1);
  assert.equal(result[0].notice.id, 'N001');
});

test('malformed, failed, or cancelled responses do not become a successful empty inbox', async () => {
  for (const result of [{}, { items: {} }, { items: [{ notice: { title: 'missing id' } }] }]) {
    await assert.rejects(loadSharedNotices('U001', { request: async () => result }), /형식/);
  }
  await assert.rejects(loadSharedNotices('U001', { request: async () => { throw new Error('offline'); } }), /offline/);
  await assert.rejects(loadSharedNotices('U001', { request: async () => { throw new DOMException('cancelled', 'AbortError'); } }), { name: 'AbortError' });
});

test('read state stays separate between accounts, notices, and local event reminders', () => {
  assert.notEqual(sharedNoticeId('U001', 'N001'), sharedNoticeId('U002', 'N001'));
  assert.notEqual(sharedNoticeId('a:b', 'c'), sharedNoticeId('a', 'b:c'));
  assert.notEqual(sharedNoticeId('U001', 'N001'), 'event-N001-2026-10-30');
});

test('demo account changes notify both screens and clearing removes the previous account', () => {
  const values = new Map();
  const storage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  const events = new EventTarget();
  const seen = [];
  events.addEventListener(DEMO_ACCOUNT_EVENT, () => seen.push(getDemoAccount(storage)));
  setDemoAccount('U001', { storage, events });
  setDemoAccount('U001', { storage, events });
  setDemoAccount('U002', { storage, events });
  setDemoAccount('', { storage, events });
  assert.deepEqual(seen, ['U001', 'U002', '']);
  assert.equal(getDemoAccount(storage), '');
});
