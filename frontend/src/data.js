export const initialPeople = [
  { id: 'p1', name: '김도윤', relation: '친구', group: '대학 동기', importance: '중요', lastMet: '2026-09-12', memo: '오래 알고 지낸 대학 동기. 결혼 준비 중이에요.', interactions: [{ id: 'i1', date: '2026-09-12', type: '만남', memo: '청첩장을 받으며 함께 저녁 식사' }, { id: 'i2', date: '2026-08-04', type: '연락', memo: '결혼 준비 안부를 나눔' }] },
  { id: 'p2', name: '윤서진', relation: '가족', group: '친척', importance: '중요', lastMet: '2026-09-27', memo: '조카의 첫 생일을 함께 축하해 주세요.', interactions: [{ id: 'i3', date: '2026-09-27', type: '만남', memo: '추석 가족 모임' }] },
  { id: 'p3', name: '이수현', relation: '거래처', group: '협력사', importance: '중요', lastMet: '2026-09-25', memo: '함께 프로젝트를 진행한 협력사 담당자', interactions: [{ id: 'i4', date: '2026-09-25', type: '만남', memo: '프로젝트 마무리 미팅' }] },
  { id: 'p4', name: '박서연', relation: '직장동료', group: '회사', importance: '중요', lastMet: '2026-10-18', memo: '같은 팀 동료. 최근 부친상을 치렀어요.', interactions: [{ id: 'i5', date: '2026-10-18', type: '만남', memo: '부친상 조문' }] },
  { id: 'p5', name: '정하늘', relation: '친구', group: '동네 친구', importance: '보통', lastMet: '2026-10-24', memo: '가끔 동네에서 만나 산책하는 친구', interactions: [{ id: 'i6', date: '2026-10-24', type: '만남', memo: '결혼식 참석, 오랜 친구들과 재회' }] },
  { id: 'p6', name: '최유진', relation: '가족', group: '친척', importance: '보통', lastMet: '2026-10-03', memo: '가까운 사촌. 결혼식에 다녀왔어요.', interactions: [{ id: 'i7', date: '2026-10-03', type: '만남', memo: '결혼식 참석' }] },
  { id: 'p7', name: '한지우', relation: '직장동료', group: '이전 직장', importance: '보통', lastMet: '2026-06-15', memo: '함께 일했던 동료. 한동안 안부를 전하지 못했어요.', interactions: [{ id: 'i8', date: '2026-06-15', type: '만남', memo: '이전 직장 동료들과 저녁 모임' }] },
  { id: 'p8', name: '오민준', relation: '친구', group: '대학 동기', importance: '보통', lastMet: '2026-07-04', memo: '아이의 첫 생일을 함께 축하했어요.', interactions: [{ id: 'i9', date: '2026-07-04', type: '만남', memo: '돌잔치 참석' }] },
]

export const initialEvents = [
  { id: 'e1', personId: 'p1', title: '김도윤의 결혼식', type: '결혼식', date: '2026-11-07', time: '14:00', location: '그랜드 웨딩홀 · 3층 그레이스홀', attendance: '참석', reminderDays: 3, memo: '대학 동기들과 함께 참석해요.' },
  { id: 'e2', personId: 'p2', title: '윤서진의 돌잔치', type: '돌잔치', date: '2026-11-14', time: '12:00', location: '온유 레스토랑 · 프라이빗룸', attendance: '', reminderDays: 7, memo: '조카의 첫 번째 생일' },
  { id: 'e3', personId: 'p3', title: '이수현의 결혼식', type: '결혼식', date: '2026-11-21', time: '13:00', location: '라온 웨딩홀 · 2층', attendance: '불참', reminderDays: 3, memo: '일정이 겹쳐 축하 메시지와 마음을 전할 예정' },
  { id: 'e4', personId: 'p4', title: '박서연 부친상', type: '장례식', date: '2026-10-18', time: '18:00', location: '서울 추모장례식장 · 5호실', attendance: '참석', reminderDays: 0, memo: '조문을 다녀왔어요.' },
  { id: 'e5', personId: 'p5', title: '정하늘의 결혼식', type: '결혼식', date: '2026-10-24', time: '12:30', location: '보타닉 웨딩 · 가든홀', attendance: '참석', reminderDays: 3, memo: '' },
  { id: 'e6', personId: 'p6', title: '최유진의 결혼식', type: '결혼식', date: '2026-10-03', time: '11:00', location: '더 채플 · 4층', attendance: '참석', reminderDays: 7, memo: '' },
  { id: 'e7', personId: 'p7', title: '한지우의 생일', type: '생일', date: '2026-11-04', time: '09:00', location: '', attendance: '', reminderDays: 1, memo: '오랜만에 안부를 전해 보세요.' },
]

export const initialRecords = [
  { id: 'r1', personId: 'p1', type: '장례식', date: '2025-05-17', direction: '받은 마음', amount: 100000, memo: '가족 장례 때 도윤이가 전해 준 마음' },
  { id: 'r2', personId: 'p5', eventId: 'e5', type: '결혼식', date: '2026-10-24', direction: '보낸 마음', amount: 150000, memo: '결혼 축하, 식사 참석' },
  { id: 'r3', personId: 'p4', eventId: 'e4', type: '장례식', date: '2026-10-18', direction: '보낸 마음', amount: 100000, memo: '부친상 조의금' },
  { id: 'r4', personId: 'p6', eventId: 'e6', type: '결혼식', date: '2026-10-03', direction: '보낸 마음', amount: 100000, memo: '사촌 결혼 축의금' },
  { id: 'r5', personId: 'p2', type: '생일', date: '2026-10-11', direction: '받은 마음', amount: 100000, memo: '생일 축하 선물' },
  { id: 'r6', personId: 'p5', type: '생일', date: '2026-10-11', direction: '받은 마음', amount: 100000, memo: '생일을 챙겨준 마음' },
  { id: 'r7', personId: 'p3', type: '결혼식', date: '2026-01-17', direction: '보낸 마음', amount: 100000, memo: '협력사 경조사' },
  { id: 'r8', personId: 'p2', type: '장례식', date: '2026-02-08', direction: '보낸 마음', amount: 150000, memo: '친척 조의금' },
  { id: 'r9', personId: 'p7', type: '결혼식', date: '2026-03-21', direction: '보낸 마음', amount: 200000, memo: '동료 결혼 축하' },
  { id: 'r10', personId: 'p6', type: '결혼식', date: '2026-04-11', direction: '보낸 마음', amount: 250000, memo: '친척 결혼 축하' },
  { id: 'r11', personId: 'p1', type: '결혼식', date: '2026-05-09', direction: '보낸 마음', amount: 300000, memo: '동기 모임 공동 경조사 기록' },
  { id: 'r12', personId: 'p4', type: '장례식', date: '2026-05-23', direction: '보낸 마음', amount: 100000, memo: '동료 가족 조문' },
  { id: 'r13', personId: 'p8', type: '돌잔치', date: '2026-06-06', direction: '보낸 마음', amount: 200000, memo: '첫 생일 축하' },
  { id: 'r14', personId: 'p8', type: '돌잔치', date: '2026-07-04', direction: '보낸 마음', amount: 150000, memo: '돌잔치 축하' },
  { id: 'r15', personId: 'p7', type: '결혼식', date: '2026-08-22', direction: '보낸 마음', amount: 250000, memo: '이전 직장 동료 경조사' },
  { id: 'r16', personId: 'p2', type: '결혼식', date: '2026-09-05', direction: '보낸 마음', amount: 200000, memo: '친척 결혼 축하' },
  { id: 'r17', personId: 'p6', type: '장례식', date: '2026-09-19', direction: '보낸 마음', amount: 150000, memo: '친척 조의금' },
  { id: 'r18', personId: 'p7', type: '생일', date: '2026-06-15', direction: '받은 마음', amount: 50000, memo: '모임에서 받은 감사의 마음' },
]

export const relationOptions = ['가족', '친구', '직장동료', '거래처', '기타']
export const eventTypes = ['결혼식', '장례식', '돌잔치', '생일', '기타']
