import { useMemo, useState } from 'react'
import { Icon, EmptyState } from './ui.jsx'
import { daysUntil } from './domain.js'
import { displayScheduleTitle, isSyntheticScheduleTitle } from './scheduleTitle.js'
import './schedule.css'

const TYPES = ['전체', '결혼식', '장례식', '돌잔치', '생일']
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const TYPE_ICON = { 결혼식: 'heart', 장례식: 'flower-2', 돌잔치: 'cake', 생일: 'gift' }
const TYPE_CLASS = { 결혼식: 'wedding', 장례식: 'funeral', 돌잔치: 'baby', 생일: 'birthday' }

function seoulToday() {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const part = (type) => parts.find((entry) => entry.type === type)?.value
  return `${part('year')}-${part('month')}-${part('day')}`
}

function dateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function readDate(date) {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export default function SchedulePage({ events = [], people = [], onAddEvent, onOpenEvent, onUpdateEvent, onOpenReceived, receivedCount = 0 }) {
  const today = seoulToday()
  const [month, setMonth] = useState(() => {
    const upcoming = [...events].filter((event) => event.date >= today).sort((a, b) => a.date.localeCompare(b.date))[0]
    const date = readDate(upcoming?.date || today)
    return { year: date.getFullYear(), month: date.getMonth() }
  })
  const [selectedDay, setSelectedDay] = useState(null)
  const [type, setType] = useState('전체')
  const monthPrefix = `${month.year}-${String(month.month + 1).padStart(2, '0')}`
  const monthEvents = useMemo(() => [...events].filter((event) => event.date.startsWith(monthPrefix)).sort((a, b) => a.date.localeCompare(b.date) || (a.time || '').localeCompare(b.time || '')), [events, monthPrefix])
  const filteredEvents = events.filter((event) => type === '전체' || event.type === type)
  const listedEvents = monthEvents.filter((event) => (type === '전체' || event.type === type) && (!selectedDay || event.date === selectedDay))
  const showSyntheticNotice = monthEvents.some((event) => (type === '전체' || event.type === type) && isSyntheticScheduleTitle(event.title))
  const firstDay = new Date(month.year, month.month, 1)
  const daysInMonth = new Date(month.year, month.month + 1, 0).getDate()
  const cellCount = Math.ceil((firstDay.getDay() + daysInMonth) / 7) * 7
  const cells = Array.from({ length: cellCount }, (_, index) => new Date(month.year, month.month, index - firstDay.getDay() + 1))

  function moveMonth(offset) {
    const next = new Date(month.year, month.month + offset, 1)
    setMonth({ year: next.getFullYear(), month: next.getMonth() })
    setSelectedDay(null)
  }

  function selectDay(date) {
    const key = dateKey(date)
    if (date.getMonth() !== month.month || date.getFullYear() !== month.year) setMonth({ year: date.getFullYear(), month: date.getMonth() })
    setSelectedDay((current) => current === key ? null : key)
  }

  function showToday() {
    const date = readDate(today)
    setMonth({ year: date.getFullYear(), month: date.getMonth() })
    setSelectedDay(today)
  }

  return <div className={`schedule-page ${type === '장례식' ? 'mood-somber' : ''}`}>
    <div className="schedule-page-heading">
      <div><span className="schedule-eyebrow">경조사 일정</span><h1>잊지 않고, 마음 전하기</h1><p>함께할 날을 기억하고, 전할 마음을 미리 준비해요.</p>{showSyntheticNotice && <p>시연용 가상 데이터가 포함되어 있습니다.</p>}</div>
      <div className="schedule-heading-actions"><button type="button" className="button button-secondary" onClick={() => onOpenReceived?.()}><Icon name="Mail" size={17} />받은 일정{receivedCount > 0 && <span className="received-count" aria-label={`새 일정 ${receivedCount}건`}>{receivedCount}</span>}</button><button className="button button-primary" onClick={onAddEvent}><Icon name="plus" size={17} />일정 등록</button></div>
    </div>

    <div className="schedule-layout">
      <section className="card schedule-calendar" aria-label="경조사 달력">
        <div className="schedule-calendar-header">
          <div className="schedule-month-title"><h2>{month.year}년 <strong>{month.month + 1}월</strong></h2><span>{monthEvents.length}개의 마음을 챙길 날</span></div>
          <div className="schedule-calendar-nav"><button className="schedule-today-button" onClick={showToday}>오늘</button><div><button aria-label="이전 달" onClick={() => moveMonth(-1)}><Icon name="chevron-left" size={18} /></button><button aria-label="다음 달" onClick={() => moveMonth(1)}><Icon name="chevron-right" size={18} /></button></div></div>
        </div>
        <div className="schedule-type-filters" aria-label="경조사 유형 필터">
          {TYPES.map((item) => <button key={item} className={`schedule-type-filter ${type === item ? 'active' : ''}`} aria-pressed={type === item} onClick={() => setType(item)}>{item !== '전체' && <i className={TYPE_CLASS[item]} />}{item}{item === '전체' && <span>{monthEvents.length}</span>}</button>)}
        </div>
        <div className="schedule-weekdays" aria-hidden="true">{WEEKDAYS.map((weekday, index) => <span className={index === 0 ? 'sunday' : index === 6 ? 'saturday' : ''} key={weekday}>{weekday}</span>)}</div>
        <div className="schedule-calendar-grid" role="group" aria-label={`${month.year}년 ${month.month + 1}월 날짜 선택`}>
          {cells.map((date) => {
            const key = dateKey(date)
            const dayEvents = filteredEvents.filter((event) => event.date === key)
            const outside = date.getMonth() !== month.month
            const isToday = key === today
            return <div key={key} className={`schedule-day ${outside ? 'outside-month' : ''} ${isToday ? 'is-today' : ''} ${selectedDay === key ? 'selected-day' : ''} ${date.getDay() === 0 ? 'sunday' : date.getDay() === 6 ? 'saturday' : ''}`}>
              <button className="schedule-day-select" aria-pressed={selectedDay === key} aria-current={isToday ? 'date' : undefined} aria-label={`${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 ${WEEKDAYS[date.getDay()]}요일${isToday ? ', 오늘' : ''}, 일정 ${dayEvents.length}개`} onClick={() => selectDay(date)}><span>{date.getDate()}</span>{isToday && <small>오늘</small>}</button>
              <div className="schedule-day-events">{dayEvents.slice(0, 2).map((event) => <button key={event.id} className={`schedule-event-chip ${TYPE_CLASS[event.type] || 'other'}`} title={`${displayScheduleTitle(event.title)} · ${event.time || '시간 미정'}`} aria-label={`${displayScheduleTitle(event.title)}, ${event.time || '시간 미정'}, 상세 보기`} onClick={() => onOpenEvent(event)}><i /><span>{displayScheduleTitle(event.title)}</span></button>)}{dayEvents.length > 2 && <button className="schedule-more-events" onClick={() => selectDay(date)} aria-label={`${date.getDate()}일 일정 ${dayEvents.length}개 모두 보기`}>+{dayEvents.length - 2}개 더</button>}</div>
            </div>
          })}
        </div>
        <div className="schedule-calendar-footer"><span><i />날짜를 선택하면 그날의 일정을 볼 수 있어요</span>{selectedDay && <button onClick={() => setSelectedDay(null)}>월 전체 보기<Icon name="arrow-right" size={13} /></button>}</div>
      </section>
      <aside className="schedule-agenda">
        <section className="card schedule-agenda-card">
          <div className="schedule-agenda-heading"><div><span className="schedule-agenda-eyebrow">기억할 날</span><h2>{selectedDay ? `${Number(selectedDay.slice(5, 7))}월 ${Number(selectedDay.slice(8))}일의 일정` : '이번 달, 챙길 마음'}<span>{listedEvents.length}</span></h2></div>{selectedDay && <button className="schedule-clear-selection" title="날짜 선택 해제" aria-label="날짜 선택 해제" onClick={() => setSelectedDay(null)}><Icon name="x" size={15} /></button>}</div>
          <div className="schedule-agenda-list">
            {listedEvents.length ? listedEvents.map((event) => {
              const person = people.find((entry) => entry.id === event.personId)
              const days = daysUntil(event.date, today)
              const date = readDate(event.date)
              return <article className={`schedule-agenda-event ${TYPE_CLASS[event.type] || 'other'}`} key={event.id}>
                <button className="schedule-agenda-event-main" onClick={() => onOpenEvent(event)}>
                  <div className="schedule-agenda-date"><span>{month.month + 1}월</span><strong>{date.getDate()}</strong><small>{WEEKDAYS[date.getDay()]}</small></div>
                  <div className="schedule-agenda-event-info"><div><span className="schedule-agenda-type"><Icon name={TYPE_ICON[event.type] || 'calendar'} size={12} />{event.type}</span>{days !== null && days >= 0 && <span className={`schedule-dday ${days <= 3 ? 'soon' : ''}`}>{days === 0 ? 'D-DAY' : `D-${days}`}</span>}</div><h3>{displayScheduleTitle(event.title)}</h3><p>{event.owner === 'me' ? '내 경조사' : person ? `${person.relation} · ${person.group || '그룹 없음'}` : '관계 미등록'}{event.source?.from ? ` · ${event.source.from}님이 보낸 일정` : ''}</p><span className="schedule-agenda-time"><Icon name="clock" size={12} />{event.time || '시간 미정'}</span></div>
                </button>
                {event.location && <p className="schedule-agenda-location"><Icon name="map-pin" size={12} /><span>{event.location}</span></p>}
                <div className="schedule-agenda-event-bottom"><label><span className="schedule-attendance-label">참석 여부</span><select value={event.attendance || ''} aria-label={`${displayScheduleTitle(event.title)} 참석 여부`} onChange={(change) => onUpdateEvent(event.id, { attendance: change.target.value })}><option value="" disabled>참석 여부 선택</option><option>참석</option><option>불참</option></select></label><span><Icon name="bell" size={11} />{Number(event.reminderDays) === 0 ? '당일 알림' : `${event.reminderDays || 1}일 전`}</span></div>
              </article>
            }) : <EmptyState icon="calendar" title={selectedDay ? '비워 둔 하루예요' : '아직 예정된 경조사가 없어요'} description={selectedDay ? '마음을 전할 날이 생기면 새 일정을 등록해 주세요.' : '필터를 바꾸거나 새로운 일정을 등록해 보세요.'} />}
          </div>
          {!selectedDay && <button className="schedule-agenda-add" onClick={onAddEvent}><Icon name="plus" size={15} />새로운 일정 더하기</button>}
        </section>
        <div className="schedule-reminder-note"><div><Icon name="bell" size={19} /></div><h3>미리 알려드릴게요</h3><p>일정마다 나에게 맞는 알림 시점을<br />설정하고, 여유 있게 마음을 준비해요.</p><span>작은 기억이, 오래가는 인연으로</span></div>
      </aside>
    </div>
  </div>
}
