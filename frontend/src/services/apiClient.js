export class ApiError extends Error {
  constructor(message, { status = 0, code = 'request_failed', fields = null, cause } = {}) {
    super(message, { cause });
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

function normalizeBaseUrl(value) {
  const base = String(value || '').trim().replace(/\/+$/, '');
  if (/^\/(?!\/)[^?#]*$/.test(base)) return base;
  try {
    const url = new URL(base);
    const localHttp = url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if ((url.protocol !== 'https:' && !localHttp) || url.username || url.password || url.search || url.hash) throw new Error();
    return base;
  } catch {
    throw new ApiError('API 주소는 /api 또는 HTTPS 주소로 설정해 주세요.', { code: 'invalid_config' });
  }
}

/** Explicit construction is required; importing this module never sends a request. */
export function createApiClient({ enabled = false, baseUrl = '', fetchImpl = globalThis.fetch, timeoutMs = 15000, getCsrfToken = () => '' } = {}) {
  // Do not require API configuration while the app is still running locally.
  const base = enabled ? normalizeBaseUrl(baseUrl) : '';
  if (enabled && typeof fetchImpl !== 'function') throw new ApiError('요청 기능을 사용할 수 없어요.', { code: 'invalid_config' });

  async function request(path, { method = 'GET', body, signal, idempotencyKey } = {}) {
    if (!enabled) throw new ApiError('백엔드 연결이 아직 활성화되지 않았어요.', { code: 'backend_disabled' });
    if (!path.startsWith('/') || path.startsWith('//')) throw new ApiError('잘못된 API 경로예요.', { code: 'invalid_path' });
    if (signal?.aborted) throw new ApiError('요청을 취소했어요.', { code: 'aborted' });
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort(signal.reason);
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
    try {
      if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) {
        const token = await getCsrfToken();
        if (token) headers['X-CSRF-Token'] = token;
      }
      const response = await fetchImpl(`${base}${path}`, {
        method, headers, credentials: 'include', signal: controller.signal,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      const raw = response.status === 204 ? '' : await response.text();
      let data = null;
      if (raw.trim()) {
        try { data = JSON.parse(raw); }
        catch {
          if (response.ok) throw new ApiError('서버 응답 형식을 확인해 주세요.', { status: response.status, code: 'invalid_response' });
        }
      }
      if (!response.ok) {
        const error = data?.error;
        throw new ApiError(typeof error?.message === 'string' ? error.message : `요청을 처리하지 못했어요. (${response.status})`, {
          status: response.status, code: error?.code || `http_${response.status}`, fields: error?.fields || null,
        });
      }
      return data;
    } catch (cause) {
      if (cause instanceof ApiError) throw cause;
      if (controller.signal.aborted) throw new ApiError(timedOut ? '서버 응답 시간이 초과됐어요.' : '요청을 취소했어요.', { code: timedOut ? 'timeout' : 'aborted', cause });
      throw new ApiError('서버에 연결하지 못했어요. 네트워크 상태를 확인해 주세요.', { code: 'network_error', cause });
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }
  return { request, enabled: !!enabled };
}
