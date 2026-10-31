export const WORK_TYPES = ['일반 회사원', '공무원', '공공기관 직원', '교직원', '언론인', '자영업·프리랜서', '학생', '기타'];
export const VISIBILITY_OPTIONS = ['전체 공개', '친구에게만 공개', '비공개'];
export const normalizeUsername = value => String(value || '').trim().toLowerCase();
export const normalizePhone = value => String(value || '').trim().replace(/[\s()\-]/g, '');
export const normalizeEmail = value => String(value || '').trim().toLowerCase();
export function findAccount(accounts, username) {
  const key = normalizeUsername(username);
  if (!key) return undefined;
  return accounts.find(account => normalizeUsername(account.username) === key);
}
function contactAndWorkError(form) {
  if (!/^\+?\d{9,15}$/.test(normalizePhone(form.phone))) return '전화번호를 확인해 주세요. 예: 010-1234-5678';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(form.email))) return '이메일 주소를 확인해 주세요.';
  if (String(form.workplace || '').length > 60 || String(form.organization || '').length > 60) return '직장과 소속기관은 60자 이내로 입력해 주세요.';
  if (!WORK_TYPES.includes(form.workType)) return '직무형태를 선택해 주세요.';
  if (!VISIBILITY_OPTIONS.includes(form.visibility)) return '정보공개여부를 선택해 주세요.';
  return '';
}
export function signupError(form, accounts = []) {
  const username = normalizeUsername(form.username);
  if (!/^[a-z0-9_]{4,20}$/.test(username)) return '아이디는 영문·숫자·밑줄로 4~20자 입력해 주세요.';
  if (!String(form.name || '').trim()) return '이름을 입력해 주세요.';
  if (String(form.password || '').length < 8) return '비밀번호는 8자 이상으로 입력해 주세요.';
  if (form.password !== form.confirmation) return '두 비밀번호가 일치하지 않아요.';
  const error = contactAndWorkError(form);
  if (error) return error;
  const email = normalizeEmail(form.email);
  if (accounts.some(account => normalizeUsername(account.username) === username)) return '이 브라우저에 이미 등록된 아이디예요.';
  if (accounts.some(account => normalizeEmail(account.email) === email)) return '이 브라우저에 이미 등록된 이메일이에요.';
  return '';
}
// 정보 수정: 비밀번호는 바꿀 때만 입력 (현재 비밀번호 확인 필요)
export function profileUpdateError(form, accounts = [], username = '') {
  if (form.password || form.confirmation) {
    if (!form.currentPassword) return '비밀번호를 바꾸려면 현재 비밀번호를 입력해 주세요.';
    if (String(form.password || '').length < 8) return '새 비밀번호는 8자 이상으로 입력해 주세요.';
    if (form.password !== form.confirmation) return '두 비밀번호가 일치하지 않아요.';
  }
  const error = contactAndWorkError(form);
  if (error) return error;
  const email = normalizeEmail(form.email);
  const self = normalizeUsername(username);
  if (accounts.some(account => normalizeUsername(account.username) !== self && normalizeEmail(account.email) === email)) return '다른 계정에서 사용 중인 이메일이에요.';
  return '';
}
export function publicProfile(account) {
  return {
    username: account.username || '', name: account.name, phone: account.phone || '', email: account.email,
    workplace: account.workplace || '', organization: account.organization || '',
    workType: account.workType || '', visibility: account.visibility || '',
  };
}
