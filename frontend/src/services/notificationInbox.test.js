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
    assert.ok(['/notices', '/shared-events/recommendations'].includes(path));
    assert.equal(options.userId, 'U001');
    assert.equal(options.signal, controller.signal);
    return { items: path === '/notices' ? [item, item] : [] };
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


test('2촌 공유 추천 API 결과가 받은 일정의 함께 아는 사람 목록에 연결된다', async () => {
  const calls = [];
  const results = {
    '/notices': { items: [] },
    '/shared-events/recommendations': { items: [{
      id: 'DSE-2HOP', reason_code: 'friend_of_friend', publisher_name: '테스트 사용자',
      title: '합성 시연 결혼식', category: '결혼', start_date: '2026-11-08', end_date: '2026-11-08', region: '서울',
    }] },
  };
  const items = await loadSharedNotices('ACC:test12345', { request: async (path, options) => {
    calls.push(path);
    assert.equal(options.userId, 'ACC:test12345');
    return results[path];
  } });
  assert.deepEqual(calls.sort(), ['/notices', '/shared-events/recommendations']);
  assert.equal(items.length, 1);
  assert.equal(items[0].relation_type, 'friend_of_friend');
  assert.equal(items[0].notice.id, 'DSE-2HOP');
  assert.equal(items[0].notice.category, '결혼');
  assert.equal(items[0].publisher_name, '테스트 사용자');
});

test('서버 공유 소식 응답이 올바르지 않으면 빈 목록 성공으로 처리하지 않는다', async () => {
  for (const invalid of [{}, { items: {} }, { items: [{ title: '식별자 누락' }] }]) {
    await assert.rejects(loadSharedNotices('ACC:test12345', { request: async path =>
      path === '/notices' ? { items: [] } : invalid }), /형식/);
  }
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
