import test from 'node:test'
import assert from 'node:assert/strict'
import { daysUntil, normalizeAttendance, getAdvice, monthSpending, typeSpending, toICS } from './domain.js'
import { displayScheduleTitle, isSyntheticScheduleTitle } from './scheduleTitle.js'

test('date calculations use calendar days without UTC offset drift', () => {
  assert.equal(daysUntil('2026-11-07', '2026-10-30'), 8)
  assert.equal(daysUntil('2026-10-30', '2026-10-30'), 0)
  assert.equal(daysUntil('2026-10-18', '2026-10-30'), -12)
  assert.equal(daysUntil('2026-02-30', '2026-10-30'), null)
})

test('legacy attendance is migrated without inventing a decision', () => {
  assert.equal(normalizeAttendance('참석 예정'), '참석')
  assert.equal(normalizeAttendance('참석'), '참석')
  assert.equal(normalizeAttendance('불참'), '불참')
  assert.equal(normalizeAttendance('미정'), '')
  assert.equal(normalizeAttendance(undefined), '')
})

test('amount advice cites actual incoming records and avoids invented amounts', () => {
  const person = { id: 'p1', name: '김도윤', relation: '친구', group: '대학 동기', importance: '중요' }
  const records = [{ personId: 'p1', direction: '받은 마음', amount: 100000, date: '2025-05-17', type: '장례식' }]
  const reply = getAdvice({ person, records })
  assert.equal(reply.amount, 100000)
  assert.ok(reply.text.includes('100,000원'))
  assert.ok(reply.evidence.some((entry) => entry.value.includes('2025.05.17')))
  assert.equal(getAdvice({ person, records: [] }).amount, undefined)
})

test('explicit question intent overrides the active mode and preserves absence in messages', () => {
  const person = { id: 'p1', name: '김도윤', relation: '친구', group: '대학 동기', importance: '중요' }
  const records = [{ personId: 'p1', direction: '받은 마음', amount: 100000, date: '2025-05-17', type: '장례식' }]
  const events = [{ id: 'e1', personId: 'p1', title: '김도윤의 결혼식', type: '결혼식', date: '2026-11-07', attendance: '참석' }]
  const context = { person, people: [person], records, events, today: '2026-10-30' }
  const amountReply = getAdvice({ ...context, mode: '메시지 작성', question: '금액도 참고하고 싶어요' })
  assert.equal(amountReply.amount, 100000)
  assert.equal(amountReply.isMessage, undefined)
  const attendanceReply = getAdvice({ ...context, mode: '금액 참고', question: '참석하지 못한다면?' })
  assert.ok(attendanceReply.title.includes('함께하지 못해도'))
  assert.equal(attendanceReply.amount, undefined)
  const messageReply = getAdvice({ ...context, mode: '금액 참고', question: '불참할 때 보낼 메시지' })
  assert.equal(messageReply.isMessage, true)
  assert.ok(messageReply.text.includes('직접 함께하지 못해'))
  const genericMessage = getAdvice({ ...context, mode: '금액 참고', question: '축하·위로 메시지 작성' })
  assert.ok(genericMessage.text.includes('결혼을 진심으로 축하'))
  assert.ok(!genericMessage.text.includes('애도'))
  const unableReply = getAdvice({ ...context, mode: '금액 참고', question: '참석할 수 없어요' })
  assert.ok(unableReply.title.includes('함께하지 못해도'))
  const funeralMessage = getAdvice({ ...context, events: [{ ...events[0], type: '장례식' }], mode: '우선순위', question: '불참할 때 보낼 위로 메시지' })
  assert.equal(funeralMessage.isMessage, true)
  assert.ok(funeralMessage.text.includes('찾아뵙지 못해'))
})

test('questions without explicit intent use the active mode', () => {
  const context = { person: { id: 'p1', name: '김도윤', relation: '친구', group: '대학 동기', importance: '중요' } }
  assert.equal(getAdvice({ ...context, mode: '메시지 작성', question: '도와주세요' }).isMessage, true)
  assert.ok(getAdvice({ ...context, mode: '참석 대응', question: '도와주세요' }).title.includes('참석 전'))
  assert.ok(getAdvice({ ...context, mode: '우선순위', question: '도와주세요' }).title.includes('예정된 경조사'))
})

test('spending aggregates only outgoing records for selected year', () => {
  const records = [
    { direction: '보낸 마음', date: '2026-10-03', amount: 100000, type: '결혼식' },
    { direction: '받은 마음', date: '2026-10-05', amount: 500000, type: '결혼식' },
    { direction: '보낸 마음', date: '2025-10-03', amount: 300000, type: '결혼식' },
    { direction: '보낸 마음', date: '2026-10-18', amount: 100000, type: '장례식' },
  ]
  assert.equal(monthSpending(records, 2026)[9].amount, 200000)
  assert.equal(monthSpending(records, 2026).length, 12)
  assert.equal(typeSpending(records, 2026).reduce((sum, entry) => sum + entry.amount, 0), 200000)
})

test('ICS export includes Korea timezone, alarms, and escaped user text', () => {
  const ics = toICS({ id: 'test', title: '김도윤, 결혼식', date: '2026-11-07', time: '14:00', location: '3층; 그레이스홀', memo: '첫 줄\n다음 줄', reminderDays: 3 })
  assert.ok(ics.includes('DTSTART;TZID=Asia/Seoul:20261107T140000'))
  assert.ok(ics.includes('TRIGGER:-P3D'))
  assert.ok(ics.includes('SUMMARY:김도윤\\, 결혼식'))
  assert.ok(ics.includes('LOCATION:3층\\; 그레이스홀'))
  assert.ok(ics.includes('DESCRIPTION:첫 줄\\n다음 줄'))
  assert.throws(() => toICS({ date: '2026-02-30' }))
})

test('priority ranks very-important relations first on the same day while keeping funeral and date precedence', () => {
  const people = ['보통', '중요', '매우중요'].map((importance, index) => ({ id:`p${index}`, name:`인맥${index}`, relation:'동호회 선배', importance }))
  const events = people.map(person => ({ id:`e${person.id}`, personId:person.id, title:`${person.name} 결혼식`, type:'결혼식', date:'2026-11-01' }))
  const context = { person:people[0], people, events, today:'2026-10-31', mode:'우선순위' }
  assert.ok(getAdvice(context).text.startsWith('인맥2 결혼식'))
  assert.equal(getAdvice(context).evidence.find(item => item.label === '관계 중요도').value, '매우 중요')
  assert.ok(getAdvice({...context, events:[...events, {...events[0], id:'earlier', title:'가까운 날', date:'2026-10-31'}]}).text.startsWith('가까운 날'))
  assert.ok(getAdvice({...context, events:[...events, {...events[0], id:'funeral', title:'조문 일정', type:'장례식', date:'2026-11-02'}]}).text.startsWith('조문 일정'))
})

test('합성 시연과 합성 예정 접두어를 화면용 제목에서 제거한다', () => {
  assert.equal(displayScheduleTitle('[합성 시연] 김민수 결혼식'), '김민수 결혼식')
  assert.equal(displayScheduleTitle('[합성 예정] 이지은 돌잔치'), '이지은 돌잔치')
  assert.equal(displayScheduleTitle('[합성 시연]김민수 결혼식'), '김민수 결혼식')
})

test('일반 제목과 내부 문구를 변경하지 않는다', () => {
  assert.equal(displayScheduleTitle('김민수 결혼식'), '김민수 결혼식')
  assert.equal(displayScheduleTitle('김민수 [합성 시연] 결혼식'), '김민수 [합성 시연] 결혼식')
  assert.equal(displayScheduleTitle('[합성 기록] 김민수'), '[합성 기록] 김민수')
  assert.equal(displayScheduleTitle(''), '')
  assert.equal(displayScheduleTitle(null), null)
})

test('화면의 합성 데이터 안내는 해당 접두어가 있는 경우에만 필요하다', () => {
  assert.equal(isSyntheticScheduleTitle('[합성 시연] 김민수 결혼식'), true)
  assert.equal(isSyntheticScheduleTitle('[합성 예정] 이지은 돌잔치'), true)
  assert.equal(isSyntheticScheduleTitle('김민수 결혼식'), false)
  assert.equal(isSyntheticScheduleTitle(undefined), false)
})
