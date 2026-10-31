export const normalizeUsername = value => String(value || '').trim().toLowerCase();
export const normalizePhone = value => String(value || '').trim().replace(/[\s()\-]/g, '');
export function findAccount(accounts, identity) {
  const key = normalizeUsername(identity);
  if (!key) return undefined;
  return accounts.find(account => normalizeUsername(account.username) === key || String(account.email || '').toLowerCase() === key);
}
export function signupError(form, accounts = []) {
  const username = normalizeUsername(form.username);
  if (!/^[a-z0-9_]{4,20}$/.test(username)) return '아이디는 영문·숫자·밑줄로 4~20자 입력해 주세요.';
  if (String(form.password || '').length < 8) return '비밀번호는 8자 이상으로 입력해 주세요.';
  if (form.password !== form.confirmation) return '두 비밀번호가 일치하지 않아요.';
  if (!String(form.name || '').trim()) return '이름을 입력해 주세요.';
  if (!/^\+?\d{9,15}$/.test(normalizePhone(form.phone))) return '전화번호를 확인해 주세요. 예: 010-1234-5678';
  const email = String(form.email || '').trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return '이메일 주소를 확인해 주세요.';
  if (accounts.some(account => normalizeUsername(account.username) === username)) return '이 브라우저에 이미 등록된 아이디예요.';
  if (accounts.some(account => String(account.email || '').toLowerCase() === email)) return '이 브라우저에 이미 등록된 이메일이에요.';
  return '';
}
