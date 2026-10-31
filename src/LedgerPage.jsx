import { useMemo, useState } from 'react';
import { Icon, EmptyState, Modal } from './ui.jsx';
import { formatMoney, monthSpending, typeSpending } from './domain.js';
import './people-ledger.css';
import { CsvExportModal, CsvImportModal } from './LedgerCsvModal.jsx';
import './ledger-tools.css';

const typeColors = ['var(--primary)', 'var(--accent)', '#b4bb98', '#a3b3bf', '#d4bd9d'];
const shortMoney = value => value >= 10000 ? `${Number((value / 10000).toFixed(1))}만` : new Intl.NumberFormat('ko-KR').format(value);

export default function LedgerPage({ people, events, records, onAddRecord, onEditRecord, onDeleteRecord, onImportRecords, notify }) {
  const [csvPanel, setCsvPanel] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState('전체');
  const [direction, setDirection] = useState('전체');
  const [type, setType] = useState('전체');
  const [query, setQuery] = useState('');
  const [chartPeriod, setChartPeriod] = useState('월별');
  const years = [...new Set([currentYear, ...records.map(record => Number(record.date.slice(0, 4)))])].sort((a, b) => b - a);
  const yearRecords = records.filter(record => record.date.startsWith(year));
  const periodRecords = yearRecords.filter(record => month === '전체' || Number(record.date.slice(5, 7)) === Number(month));
  const sumDirection = value => periodRecords.filter(record => record.direction === value).reduce((sum, record) => sum + Number(record.amount), 0);
  const sent = sumDirection('보낸 마음');
  const received = sumDirection('받은 마음');
  const visibleRecords = useMemo(() => periodRecords.filter(record => {
    const person = people.find(item => item.id === record.personId);
    const event = events.find(item => item.id === record.eventId);
    return (direction === '전체' || record.direction === direction) && (type === '전체' || record.type === type) && `${person?.name || ''} ${person?.relation || ''} ${record.memo || ''} ${record.type} ${event?.title || ''}`.toLowerCase().includes(query.toLowerCase());
  }).sort((a, b) => b.date.localeCompare(a.date)), [periodRecords, people, events, direction, type, query]);
  const monthly = monthSpending(records, Number(year));
  const yearly = [...years].sort((a, b) => a - b).map(item => ({ label: `${item}년`, amount: records.filter(record => record.date.startsWith(String(item)) && record.direction === '보낸 마음').reduce((sum, record) => sum + Number(record.amount), 0) }));
  const chartData = chartPeriod === '월별' ? monthly : yearly;
  const maxValue = Math.max(...chartData.map(item => item.amount), 1);
  const types = typeSpending(records, Number(year)).filter(item => item.amount > 0);
  const annualSent = yearRecords.filter(record => record.direction === '보낸 마음').reduce((sum, record) => sum + Number(record.amount), 0);
  let progress = 0;
  const donutStops = types.map((item, index) => {
    const start = progress;
    progress += annualSent ? item.amount / annualSent * 100 : 0;
    return `${typeColors[index % typeColors.length]} ${start}% ${progress}%`;
  });
  return <div className="ledger-page">
    <div className="pl-page-heading"><div><span className="pl-eyebrow">MONEY & MEMORIES</span><h1>마음을 주고받은 기록</h1><p>보낸 마음도, 받은 마음도. 다음 순간을 위해 기억해요.</p></div><div className="ledger-heading-actions"><button className="button button-primary" onClick={() => onAddRecord()}><Icon name="plus" size={17} />금액 기록</button></div></div>
    <div className="ledger-period-bar"><div><Icon name="calendar" size={17} /><strong>{year}년{month !== '전체' ? ` ${month}월` : '의 기록'}</strong><span className="muted">{periodRecords.length}건의 마음을 나눴어요</span></div><div><label className="ledger-select-label"><span className="sr-only">조회 연도</span><select className="input" aria-label="조회 연도" value={year} onChange={e => setYear(e.target.value)}>{years.map(item => <option key={item} value={item}>{item}년</option>)}</select></label><label className="ledger-select-label"><span className="sr-only">조회 월</span><select className="input" aria-label="조회 월" value={month} onChange={e => setMonth(e.target.value)}><option value="전체">전체 월</option>{Array.from({ length: 12 }, (_, index) => <option key={index} value={index + 1}>{index + 1}월</option>)}</select></label></div></div>
    <div className="ledger-summary-grid"><Summary icon="arrow-up-right" label="내가 보낸 마음" amount={sent} count={periodRecords.filter(record => record.direction === '보낸 마음').length} tone="sent" /><Summary icon="arrow-down-left" label="내가 받은 마음" amount={received} count={periodRecords.filter(record => record.direction === '받은 마음').length} tone="received" /><div className="card ledger-summary ledger-summary-balance"><div><span className="ledger-summary-icon"><Icon name="heart-handshake" size={19} /></span><span>주고받은 마음의 차이</span></div><strong>{formatMoney(Math.abs(sent - received))}</strong><p>{sent === received ? '같은 만큼 마음을 나눴어요' : sent > received ? '보낸 마음이 더 많아요' : '받은 마음이 더 많아요'}</p></div></div>
    <div className="ledger-charts-grid">
      <section className="card ledger-chart-card"><div className="ledger-card-heading"><div><h2>{chartPeriod} 경조사 지출</h2><p>{chartPeriod === '월별' ? `${year}년 · 보낸 금액 기준` : '전체 연도 · 보낸 금액 기준'}</p></div><div className="ledger-chart-tabs">{['월별', '연도별'].map(item => <button key={item} className={chartPeriod === item ? 'active' : ''} onClick={() => setChartPeriod(item)}>{item}</button>)}</div></div><div className="ledger-bar-chart" role="img" aria-label={`${chartPeriod} 지출: ${chartData.map(item => `${item.label} ${formatMoney(item.amount)}`).join(', ')}`}><div className="ledger-chart-gridlines"><span>{shortMoney(maxValue)}원</span><span>{shortMoney(Math.round(maxValue / 2))}원</span><span>0원</span></div><div className="ledger-bar-columns">{chartData.map((item, index) => <div className="ledger-bar-column" key={item.label || index} title={`${item.label}: ${formatMoney(item.amount)}`}><div className="ledger-bar-area"><span className="ledger-bar-value">{item.amount ? shortMoney(item.amount) : ''}</span><div className={`ledger-bar ${item.amount === maxValue ? 'peak' : ''} ${item.amount === 0 ? 'zero' : ''}`} style={{ height: `${item.amount ? Math.max(item.amount / maxValue * 100, 3) : 1}%` }} /></div><span className="ledger-bar-label">{item.label}</span></div>)}</div></div><div className="ledger-chart-footer"><span>{chartPeriod === '월별' ? `${year}년 누적 지출` : '전체 누적 지출'}</span><strong>{formatMoney(chartData.reduce((sum, item) => sum + item.amount, 0))}</strong></div></section>
      <section className="card ledger-types-card"><div className="ledger-card-heading"><div><h2>어떤 마음을 전했나요?</h2><p>{year}년 · 경조사 유형별 지출</p></div></div><div className="ledger-donut-wrap"><div className="ledger-donut" role="img" aria-label={types.length ? types.map(item => `${item.type} ${formatMoney(item.amount)}`).join(', ') : '지출 내역 없음'} style={{ background: types.length ? `conic-gradient(${donutStops.join(',')})` : 'var(--border)' }}><div><span>총 지출</span><strong>{shortMoney(annualSent)}<small>원</small></strong></div></div></div><div className="ledger-type-legend">{types.length ? types.map((item, index) => <div key={item.type}><span><i style={{ background: typeColors[index % typeColors.length] }} />{item.type}<small>{item.count}건</small></span><strong>{formatMoney(item.amount)}</strong></div>) : <p className="muted">올해 보낸 마음을 기록해 보세요.</p>}</div></section>
    </div>
    <section className="card ledger-records-card"><div className="ledger-card-heading"><div><h2>경조사금 장부 <span>{visibleRecords.length}</span></h2><p>사람별, 행사별로 찾아보는 주고받은 마음</p></div></div><div className="ledger-record-controls"><div className="ledger-direction-tabs">{['전체', '보낸 마음', '받은 마음'].map(item => <button key={item} className={`filter-chip ${direction === item ? 'active' : ''}`} onClick={() => setDirection(item)}>{item}</button>)}</div><label className="pl-search ledger-search"><Icon name="search" size={16} /><input aria-label="금액 기록 검색" placeholder="이름 또는 행사로 검색" value={query} onChange={e => setQuery(e.target.value)} /></label></div><div className="ledger-type-filters">{['전체', '결혼식', '장례식', '돌잔치', '생일', '기타'].map(item => <button className={type === item ? 'active' : ''} key={item} onClick={() => setType(item)}>{item === '전체' ? '전체 유형' : item}</button>)}</div>{visibleRecords.length ? <div className="ledger-table-wrap"><table className="ledger-table"><thead><tr><th>이름 / 관계</th><th>경조사</th><th>날짜</th><th>구분</th><th>금액</th><th>관리</th></tr></thead><tbody>{visibleRecords.map(record => {
      const person = people.find(item => item.id === record.personId);
      const event = events.find(item => item.id === record.eventId);
      return <tr key={record.id}><td><div className="ledger-table-person"><span className="avatar">{(person?.name || '?').slice(0, 1)}</span><span><strong>{person?.name || '이름 미등록'}</strong><small>{person?.relation || '관계 미등록'}{person?.group ? ` · ${person.group}` : ''}</small></span></div></td><td><span className={`ledger-event-type ${record.type === '장례식' ? 'somber' : ''}`}><Icon name={record.type === '장례식' ? 'Flower2' : record.type === '결혼식' ? 'heart' : 'gift'} size={13} />{record.type}</span>{(record.memo || event?.title) && <small className="ledger-table-memo">{record.memo || event.title}</small>}</td><td className="ledger-date">{record.date.replaceAll('-', '.')}</td><td><span className={`badge ${record.direction === '받은 마음' ? 'green' : 'peach'}`}><Icon name={record.direction === '받은 마음' ? 'arrow-down-left' : 'arrow-up-right'} size={12} />{record.direction === '받은 마음' ? '받음' : '보냄'}</span></td><td className="ledger-table-amount">{formatMoney(record.amount)}</td><td><div className="ledger-row-actions"><button className="icon-button" aria-label={`${person?.name || '이름 미등록'} ${record.date} ${formatMoney(record.amount)} 기록 수정`} title="수정" onClick={() => onEditRecord(record.id)}><Icon name="Pencil" size={14} /></button><button className="icon-button delete-action" aria-label={`${person?.name || '이름 미등록'} ${record.date} ${formatMoney(record.amount)} 기록 삭제`} title="삭제" onClick={() => setDeleteTarget(record)}><Icon name="Trash2" size={14} /></button></div></td></tr>;
    })}</tbody></table></div> : <EmptyState icon="notebook-pen" title="이 조건에 맞는 기록이 없어요" description="기간과 필터를 변경하거나 새로운 금액 기록을 남겨보세요." />}<div className="ledger-record-footer"><Icon name="heart" size={14} /><span>금액은 관계를 평가하는 기준이 아니라, 다음 마음을 위한 참고 기록이에요.</span></div></section>
    <details className="card ledger-file-management"><summary><Icon name="FileText" size={17}/><span>파일로 기록 관리<small>CSV 가져오기 · 내보내기</small></span><Icon name="ChevronDown" size={16}/></summary><div><p>기존 장부를 옮기거나 기록을 파일로 보관할 때 사용하세요.</p><div className="ledger-file-actions"><button className="button button-secondary" onClick={() => setCsvPanel('import')}><Icon name="FileText" size={16} />CSV 가져오기</button><button className="button button-secondary" onClick={() => setCsvPanel('export')} disabled={!records.length}><Icon name="Download" size={16} />CSV 내보내기</button></div></div></details>
    {csvPanel === 'export' && <CsvExportModal records={records} visibleRecords={visibleRecords} people={people} notify={notify} onClose={() => setCsvPanel(null)} />}
    {csvPanel === 'import' && <CsvImportModal people={people} events={events} records={records} onImport={onImportRecords} onClose={() => setCsvPanel(null)} />}
    {deleteTarget && <Modal title="금액 기록을 삭제할까요?" subtitle="삭제할 내역을 한 번 더 확인해 주세요." onClose={() => setDeleteTarget(null)}><div className="ledger-delete-summary"><strong>{people.find(person => person.id === deleteTarget.personId)?.name || '이름 미등록'}</strong><p>{deleteTarget.date.replaceAll('-', '.')} · {deleteTarget.type} · {deleteTarget.direction}</p><b>{formatMoney(deleteTarget.amount)}</b>{deleteTarget.memo && <p className="delete-memo">{deleteTarget.memo}</p>}</div><p className="delete-explanation">금액 기록만 삭제하며, 장부·사람별 이력·통계에도 반영됩니다. 인맥과 일정은 유지돼요.</p><div className="form-actions"><button className="button button-secondary" onClick={() => setDeleteTarget(null)}>취소</button><button className="button button-danger" onClick={() => { if(onDeleteRecord(deleteTarget.id)) setDeleteTarget(null); }}><Icon name="Trash2" size={16} />삭제하기</button></div></Modal>}
  </div>;
}

function Summary({ icon, label, amount, count, tone }) {
  return <div className={`card ledger-summary ${tone}`}><div><span className="ledger-summary-icon"><Icon name={icon} size={19} /></span><span>{label}</span></div><strong>{formatMoney(amount)}</strong><p>총 {count}건의 마음</p></div>;
}
