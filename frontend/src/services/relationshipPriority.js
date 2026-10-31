// 사용자가 직접 기록한 관계 중요도로 '이미 볼 수 있는' 받은 일정의 순서를 정한다.
// 서버(gyeongjosa_ai/relationship_priority.py)와 같은 기준을 쓴다. 공유 범위는 바꾸지 않는다.
export const PRIORITY_WEIGHTS = Object.freeze({ '매우 중요': 30, '중요': 15, special: 20, within7: 10 });
export const PRIORITY_RELATIONS = ['가족', '친척', '친구', '직장동료', '거래처', '기타'];

const normalize = value => {
  const text = String(value || '').replace(/\s/g, '');
  return text === '매우중요' ? '매우 중요' : text === '중요' ? '중요' : '보통';
};

export function daysBetween(date, today) {
  if (!date || !today) return null;
  const a = Date.UTC(...String(date).split('-').map((v, i) => i === 1 ? Number(v) - 1 : Number(v)));
  const b = Date.UTC(...String(today).split('-').map((v, i) => i === 1 ? Number(v) - 1 : Number(v)));
  return Number.isFinite(a) && Number.isFinite(b) ? Math.round((a - b) / 86400000) : null;
}

export const dayReason = days => days === 0 ? '오늘' : `${days}일 남음`;
const isDayReason = text => /^(오늘|\d+일 남음)$/.test(text);

/** 중요도 · 특별 표시 · 남은 날짜로 점수와 추천 이유를 만든다. */
export function priorityFor(priority, days) {
  let score = 0;
  const reasons = [];
  if (priority) {
    const relation = String(priority.relation || '').trim();
    const importance = normalize(priority.importance);
    if (importance !== '보통') { score += PRIORITY_WEIGHTS[importance]; reasons.push(`‘${importance}’로 기록한 ${relation || '사람'}`); }
    else if (relation) reasons.push(relation);
    if (priority.special === true) { score += PRIORITY_WEIGHTS.special; reasons.push('특별히 챙길 사람'); }
  }
  if (days !== null && days !== undefined && days >= 0 && days <= 7) { score += PRIORITY_WEIGHTS.within7; reasons.push(dayReason(days)); }
  return { score, reasons };
}

/** 서버가 계산한 점수에서 날짜 부분만 오늘 기준으로 다시 계산한다. (서버는 고정 시연일을 쓴다) */
export function priorityFromServer(entry, days) {
  const reasons = (entry.priority_reasons || []).filter(text => !isDayReason(text));
  const hadDay = (entry.priority_reasons || []).some(isDayReason);
  let score = Number(entry.priority_score || 0) - (hadDay ? PRIORITY_WEIGHTS.within7 : 0);
  if (days !== null && days !== undefined && days >= 0 && days <= 7) { score += PRIORITY_WEIGHTS.within7; reasons.push(dayReason(days)); }
  return { score: Math.max(0, score), reasons };
}
