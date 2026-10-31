// 기존 통합 화면의 API 호출 계약을 유지한다. 로그인 세션은 HttpOnly 쿠키로만 주고받는다.
export async function demoApi(path, { userId, method = 'GET', body, signal } = {}) {
  const response = await fetch('/api' + path, {
    method, signal, credentials: 'same-origin',
    headers: { ...(userId ? { 'X-Demo-User-Id': userId } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
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
