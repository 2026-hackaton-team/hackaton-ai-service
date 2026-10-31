// 경조사 유형별 색상 체계 — occasion-theme.css 의 --oc-* 토큰과 짝을 이룹니다.
const KEY = { 결혼식: 'wedding', 장례식: 'funeral', 돌잔치: 'baby', 생일: 'birthday' };

export const occasionKey = (type) => KEY[type] || 'other';
export const occasionClass = (type) => `oc oc-${occasionKey(type)}`;
export const occasionColor = (type) => `var(--oc-${occasionKey(type)})`;
export const isSorrow = (type) => type === '장례식';
export const attendanceClass = (value) => value === '참석' ? 'att-yes' : value === '불참' ? 'att-no' : 'att-none';
