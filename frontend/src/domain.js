import { normalizeImportance, importanceRank } from './relationships.js'

const localDate = (value) => {
  if (value instanceof Date) return new Date(value.getFullYear(), value.getMonth(), value.getDate())
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return null
  const date = new Date(+match[1], +match[2] - 1, +match[3])
  return date.getFullYear() === +match[1] && date.getMonth() === +match[2] - 1 && date.getDate() === +match[3] ? date : null
}

export function formatMoney(amount) {
  return `${Number(amount || 0).toLocaleString('ko-KR')}원`
}

export function daysUntil(date, today = new Date()) {
  const end = localDate(date)
  const start = localDate(today)
  if (!end || !start) return null
  return Math.round((Date.UTC(end.getFullYear(), end.getMonth(), end.getDate()) - Date.UTC(start.getFullYear(), start.getMonth(), start.getDate())) / 86400000)
}

export function normalizeAttendance(value) {
  if (value === '참석' || value === '참석 예정') return '참석'
  return value === '불참' ? '불참' : ''
}

export function monthSpending(records = [], year = new Date().getFullYear()) {
  return Array.from({ length: 12 }, (_, index) => ({
    month: index + 1,
    label: `${index + 1}월`,
    amount: records.filter((record) => record.direction === '보낸 마음' && record.date?.startsWith(`${year}-${String(index + 1).padStart(2, '0')}`)).reduce((sum, record) => sum + Number(record.amount || 0), 0),
  }))
}

export function typeSpending(records = [], year = new Date().getFullYear()) {
  const groups = new Map()
  records.filter((record) => record.direction === '보낸 마음' && record.date?.startsWith(`${year}-`)).forEach((record) => {
    const entry = groups.get(record.type) || { type: record.type || '기타', amount: 0, count: 0 }
    entry.amount += Number(record.amount || 0)
    entry.count += 1
    groups.set(record.type, entry)
  })
  return [...groups.values()].sort((a, b) => b.amount - a.amount)
}

export function getAdvice({ question = '', mode = '금액 참고', person, people = [], events = [], records = [], today = new Date() } = {}) {
  const messageRequest = /메시지|문구|문자|답장|써\s*줘|작성해|축하해\s*줘|위로해\s*줘/.test(question)
  const attendanceRequest = /불참|못\s*가|못\s*갈|못\s*오|참석|참여|가야/.test(question)
  const amountRequest = /금액|얼마|축의금|조의금|부의금|예산/.test(question)
  const priorityRequest = /우선|놓치|먼저/.test(question)
  const intent = messageRequest ? 'message' : attendanceRequest ? 'attendance' : amountRequest ? 'amount' : priorityRequest ? 'priority'
    : /메시지|축하|문구|위로/.test(mode) ? 'message' : /참석|대응|불참/.test(mode) ? 'attendance' : /우선|놓치/.test(mode) ? 'priority' : 'amount'
  const target = people.find((candidate) => question.includes(candidate.name)) || person || people[0]
  if (!target) return { title: '먼저 인연을 등록해 주세요', text: '등록한 관계와 주고받은 기록이 있으면 상황에 맞는 참고 제안을 확인할 수 있어요.', evidence: [], suggestions: ['인맥을 먼저 등록하기'] }
  const personRecords = records.filter((record) => record.personId === target.id).sort((a, b) => b.date.localeCompare(a.date))
  const incoming = personRecords.find((record) => record.direction === '받은 마음')
  const outgoing = personRecords.find((record) => record.direction === '보낸 마음')
  const upcoming = events.filter((event) => event.personId === target.id && daysUntil(event.date, today) >= 0).sort((a, b) => a.date.localeCompare(b.date))
  const event = upcoming[0] || events.filter((item) => item.personId === target.id).sort((a, b) => b.date.localeCompare(a.date))[0]
  const evidence = [{ label: '관계', value: `${target.relation} · ${target.group || '그룹 없음'} · ${normalizeImportance(target.importance)}` }]
  if (incoming) evidence.push({ label: '최근 받은 마음', value: `${incoming.date.replaceAll('-', '.')} · ${incoming.type} · ${formatMoney(incoming.amount)}` })
  if (outgoing) evidence.push({ label: '최근 보낸 마음', value: `${outgoing.date.replaceAll('-', '.')} · ${outgoing.type} · ${formatMoney(outgoing.amount)}` })
  if (target.lastMet) evidence.push({ label: '최근 만남', value: target.lastMet.replaceAll('-', '.') })
  if (event) evidence.push({ label: '참고한 일정', value: `${event.date.replaceAll('-', '.')} · ${event.title} · ${event.attendance || '참석 여부 선택'}` })

  const isFuneral = event?.type === '장례식' || /부고|조문|조의|애도|추모/.test(question) || (/위로/.test(question) && !/축하/.test(question))
  const explicitCannotAttend = /불참|못\s*가|못\s*갈|못\s*오|참석.{0,8}(?:못|어려|없)/.test(question)
  const explicitCanAttend = !explicitCannotAttend && /참석할|참석해|참석.{0,4}가능|갈\s*수|갈게/.test(question)
  const cannotAttend = explicitCannotAttend || (!explicitCanAttend && event?.attendance === '불참')
  if (intent === 'message') {
    let text
    if (isFuneral) text = `${target.name}님, 갑작스러운 소식에 마음이 무겁습니다. 어떤 말로도 위로가 되기 어렵겠지만, 깊은 애도의 마음을 전합니다. 어려운 시간 잘 추스르시길 바라며, 필요한 일이 있다면 언제든 말씀해 주세요.`
    else if (event?.type === '돌잔치') text = `${target.name}님, 아이의 첫 번째 생일을 진심으로 축하해요. 웃음 가득한 날들이 차곡차곡 쌓이길, 온 가족의 건강과 행복을 함께 응원합니다.`
    else if (event?.type === '생일') text = `${target.name}님, 생일을 진심으로 축하해요. 새로운 한 해도 건강하고 행복한 순간들로 가득하길 바랍니다. 조만간 반가운 얼굴로 만나요!`
    else text = `${target.name}님, 결혼을 진심으로 축하해요. 서로의 가장 든든한 편이 되어, 평범한 날에도 웃음과 다정함이 가득한 두 분의 날들을 응원할게요.`
    if (cannotAttend) text += isFuneral
      ? ' 직접 찾아뵙지 못해 죄송한 마음입니다. 멀리서나마 함께 애도하며, 마음으로 곁에 있겠습니다.'
      : ' 소중한 날에 직접 함께하지 못해 아쉬운 마음이에요. 멀리서나마 진심을 담아 축하하고, 조만간 따로 만나 인사드릴게요.'
    return { title: cannotAttend ? (isFuneral ? '찾아뵙지 못할 때 전하는 위로' : '함께하지 못할 때 전하는 축하') : isFuneral ? '조심스럽게 전하는 위로' : '마음을 담은 메시지 초안', text, evidence, suggestions: ['불참할 때 보낼 메시지', '금액도 참고하고 싶어요'], isMessage: true }
  }
  if (intent === 'attendance') {
    const text = cannotAttend
      ? `${target.name}님께 참석이 어려운 사정을 미리 짧게 전하고 ${isFuneral ? '깊은 위로의 마음' : '축하의 마음'}을 함께 표현해 보세요. ${incoming ? `과거에 ${formatMoney(incoming.amount)}을 받은 기록도 함께 참고할 수 있어요. ` : ''}${isFuneral ? '답장을 재촉하지 않고, 시간이 지난 뒤 한 번 더 안부를 전하면 좋겠습니다.' : '행사가 끝난 뒤 다시 안부를 전하면 관계를 이어 가는 데 도움이 돼요.'}`
      : `${target.name}님의 ${event?.type || '행사'}${event?.date ? `는 ${event.date.replaceAll('-', '.')}에 예정되어 있어요` : ' 일정을 먼저 확인해 보세요'}. ${isFuneral ? '조문 가능 시간과 빈소를 확인하고, 말보다 조용한 곁이 되어 주세요.' : '장소와 시간을 확인한 뒤 참석 여부를 미리 알려 주세요.'} ${incoming ? `받은 마음 ${formatMoney(incoming.amount)}도 준비할 때 참고할 수 있어요.` : '주고받은 기록이 없어 금액을 단정할 수는 없어요.'}`
    return { title: cannotAttend ? '함께하지 못해도 마음은 전할 수 있어요' : '참석 전, 이렇게 준비해 보세요', text, evidence, suggestions: ['보낼 메시지를 작성해 주세요', '금액 참고하기'] }
  }
  if (intent === 'priority') {
    const ranked = events.filter((item) => daysUntil(item.date, today) >= 0).map((item) => ({ ...item, days: daysUntil(item.date, today), person: people.find((entry) => entry.id === item.personId) })).sort((a, b) => Number(b.type === '장례식') - Number(a.type === '장례식') || a.days - b.days || importanceRank(b.person?.importance) - importanceRank(a.person?.importance))
    const next = ranked[0]
    if (!next) return { title: '예정된 경조사가 없어요', text: '새 일정을 등록하면 날짜와 관계 중요도를 함께 살펴볼 수 있어요.', evidence, suggestions: ['새 일정 등록하기'] }
    return { title: '가장 먼저 챙길 마음', text: `${next.title}${next.days === 0 ? '이 오늘이에요' : `까지 ${next.days}일 남았어요`}. ${next.type === '장례식' ? '갑작스러운 조사인 만큼 빈소와 조문 가능 시간을 먼저 확인해 주세요.' : `참석 여부${!next.attendance ? '가 아직 정해지지 않았어요. 먼저 일정을 확인하고 참석 여부를 알려 주세요.' : '와 장소를 다시 확인해 주세요.'}`} ${ranked.length > 1 ? `그다음은 ${ranked[1].title}(${ranked[1].date.replaceAll('-', '.')})입니다.` : ''}`, evidence: [{ label: '선정 기준', value: '조사 우선 · 가까운 날짜 · 같은 날은 매우 중요 → 중요 → 보통' }, { label: '관계 중요도', value: next.person ? normalizeImportance(next.person.importance) : '미등록' }, { label: '참석 여부', value: next.attendance || '참석 여부 선택' }], suggestions: ['참석 대응 가이드', '메시지 작성하기'] }
  }
  const amount = incoming?.amount || (outgoing && event && outgoing.type === event.type ? outgoing.amount : null)
  return {
    title: `${target.name}님께 전할 마음, 기록을 참고해 보세요`,
    text: amount
      ? `${target.name}님${incoming ? `께 ${formatMoney(incoming.amount)}을 받은 기록이 있어요` : `께 ${formatMoney(amount)}을 보낸 같은 유형의 기록이 있어요`}. 이번 ${event?.type || '경조사'}에도 ${formatMoney(amount)}을 하나의 참고점으로 살펴볼 수 있습니다. ${importanceRank(target.importance) > 0 ? '중요한 관계로 등록되어 있지만, ' : ''}현재의 친밀도와 참석 여부, 본인의 예산에 맞춰 편안하게 결정해 주세요.`
      : `${target.name}님과 주고받은 ${event?.type || '경조사'} 금액을 비교할 기록이 아직 충분하지 않아요. 금액을 임의로 제안하기보다는 현재 관계와 참석 여부, 본인의 예산을 먼저 살펴보세요. 새 기록이 쌓이면 과거 내역을 함께 참고할 수 있어요.`,
    evidence,
    suggestions: ['참석하지 못한다면?', '축하·위로 메시지 작성'],
    ...(amount ? { amount } : {}),
  }
}

const escapeICS = (value) => String(value || '').replaceAll('\\', '\\\\').replaceAll('\n', '\\n').replaceAll(',', '\\,').replaceAll(';', '\\;')

export function toICS(event) {
  if (!localDate(event.date)) throw new Error('올바른 행사 날짜가 필요해요.')
  const compactDate = event.date.replaceAll('-', '')
  const hasTime = /^\d{2}:\d{2}$/.test(event.time || '')
  const dateLine = hasTime ? `DTSTART;TZID=Asia/Seoul:${compactDate}T${event.time.replace(':', '')}00` : `DTSTART;VALUE=DATE:${compactDate}`
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Maeum//Gyeongjosa Calendar//KO', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'BEGIN:VEVENT', `UID:${escapeICS(event.id || globalThis.crypto?.randomUUID?.() || Date.now())}@maeum.local`, `DTSTAMP:${stamp}`, dateLine, `SUMMARY:${escapeICS(event.title)}`, `LOCATION:${escapeICS(event.location)}`, `DESCRIPTION:${escapeICS(event.memo)}`]
  if (Number.isFinite(Number(event.reminderDays)) && Number(event.reminderDays) >= 0) lines.push('BEGIN:VALARM', `TRIGGER:-P${Number(event.reminderDays)}D`, 'ACTION:DISPLAY', `DESCRIPTION:${escapeICS(event.title)} 알림`, 'END:VALARM')
  lines.push('END:VEVENT', 'END:VCALENDAR')
  return lines.join('\r\n') + '\r\n'
}
