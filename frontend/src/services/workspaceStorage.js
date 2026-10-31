export const STORAGE_KEYS = Object.freeze({
  people: 'maeum-people-v1', events: 'maeum-events-v1', records: 'maeum-records-v1',
  theme: 'maeum-theme-v1', session: 'maeum-session-v1', readIds: 'maeum-read-notices-v1',
  notifications: 'maeum-notifications-v1', sidebarCollapsed: 'maeum-sidebar-collapsed-v1',
});

export function readStored(key, initial, normalize = value => value, storage) {
  try {
    storage ??= globalThis.localStorage;
    const raw = storage.getItem(key);
    const parsed = raw === null ? initial : JSON.parse(raw);
    return normalize(Array.isArray(initial) && !Array.isArray(parsed) ? initial : parsed);
  } catch { return initial; }
}

export function writeStored(key, value, storage) {
  storage ??= globalThis.localStorage;
  const json = JSON.stringify(value);
  if (json === undefined) throw new TypeError('저장할 값이 없어요.');
  storage.setItem(key, json);
}

/** Best-effort local rollback; server imports must use an actual DB transaction. */
export function commitWorkspace(patch, storage, keys = STORAGE_KEYS) {
  storage ??= globalThis.localStorage;
  const entries = ['people', 'events', 'records', 'readIds', 'notifications']
    .filter(field => Object.hasOwn(patch, field))
    .map(field => [keys[field] || STORAGE_KEYS[field], JSON.stringify(patch[field])]);
  if (entries.some(([, json]) => json === undefined)) throw new TypeError('저장할 값이 없어요.');
  // Read every backup before writing anything, including quota/security errors.
  const before = new Map(entries.map(([key]) => [key, storage.getItem(key)]));
  const written = [];
  try {
    for (const [key, json] of entries) { storage.setItem(key, json); written.push(key); }
  } catch (error) {
    for (const key of written.reverse()) {
      try {
        if (before.get(key) === null) storage.removeItem(key);
        else storage.setItem(key, before.get(key));
      } catch (rollbackError) { error.rollbackError = rollbackError; }
    }
    throw error;
  }
}
