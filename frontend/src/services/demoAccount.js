export const DEMO_ACCOUNT_EVENT = 'maeum-demo-account-change';
const KEY = 'rag-demo-user';

export function getDemoAccount(storage = globalThis.sessionStorage) {
  try { return storage?.getItem(KEY) || ''; } catch { return ''; }
}

export function setDemoAccount(userId, { storage = globalThis.sessionStorage, events = globalThis.window } = {}) {
  const previous = getDemoAccount(storage);
  try {
    if (!storage) return false;
    if (userId) storage.setItem(KEY, userId);
    else storage.removeItem(KEY);
  } catch { return false; }
  if (previous !== userId) events?.dispatchEvent(new Event(DEMO_ACCOUNT_EVENT));
  return true;
}
