// 기존 통합 화면의 API 호출 계약을 유지한다. 로그인 토큰이 있으면 함께 보낸다.
const AUTH_TOKEN_KEY = 'maeum-auth-token-v1';

function authHeader() {
  try {
    const token = globalThis.localStorage?.getItem(AUTH_TOKEN_KEY);
    return token ? { Authorization: 'Bearer ' + token } : {};
  } catch { return {}; }
}

export async function demoApi(path, { userId, method = 'GET', body, signal } = {}) {
  const response = await fetch('/api' + path, {
    method, signal,
    headers: { ...authHeader(), ...(userId ? { 'X-Demo-User-Id': userId } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (response.status === 204) return {};
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(typeof result.detail === 'string' ? result.detail : '서버 요청에 실패했습니다.');
    error.status = response.status;
    throw error;
  }
  return result;
}
