import { ApiError, createApiClient } from './apiClient.js';

export const AI_MODES = ['금액 참고', '참석 대응', '메시지 작성', '우선순위'];
const providers = ['mock', 'openai'];
const text = (value, max, empty = false) => typeof value === 'string' && value.length <= max && (empty || value.trim().length > 0);
const invalid = () => new ApiError('서버 응답 형식을 확인해 주세요.', { code: 'invalid_response' });

export function aiConfig(env = import.meta.env || {}) {
  const serverAvailable = !!env.DEV || env.VITE_AI_MODE === 'server' || !!env.VITE_AI_API_BASE_URL;
  return {
    serverAvailable,
    defaultSource: env.VITE_AI_MODE === 'local' ? 'local' : env.DEV || env.VITE_AI_MODE === 'server' ? 'server' : 'local',
    baseUrl: env.VITE_AI_API_BASE_URL || '/api',
  };
}

export function validateContext(value) {
  if (!value || !providers.includes(value.provider) || value.dataSource !== 'mock' || !/^\d{4}-\d{2}-\d{2}$/.test(value.today || '') || !Array.isArray(value.people) || value.people.length > 100) throw invalid();
  const ids = new Set();
  const people = value.people.map(person => {
    if (!person || !text(person.id, 128) || ids.has(person.id) || !text(person.name, 40) || !text(person.relation, 40) || !text(person.group, 40, true) || !['매우 중요', '중요', '보통'].includes(person.importance)) throw invalid();
    ids.add(person.id);
    return { id: person.id, name: person.name, relation: person.relation, group: person.group, importance: person.importance };
  });
  return { people, provider: value.provider, dataSource: 'mock', today: value.today };
}

export function validateAdvice(value) {
  if (!value || !text(value.title, 300) || !text(value.text, 12000) || !providers.includes(value.provider) || value.dataSource !== 'mock' || value.demo !== true || typeof value.isMessage !== 'boolean') throw invalid();
  if (!Array.isArray(value.evidence) || value.evidence.length > 30 || !value.evidence.every(item => item && text(item.label, 100) && text(item.value, 2000))) throw invalid();
  if (!Array.isArray(value.suggestions) || value.suggestions.length > 8 || !value.suggestions.every(item => text(item, 1000))) throw invalid();
  if (value.amount !== undefined && value.amount !== null && (!Number.isSafeInteger(value.amount) || value.amount < 1 || value.amount > 1000000000)) throw invalid();
  return { title:value.title, text:value.text, evidence:value.evidence.map(({label,value}) => ({label,value})), suggestions:[...value.suggestions], ...(value.amount ? {amount:value.amount} : {}), isMessage:value.isMessage, provider:value.provider, dataSource:'mock', demo:true };
}

export function createAiChat({ baseUrl = '/api', ...options } = {}) {
  const client = createApiClient({ ...options, enabled:true, baseUrl, timeoutMs:40000 });
  return {
    async context({signal} = {}) { return validateContext(await client.request('/demo/context', {signal})); },
    async advice(values, {signal} = {}) {
      const question = String(values.question || '').trim();
      if (!question || question.length > 1000 || !AI_MODES.includes(values.mode) || !text(values.personId, 128)) throw new ApiError('질문과 참고할 인맥을 확인해 주세요.', {code:'invalid_input'});
      // Only identifiers and the question leave the UI. Browser contacts/ledger are never uploaded.
      const body = {question, mode:values.mode, personId:values.personId};
      if (values.eventId) {
        if (!text(values.eventId, 128)) throw new ApiError('참고할 일정을 확인해 주세요.', {code:'invalid_input'});
        body.eventId = values.eventId;
      }
      return validateAdvice(await client.request('/ai/advice', {method:'POST',body,signal}));
    },
  };
}
