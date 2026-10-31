import { useEffect, useRef, useState } from 'react';
import { Icon, Modal } from './ui.jsx';
import { csvTemplate, decodeCsv, exportRecordsCsv, prepareRecordImport } from './ledgerCsv.js';
import { formatMoney } from './domain.js';
import './ledger-tools.css';

function download(text, name) {
  const url = URL.createObjectURL(new Blob([text], {type:'text/csv;charset=utf-8;'}));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const today = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Seoul'}).format(new Date());

export function CsvExportModal({ records, visibleRecords, people, onClose, notify }) {
  const [scope, setScope] = useState('filtered');
  const selected = scope === 'all' ? records : visibleRecords;
  function save() {
    download(exportRecordsCsv(selected, people), `마음결_금액기록_${scope === 'all' ? '전체' : '조회결과'}_${today()}.csv`);
    notify(`${selected.length}건의 금액 기록을 CSV로 내보냈어요.`); onClose();
  }
  return <Modal title="금액 기록 CSV 내보내기" subtitle="내보낼 범위를 선택해 주세요." onClose={onClose}>
    <fieldset className="csv-scope"><legend className="sr-only">내보낼 기록 범위</legend>
      <label><input type="radio" name="export-scope" checked={scope === 'filtered'} onChange={() => setScope('filtered')} /><span><strong>현재 조회 결과</strong><small>선택한 기간·검색·유형 필터 적용</small></span><b>{visibleRecords.length}건</b></label>
      <label><input type="radio" name="export-scope" checked={scope === 'all'} onChange={() => setScope('all')} /><span><strong>전체 기록</strong><small>기간과 필터에 관계없이 모든 기록</small></span><b>{records.length}건</b></label>
    </fieldset>
    <p className="csv-help">이름·관계·그룹·행사유형·날짜·받음/냄·금액·메모와 연결 ID를 저장해요. 한글 엑셀에서 열 수 있는 UTF-8 CSV 형식입니다.</p>
    <div className="form-actions"><button className="button button-secondary" onClick={onClose}>취소</button><button className="button button-primary" disabled={!selected.length} onClick={save}><Icon name="Download" size={16} />{selected.length}건 내보내기</button></div>
  </Modal>;
}

export function CsvImportModal({ people, events, records, onImport, onClose }) {
  const [filename, setFilename] = useState('');
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState('');
  const [reading, setReading] = useState(false);
  const request = useRef(0);
  useEffect(() => () => { request.current++; }, []);
  async function readFile(file) {
    const token = ++request.current;
    setPlan(null); setError(''); setReading(false); setFilename(file?.name || '');
    if (!file) return;
    if (!/\.csv$/i.test(file.name)) { setError('CSV 파일을 선택해 주세요. 엑셀 파일은 CSV로 저장한 뒤 가져올 수 있어요.'); return; }
    if (file.size > 2 * 1024 * 1024) { setError('파일은 2MB 이하로 선택해 주세요. 한 번에 최대 5,000건을 가져올 수 있어요.'); return; }
    setReading(true);
    try {
      const text = decodeCsv(await file.arrayBuffer());
      const parsed = prepareRecordImport(text, {people, events, records});
      if (request.current === token) setPlan(parsed);
    } catch { if (request.current === token) setError('파일을 읽지 못했어요. UTF-8 또는 한글 CSV로 다시 저장해 주세요.'); }
    finally { if (request.current === token) setReading(false); }
  }
  function apply() {
    if (!plan?.rows.length || plan.errors.length) return;
    if (onImport(plan)) onClose();
  }
  return <Modal title="금액 기록 CSV 가져오기" subtitle="파일을 확인한 후 선택한 기록을 추가해요." onClose={onClose} wide>
    <div className="csv-import-guide"><p>필수 열: <strong>이름 · 행사유형 · 날짜 · 구분 · 금액</strong><br />같은 기록ID는 중복으로 제외하며, 기존 기록을 덮어쓰지 않아요. ID가 없는 행은 내용이 같은 기록을 제외해요.</p><button className="button button-secondary" onClick={() => download(csvTemplate(people, today()), '마음결_금액기록_양식.csv')}><Icon name="Download" size={15} />양식 다운로드</button></div>
    <label className="field csv-file-field"><span className="field-label">CSV 파일 선택</span><input type="file" className="input" accept=".csv,text/csv" aria-label="CSV 파일 선택" onChange={e => readFile(e.target.files?.[0])} /><span className="field-hint">UTF-8·한글(CP949) CSV · 최대 2MB / 5,000건</span></label>
    {reading && <p className="csv-help" role="status">파일을 확인하고 있어요…</p>}
    {error && <p className="form-error" role="alert"><Icon name="CircleAlert" size={16} />{error}</p>}
    {plan && <>
      <div className="csv-import-summary" role="status"><span>전체 <strong>{plan.totalCount}건</strong></span><span>추가 예정 <strong>{plan.rows.length}건</strong></span><span>중복 제외 <strong>{plan.duplicateCount}건</strong></span><span>새 인맥 <strong>{plan.newPeople.length}명</strong></span></div>
      {plan.errors.length > 0 && <div className="csv-errors" role="alert"><strong>오류 {plan.errors.length}건을 수정한 뒤 파일을 다시 선택해 주세요.</strong><ul>{plan.errors.slice(0,20).map((message,index) => <li key={index}>{message}</li>)}</ul>{plan.errors.length > 20 && <p>외 {plan.errors.length - 20}건</p>}<p>오류가 있으면 기록과 인맥 모두 저장하지 않아요.</p></div>}
      {plan.warnings.length > 0 && <details className="csv-notes"><summary>일정 연결 안내 {plan.warnings.length}건</summary><ul>{plan.warnings.slice(0,20).map((message,index) => <li key={index}>{message}</li>)}</ul></details>}
      {plan.newPeople.length > 0 && <div className="csv-new-people"><strong>함께 등록할 새 인맥</strong><p>{plan.newPeople.slice(0,15).map(person => `${person.name}(${person.relation}${person.group ? ` · ${person.group}` : ''})`).join(', ')}{plan.newPeople.length > 15 ? ` 외 ${plan.newPeople.length - 15}명` : ''}</p></div>}
      {plan.rows.length > 0 && <div className="csv-preview"><div className="csv-preview-heading"><strong>가져올 기록 미리보기</strong><span>{filename} · 처음 {Math.min(20,plan.rows.length)}건 표시</span></div><div className="ledger-table-wrap"><table className="ledger-table"><thead><tr><th>행</th><th>이름</th><th>날짜 / 행사</th><th>구분</th><th>금액</th></tr></thead><tbody>{plan.rows.slice(0,20).map((row,index) => <tr key={index}><td>{row.line}</td><td>{row.personName}</td><td>{row.date}<small className="csv-type">{row.type}</small></td><td>{row.direction}</td><td className="ledger-table-amount">{formatMoney(row.amount)}</td></tr>)}</tbody></table></div></div>}
      {!plan.rows.length && !plan.errors.length && <p className="csv-help">모두 이미 있는 기록이에요. 새로 추가할 내역이 없어요.</p>}
    </>}
    <div className="form-actions"><button className="button button-secondary" onClick={onClose}>취소</button><button className="button button-primary" disabled={reading || !plan?.rows.length || plan.errors.length > 0} onClick={apply}><Icon name="Check" size={16} />{plan?.rows.length || 0}건 가져오기</button></div>
  </Modal>;
}
