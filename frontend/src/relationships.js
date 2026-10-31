export const RELATION_OPTIONS = ['가족', '친구', '직장동료', '거래처', '기타'];
export const IMPORTANCE_OPTIONS = ['매우 중요', '중요', '보통'];

export function relationDraft(value) {
  const relation = String(value || '').trim() || '기타';
  return RELATION_OPTIONS.includes(relation)
    ? { relation, customRelation: '' }
    : { relation: '기타', customRelation: relation };
}

export function resolveRelation(choice, custom = '') {
  return choice === '기타' ? String(custom).trim() || '기타' : String(choice || '').trim() || '기타';
}

export function matchesRelation(value, filter) {
  if (filter === '전체') return true;
  const category = relationDraft(value).relation;
  return category === filter;
}

export function normalizeImportance(value) {
  if (String(value || '').replace(/\s/g, '') === '매우중요') return '매우 중요';
  return value === '중요' ? '중요' : '보통';
}

export function importanceRank(value) {
  return { '매우 중요': 2, '중요': 1, '보통': 0 }[normalizeImportance(value)];
}

export function normalizePerson(person) {
  return { ...person, relation:String(person.relation || '').trim() || '기타', importance:normalizeImportance(person.importance) };
}
