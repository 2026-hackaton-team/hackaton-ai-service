import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, createApiClient } from './apiClient.js';
import { backendOptionsFromEnv, createBackendServices } from './backend.js';

test('backend stays disabled by default and never calls fetch', async () => {
  let calls = 0;
  const api = createApiClient({ fetchImpl: () => { calls++; } });
  await assert.rejects(api.request('/workspace'), error => error instanceof ApiError && error.code === 'backend_disabled');
  assert.equal(calls, 0);
  assert.deepEqual(backendOptionsFromEnv({ VITE_API_ENABLED: 'false' }), { enabled: false, baseUrl: '' });
  assert.deepEqual(backendOptionsFromEnv({ VITE_API_ENABLED: 'true', VITE_API_BASE_URL: '/api' }), { enabled: true, baseUrl: '/api' });
});

test('cookie session, JSON body, CSRF and encoded resource IDs reach the proposed endpoint', async () => {
  const calls = [];
  const api = createBackendServices({ enabled: true, baseUrl: 'https://example.test/api/', getCsrfToken: () => 'csrf-test', fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ id: 'p/한글', name: '민수', relation: '동호회', importance: '매우 중요' }), { status: 200 });
  } });
  const result = await api.people.update('p/한글', { relation: '동호회', importance: '매우 중요' });
  assert.equal(result.relation, '동호회');
  assert.equal(calls[0].url, 'https://example.test/api/people/p%2F%ED%95%9C%EA%B8%80');
  assert.equal(calls[0].options.credentials, 'include');
  assert.equal(calls[0].options.headers['X-CSRF-Token'], 'csrf-test');
  assert.deepEqual(JSON.parse(calls[0].options.body), { relation: '동호회', importance: '매우 중요' });
});

test('query values are encoded, GET has no JSON body and delete accepts 204', async () => {
  const calls = [];
  const api = createBackendServices({ enabled: true, baseUrl: '/api', fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return options.method === 'DELETE' ? new Response(null, { status: 204 }) : new Response('{"items":[],"nextCursor":null}');
  } });
  assert.deepEqual(await api.people.list({ query: '친구 & 가족', cursor: undefined }), { items: [], nextCursor: null });
  assert.equal(calls[0].url, '/api/people?query=%EC%B9%9C%EA%B5%AC+%26+%EA%B0%80%EC%A1%B1');
  assert.equal(calls[0].options.body, undefined);
  assert.equal(calls[0].options.headers['Content-Type'], undefined);
  assert.equal(await api.records.remove('r1'), null);
});

test('JSON API failures keep status, stable code and field errors without a local success fallback', async () => {
  const api = createApiClient({ enabled: true, baseUrl: '/api', fetchImpl: async () => new Response(JSON.stringify({ error: { code: 'validation_failed', message: '관계를 확인해 주세요.', fields: { relation: 'max40' } } }), { status: 422 }) });
  await assert.rejects(api.request('/people', { method: 'POST', body: {} }), error => {
    assert.equal(error.status, 422);
    assert.equal(error.code, 'validation_failed');
    assert.deepEqual(error.fields, { relation: 'max40' });
    assert.equal(error.message, '관계를 확인해 주세요.');
    return true;
  });
});

test('non-JSON server errors do not render HTML, successful malformed responses are rejected', async () => {
  const broken = createApiClient({ enabled: true, baseUrl: '/api', fetchImpl: async () => new Response('<html>internal stack trace</html>', { status: 502 }) });
  await assert.rejects(broken.request('/workspace'), error => error.status === 502 && error.code === 'http_502' && !error.message.includes('stack'));
  const invalid = createApiClient({ enabled: true, baseUrl: '/api', fetchImpl: async () => new Response('<html>login page</html>') });
  await assert.rejects(invalid.request('/workspace'), error => error.code === 'invalid_response');
});

test('network failure is surfaced and mutation is not retried', async () => {
  let calls = 0;
  const api = createApiClient({ enabled: true, baseUrl: '/api', fetchImpl: async () => { calls++; throw new TypeError('offline'); } });
  await assert.rejects(api.request('/records', { method: 'POST', body: {} }), error => error.code === 'network_error');
  assert.equal(calls, 1);
});

const pendingFetch = (_url, { signal }) => new Promise((_, reject) => {
  if (signal.aborted) reject(new DOMException('aborted', 'AbortError'));
  else signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true });
});
test('caller cancellation and timeout are distinct and cleanly cancel the request', async () => {
  const controller = new AbortController();
  const api = createApiClient({ enabled: true, baseUrl: '/api', fetchImpl: pendingFetch });
  const request = api.request('/workspace', { signal: controller.signal });
  controller.abort();
  await assert.rejects(request, error => error.code === 'aborted');
  const timed = createApiClient({ enabled: true, baseUrl: '/api', fetchImpl: pendingFetch, timeoutMs: 5 });
  await assert.rejects(timed.request('/workspace'), error => error.code === 'timeout');
  const cancelled = new AbortController(); cancelled.abort();
  await assert.rejects(api.request('/workspace', { signal: cancelled.signal }), error => error.code === 'aborted');
});

test('import commits pass an explicit idempotency key and preview ID, not client-trusted parsed rows', async () => {
  const calls = [];
  const api = createBackendServices({ enabled: true, baseUrl: '/api', fetchImpl: async (url, options) => {
    calls.push({ url, options }); return new Response('{"records":[],"people":[]}');
  } });
  await api.records.commitImport('preview-1', { idempotencyKey: 'attempt-1' });
  assert.equal(calls[0].url, '/api/records/import/commit');
  assert.deepEqual(JSON.parse(calls[0].options.body), { previewId: 'preview-1' });
  assert.equal(calls[0].options.headers['Idempotency-Key'], 'attempt-1');
});

test('enabled client rejects credentials, insecure remote origins and missing base URL', () => {
  for (const baseUrl of ['', 'http://example.test/api', 'https://user:pass@example.test/api', '//example.test/api', 'https://example.test/api?secret=x']) {
    assert.throws(() => createApiClient({ enabled: true, baseUrl }), error => error.code === 'invalid_config');
  }
  assert.doesNotThrow(() => createApiClient({ enabled: true, baseUrl: 'http://localhost:3000/api' }));
});
