import { useMemo, useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import { formatMoney } from './domain.js';
import { RELATION_OPTIONS, IMPORTANCE_OPTIONS, relationDraft, resolveRelation, matchesRelation, normalizeImportance, importanceRank } from './relationships.js';
import './people-ledger.css';

const relations = ['전체', ...RELATION_OPTIONS];
const personDraft = person => ({ name:person.name, ...relationDraft(person.relation), group:person.group || '', importance:normalizeImportance(person.importance), lastMet:person.lastMet || '', memo:person.memo || '' });
const displayDate = (date) => date ? date.replaceAll('-', '.') : '아직 기록이 없어요';
const todayString = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

export default function PeoplePage({ people, events, records, onAddPerson, onUpdatePerson, onAddRecord }) {
  const [query, setQuery] = useState('');
  const [relation, setRelation] = useState('전체');
  const [selectedId, setSelectedId] = useState(null);
  const [importantOnly, setImportantOnly] = useState(false);
  const selected = people.find(person => person.id === selectedId);
  const visiblePeople = useMemo(() => people.filter(person =>
    matchesRelation(person.relation, relation) &&
    (!importantOnly || importanceRank(person.importance) > 0) &&
    `${person.name} ${person.relation} ${person.group} ${person.memo || ''}`.toLowerCase().includes(query.toLowerCase())
  ), [people, relation, importantOnly, query]);

  return <div className="people-page">
    <div className="pl-page-heading">
      <div><span className="pl-eyebrow">RELATIONSHIPS</span><h1>오래 이어갈 인연</h1><p>가까운 사람부터, 함께한 순간까지 기억해요.</p></div>
      <button className="button button-primary" onClick={onAddPerson}><Icon name="user-plus" size={17} />인맥 등록</button>
    </div>
    <section className="card people-directory">
      <div className="people-toolbar">
        <label className="pl-search"><Icon name="search" size={18} /><input aria-label="인맥 검색" placeholder="이름, 관계, 그룹으로 검색" value={query} onChange={e => setQuery(e.target.value)} />{query && <button aria-label="검색 지우기" onClick={() => setQuery('')}><Icon name="x" size={15} /></button>}</label>
        <button className={`filter-chip people-important-filter ${importantOnly ? 'active' : ''}`} aria-pressed={importantOnly} onClick={() => setImportantOnly(value => !value)}><Icon name="star" size={15} />중요한 인연</button>
      </div>
      <div className="people-relation-filters" aria-label="관계별 필터">
        {relations.map(item => <button key={item} className={`filter-chip ${relation === item ? 'active' : ''}`} onClick={() => setRelation(item)}>{item}<span>{people.filter(person => matchesRelation(person.relation, item)).length}</span></button>)}
      </div>
    </section>
    <div className="people-results-heading"><span>함께하는 인연 <strong>{visiblePeople.length}</strong></span><span className="muted">소중한 관계를 차곡차곡</span></div>
    {visiblePeople.length === 0 ? <div className="card"><EmptyState icon="users" title="아직 찾는 인연이 없어요" description="검색어나 관계 필터를 바꾸거나 새로운 인연을 등록해 보세요." /></div> : <div className="people-grid">
      {visiblePeople.map((person, index) => {
        const personalEvents = events.filter(event => event.personId === person.id).sort((a, b) => a.date.localeCompare(b.date));
        const nextEvent = personalEvents.find(event => event.date >= todayString()) || personalEvents.at(-1);
        const sent = records.filter(record => record.personId === person.id && record.direction === '보낸 마음').reduce((sum, record) => sum + Number(record.amount), 0);
        const received = records.filter(record => record.personId === person.id && record.direction === '받은 마음').reduce((sum, record) => sum + Number(record.amount), 0);
        return <button className="card people-person-card" key={person.id} onClick={() => setSelectedId(person.id)} style={{ '--card-delay': `${index * 35}ms` }}>
          <div className="people-person-top"><div className={`avatar people-avatar tone-${index % 4}`}>{person.name.slice(0, 1)}</div><div className="people-person-name"><h3>{person.name}</h3><span>{person.relation}<i />{person.group || '그룹 없음'}</span></div>{importanceRank(person.importance) > 0 && <span className="people-star" title={normalizeImportance(person.importance)} aria-label={normalizeImportance(person.importance)}><Icon name="star" size={15} fill={importanceRank(person.importance) === 2 ? 'currentColor' : 'none'} /></span>}</div>
          <div className="people-person-note"><Icon name="calendar" size={14} /><span>마지막 만남</span><strong>{person.lastMet ? displayDate(person.lastMet) : '기록 없음'}</strong></div>
          <div className="people-person-money"><span>보낸 마음<strong>{formatMoney(sent)}</strong></span><span>받은 마음<strong>{formatMoney(received)}</strong></span></div>
          <div className="people-person-bottom"><span>{nextEvent ? `${displayDate(nextEvent.date).slice(5)} · ${nextEvent.type}` : '새로운 이야기를 남겨 보세요'}</span><span className="people-detail-link">관계 기록<Icon name="arrow-up-right" size={15} /></span></div>
        </button>;
      })}
    </div>}
    <div className="people-gentle-note"><Icon name="heart" size={16} /><p>관계의 깊이는 금액으로 정해지지 않아요. 함께한 시간을 기억하는 작은 기록이에요.</p></div>
    {selected && <PersonDetail key={selected.id} person={selected} events={events.filter(event => event.personId === selected.id)} records={records.filter(record => record.personId === selected.id)} onUpdate={patch => onUpdatePerson(selected.id, patch)} onAddRecord={() => { setSelectedId(null); onAddRecord(selected.id); }} onClose={() => setSelectedId(null)} />}
  </div>;
}

function PersonDetail({ person, events, records, onUpdate, onAddRecord, onClose }) {
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState('관계 기록');
  const [draft, setDraft] = useState(() => personDraft(person));
  const [interaction, setInteraction] = useState({ date: todayString(), note: '' });
  const sent = records.filter(record => record.direction === '보낸 마음').reduce((sum, record) => sum + Number(record.amount), 0);
  const received = records.filter(record => record.direction === '받은 마음').reduce((sum, record) => sum + Number(record.amount), 0);
  const interactions = [...(person.interactions || [])].sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
  function savePerson(event) {
    event.preventDefault();
    if (!draft.name.trim()) return;
    const { customRelation, ...values } = draft;
    onUpdate({ ...values, relation:resolveRelation(draft.relation, customRelation), name: draft.name.trim(), group: draft.group.trim(), memo: draft.memo.trim() });
    setEditing(false);
  }
  function addInteraction(event) {
    event.preventDefault();
    if (!interaction.note.trim()) return;
    onUpdate({ interactions: [...(person.interactions || []), { id: crypto.randomUUID(), date: interaction.date, note: interaction.note.trim() }], lastMet: !person.lastMet || interaction.date > person.lastMet ? interaction.date : person.lastMet });
    setInteraction(current => ({ ...current, note: '' }));
  }
  return <Modal title={`${person.name}님의 관계 기록`} onClose={onClose} wide>
    <div className="person-detail-header"><div className="avatar people-avatar">{person.name.slice(0, 1)}</div><div><h2>{person.name}<span className="badge green">{person.relation}</span><span className="badge">{normalizeImportance(person.importance)}</span></h2><p>{person.group || '소속 그룹 없음'} · 마지막 만남 {displayDate(person.lastMet)}</p></div><button className="button button-secondary" onClick={() => { setDraft(personDraft(person)); setEditing(value => !value); }}><Icon name="pencil" size={15} />{editing ? '편집 닫기' : '관계 편집'}</button></div>
    {editing && <form className="person-edit-form" onSubmit={savePerson}>
      <div className="people-form-grid">
        <label className="people-field">이름<input className="input" required maxLength={40} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
        <label className="people-field">관계<select className="input" aria-label="관계" value={draft.relation} onChange={e => setDraft({ ...draft, relation: e.target.value })}>{RELATION_OPTIONS.map(item => <option key={item}>{item}</option>)}</select></label>
        {draft.relation === '기타' && <label className="people-field">관계 직접 입력<input className="input" aria-label="관계 직접 입력" value={draft.customRelation} placeholder="예) 동호회 선배, 이웃" maxLength={40} onChange={e => setDraft({ ...draft, customRelation:e.target.value })} /><span className="field-hint">비워 두면 ‘기타’로 표시돼요.</span></label>}
        <label className="people-field">소속 그룹<input className="input" value={draft.group} placeholder="예: 대학 동기" maxLength={40} onChange={e => setDraft({ ...draft, group: e.target.value })} /></label>
        <label className="people-field">중요도<select className="input" aria-label="중요도" value={draft.importance} onChange={e => setDraft({ ...draft, importance: e.target.value })}>{IMPORTANCE_OPTIONS.map(value => <option key={value}>{value}</option>)}</select></label>
        <label className="people-field">마지막 만난 날짜<input className="input" type="date" max={todayString()} value={draft.lastMet} onChange={e => setDraft({ ...draft, lastMet: e.target.value })} /></label>
      </div><label className="people-field">기억할 메모<textarea className="input" rows={2} maxLength={1000} value={draft.memo} onChange={e => setDraft({ ...draft, memo: e.target.value })} /></label><button className="button button-primary" type="submit">변경사항 저장</button>
    </form>}
    <div className="person-money-summary"><div><span>내가 보낸 마음</span><strong>{formatMoney(sent)}</strong></div><div><span>내가 받은 마음</span><strong>{formatMoney(received)}</strong></div></div>
    <div className="people-detail-tabs" role="tablist">{['관계 기록', '경조사 이력', '금액 이력'].map(item => <button key={item} role="tab" aria-selected={tab === item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}<span>{item === '관계 기록' ? interactions.length : item === '경조사 이력' ? events.length : records.length}</span></button>)}</div>
    {tab === '관계 기록' && <div className="person-interactions">{person.memo && <div className="person-memo"><Icon name="notebook-pen" size={16} /><p>{person.memo}</p></div>}<form className="person-interaction-form" onSubmit={addInteraction}><label className="people-field">만난 날짜<input className="input" type="date" required max={todayString()} value={interaction.date} onChange={e => setInteraction({ ...interaction, date: e.target.value })} /></label><label className="people-field">함께한 순간<input className="input" required placeholder="예: 오랜만에 만나 저녁 식사" value={interaction.note} onChange={e => setInteraction({ ...interaction, note: e.target.value })} /></label><button className="button button-primary" type="submit"><Icon name="plus" size={16} />기록</button></form><div className="person-timeline">{interactions.length ? interactions.map((entry, index) => <div className="person-timeline-row" key={entry.id || index}><span className="person-timeline-dot" /><div><time>{displayDate(entry.date)}</time><p>{entry.note || entry.memo || entry.description || entry.content || '교류 기록'}</p></div></div>) : <EmptyState icon="message-circle" title="함께한 첫 순간을 남겨보세요" description="만남과 안부를 기록하면 다음 경조사에도 참고할 수 있어요." />}</div></div>}
    {tab === '경조사 이력' && <div className="person-history">{events.length ? [...events].sort((a, b) => b.date.localeCompare(a.date)).map(event => <div className="person-history-row" key={event.id}><div className={`person-history-icon ${event.type === '장례식' ? 'somber' : ''}`}><Icon name={event.type === '장례식' ? 'Flower2' : event.type === '돌잔치' ? 'cake' : 'heart'} size={18} /></div><div><strong>{event.title}</strong><p>{displayDate(event.date)} {event.time} · {event.location || '장소 미정'}</p></div><span className="badge">{event.attendance || '참석 여부 선택'}</span></div>) : <EmptyState icon="calendar" title="등록된 경조사가 없어요" description="일정을 등록하면 이곳에서 함께 확인할 수 있어요." />}</div>}
    {tab === '금액 이력' && <div className="person-history"><div className="person-history-action"><span className="muted">과거에 주고받은 마음을 참고해요.</span><button className="button button-secondary" onClick={onAddRecord}><Icon name="plus" size={15} />금액 기록</button></div>{records.length ? [...records].sort((a, b) => b.date.localeCompare(a.date)).map(record => <div className="person-history-row" key={record.id}><div className={`person-history-icon ${record.direction === '받은 마음' ? 'received' : ''}`}><Icon name={record.direction === '받은 마음' ? 'arrow-down-left' : 'arrow-up-right'} size={18} /></div><div><strong>{record.type} · {record.direction}</strong><p>{displayDate(record.date)}{record.memo ? ` · ${record.memo}` : ''}</p></div><strong className="person-history-amount">{formatMoney(record.amount)}</strong></div>) : <EmptyState icon="wallet" title="아직 금액 기록이 없어요" description="보내고 받은 마음을 기록해 다음에 참고해 보세요." />}</div>}
  </Modal>;
}
