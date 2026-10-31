// 회원가입·로그인은 서버 SQLite가 원천이다. 브라우저에는 세션 토큰만 보관한다.
import { demoApi } from './demoApi.js';

export const AUTH_TOKEN_KEY = 'maeum-auth-token-v1';
const ACCOUNTS_KEY = 'maeum-demo-accounts-v1';
const MEMBER_FIELDS = ['username', 'name', 'workplace', 'organization', 'workType', 'visibility'];

export function getAuthToken(storage = globalThis.localStorage) {
  try { return storage?.getItem(AUTH_TOKEN_KEY) || ''; } catch { return ''; }
}

function setAuthToken(token, storage = globalThis.localStorage) {
  try { if (token) storage.setItem(AUTH_TOKEN_KEY, token); else storage.removeItem(AUTH_TOKEN_KEY); } catch { /* 저장 공간이 없으면 이번 화면에서만 로그인 */ }
}

/** 로그인한 회원의 서버 인맥·일정·장부 소유자 ID (서버 account_store.workspace_owner와 같다) */
export const memberWorkspace = username => 'ACC:' + String(username || '').trim().toLowerCase();

/**
 * 같은 브라우저의 친구 찾기 목록에 공개 정보만 남긴다. 비밀번호·연락처는 저장하지 않는다.
 * (친구·공유 일정은 아직 브라우저 저장소를 쓴다)
 */
export function rememberMember(profile, storage = globalThis.localStorage) {
  try {
    const raw = JSON.parse(storage.getItem(ACCOUNTS_KEY) || '[]');
    const members = Array.isArray(raw) ? raw : [];
    const entry = Object.fromEntries(MEMBER_FIELDS.map(field => [field, profile[field] || '']));
    const rest = members.filter(item => String(item?.username || '').toLowerCase() !== entry.username);
    storage.setItem(ACCOUNTS_KEY, JSON.stringify([...rest, entry]));
  } catch { /* 친구 찾기 목록만 갱신하지 못한다 */ }
}

async function startSession(path, body) {
  const result = await demoApi(path, { method: 'POST', body });
  setAuthToken(result.token);
  rememberMember(result.profile);
  return result.profile;
}

export const signupAccount = form => startSession('/auth/signup', {
  username: form.username, name: form.name, password: form.password, phone: form.phone, email: form.email,
  workplace: form.workplace, organization: form.organization, workType: form.workType, visibility: form.visibility,
});

export const loginAccount = form => startSession('/auth/login', { username: form.username, password: form.password });

export async function updateAccount(form) {
  const { profile } = await demoApi('/auth/me', {
    method: 'PUT',
    body: {
      phone: form.phone, email: form.email, workplace: form.workplace, organization: form.organization,
      workType: form.workType, visibility: form.visibility, password: form.password, currentPassword: form.currentPassword,
    },
  });
  rememberMember(profile);
  return profile;
}

/** 저장된 토큰이 아직 유효하면 서버의 최신 프로필을, 아니면 null을 돌려준다. */
export async function fetchMe() {
  if (!getAuthToken()) return null;
  try { return (await demoApi('/auth/me')).profile; }
  catch (error) { if (error.status === 401) { setAuthToken(''); return null; } throw error; }
}

export async function logoutAccount() {
  try { if (getAuthToken()) await demoApi('/auth/logout', { method: 'POST' }); } catch { /* 서버가 꺼져 있어도 브라우저에서는 로그아웃 */ }
  setAuthToken('');
}
