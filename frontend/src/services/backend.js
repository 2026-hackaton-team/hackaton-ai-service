import { createApiClient } from './apiClient.js';

const id = value => encodeURIComponent(String(value));
const query = filters => {
  const params = new URLSearchParams(Object.entries(filters || {}).filter(([, value]) => value !== undefined && value !== null && value !== ''));
  return params.size ? `?${params}` : '';
};

/** Proposed API contract. Not used by the local UI until its lifecycle is wired. */
export function createBackendServices(options = {}) {
  const client = createApiClient(options);
  const get = (path, options) => client.request(path, options);
  const send = (method, path, body, options) => client.request(path, { ...options, method, body });
  return {
    enabled: client.enabled,
    auth: {
      session: options => get('/auth/session', options),
      signup: (values, options) => send('POST', '/auth/signup', values, options),
      login: (values, options) => send('POST', '/auth/login', values, options),
      logout: options => send('POST', '/auth/logout', undefined, options),
    },
    workspace: {
      load: options => get('/workspace', options),
      previewMigration: (snapshot, options) => send('POST', '/workspace/migrations/preview', snapshot, options),
      commitMigration: (previewId, options) => send('POST', '/workspace/migrations/commit', { previewId }, options),
    },
    people: {
      list: (filters, options) => get(`/people${query(filters)}`, options),
      create: (values, options) => send('POST', '/people', values, options),
      update: (personId, patch, options) => send('PATCH', `/people/${id(personId)}`, patch, options),
      addInteraction: (personId, values, options) => send('POST', `/people/${id(personId)}/interactions`, values, options),
    },
    events: {
      list: (filters, options) => get(`/events${query(filters)}`, options),
      create: (values, options) => send('POST', '/events', values, options),
      update: (eventId, patch, options) => send('PATCH', `/events/${id(eventId)}`, patch, options),
      remove: (eventId, options) => send('DELETE', `/events/${id(eventId)}`, undefined, options),
    },
    records: {
      list: (filters, options) => get(`/records${query(filters)}`, options),
      create: (values, options) => send('POST', '/records', values, options),
      update: (recordId, patch, options) => send('PATCH', `/records/${id(recordId)}`, patch, options),
      remove: (recordId, options) => send('DELETE', `/records/${id(recordId)}`, undefined, options),
      previewImport: (csv, options) => send('POST', '/records/import/preview', { csv }, options),
      commitImport: (previewId, options) => send('POST', '/records/import/commit', { previewId }, options),
    },
    notifications: {
      list: (filters, options) => get(`/notifications${query(filters)}`, options),
      markRead: (noticeId, options) => send('PATCH', `/notifications/${id(noticeId)}`, { read: true }, options),
      markAllRead: options => send('POST', '/notifications/read-all', undefined, options),
      preferences: options => get('/notification-preferences', options),
      updatePreferences: (patch, options) => send('PATCH', '/notification-preferences', patch, options),
      subscribePush: (subscription, options) => send('POST', '/push-subscriptions', subscription, options),
      unsubscribePush: (subscriptionId, options) => send('DELETE', `/push-subscriptions/${id(subscriptionId)}`, undefined, options),
    },
    ai: { advice: (values, options) => send('POST', '/ai/advice', values, options) },
  };
}

export function backendOptionsFromEnv(env = import.meta.env || {}) {
  return { enabled: env.VITE_API_ENABLED === 'true', baseUrl: env.VITE_API_BASE_URL || '' };
}
