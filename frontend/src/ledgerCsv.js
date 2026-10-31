export const CSV_HEADERS = ['기록ID', '인맥ID', '이름', '관계', '그룹', '행사ID', '행사유형', '날짜', '구분', '금액', '메모'];
export const RECORD_TYPES = ['결혼식', '돌잔치', '장례식', '생일', '기타'];
const aliases = { recordId:'기록ID', personId:'인맥ID', name:'이름', relation:'관계', group:'그룹', eventId:'행사ID', type:'행사유형', date:'날짜', direction:'구분', amount:'금액', memo:'메모', 경조사:'행사유형' };
const directions = { '보낸 마음':'보낸 마음', '받은 마음':'받은 마음', 보냄:'보낸 마음', 받음:'받은 마음', 지출:'보낸 마음', 수입:'받은 마음' };

export function parseCsv(text) {
  const source = String(text).replace(/^\uFEFF/, '');
  const rows = [];
  let cells = [], field = '', quoted = false, afterQuote = false, line = 1, rowLine = 1;
  const finishField = () => { cells.push(field); field = ''; afterQuote = false; };
  const finishRow = () => { finishField(); if (cells.some(cell => cell.trim())) rows.push({ cells, line: rowLine }); cells = []; };
  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (quoted) {
      if (ch === '"' && source[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') { quoted = false; afterQuote = true; }
      else { field += ch; if (ch === '\n') line++; }
    } else if (ch === ',') finishField();
    else if (ch === '\r' || ch === '\n') {
      finishRow(); if (ch === '\r' && source[i + 1] === '\n') i++;
      line++; rowLine = line;
    } else if (afterQuote && /[ \t]/.test(ch)) { /* Ignore whitespace after a quoted cell. */ }
    else if (afterQuote) throw new Error(`${line}행: 닫는 따옴표 뒤에 쉼표가 필요해요.`);
    else if (ch === '"') { if (field) throw new Error(`${line}행: 따옴표 형식을 확인해 주세요.`); quoted = true; }
    else field += ch;
  }
  if (quoted) throw new Error(`${rowLine}행: 닫히지 않은 따옴표가 있어요.`);
  if (cells.length || field || afterQuote) finishRow();
  return rows;
}

// Excel should treat formula-like names and memos as text; double leading apostrophes
// so the app's own CSV can be imported again without changing the original value.
const safeText = value => {
  const s = String(value ?? '');
  return /^'|^[\s\uFEFF]*[=+\-@]/.test(s) ? `'${s}` : s;
};
const restoreText = value => /^''|^'[\s\uFEFF]*[=+\-@]/.test(value) ? value.slice(1) : value;
const quote = value => `"${safeText(value).replaceAll('"', '""')}"`;

export function exportRecordsCsv(records, people) {
  const rows = records.map(record => {
    const person = people.find(item => item.id === record.personId);
    return [record.id || '', record.personId || '', person?.name || '', person?.relation || '', person?.group || '', record.eventId || '', record.type, record.date, record.direction, record.amount, record.memo || ''];
  });
  return '\uFEFF' + [CSV_HEADERS, ...rows].map(row => row.map(quote).join(',')).join('\r\n') + '\r\n';
}

export function csvTemplate(people = [], today = '2026-10-31') {
  const person = { ...(people[0] || { name:'홍길동', relation:'친구', group:'대학 동기' }), id:people[0]?.id || '' };
  return exportRecordsCsv([{ personId:person.id || '', type:'결혼식', date:today, direction:'보낸 마음', amount:100000, memo:'예시를 수정한 뒤 가져오세요' }], [person]);
}

export function decodeCsv(buffer) {
  const bytes = new Uint8Array(buffer);
  if (bytes[0] === 255 && bytes[1] === 254) return new TextDecoder('utf-16le', { fatal:true }).decode(bytes);
  if (bytes[0] === 254 && bytes[1] === 255) return new TextDecoder('utf-16be', { fatal:true }).decode(bytes);
  try { return new TextDecoder('utf-8', { fatal:true }).decode(bytes); }
  catch { return new TextDecoder('euc-kr', { fatal:true }).decode(bytes); }
}

function validDate(value) {
  const match = String(value).trim().match(/^(19\d{2}|20\d{2})[-./](\d{1,2})[-./](\d{1,2})$/);
  if (!match) return '';
  const [, y, m, d] = match;
  const date = new Date(+y, +m - 1, +d);
  return date.getFullYear() === +y && date.getMonth() === +m - 1 && date.getDate() === +d ? `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}` : '';
}
const identity = person => JSON.stringify([person.name, person.relation || '기타', person.group || '']);
const fingerprint = record => JSON.stringify([record.personId || record.personKey, record.type, record.date, record.direction, Number(record.amount), record.memo || '', record.eventId || '']);

export function prepareRecordImport(text, { people = [], events = [], records = [] } = {}) {
  const result = { rows:[], newPeople:[], errors:[], warnings:[], duplicateCount:0, totalCount:0 };
  let parsed;
  try { parsed = parseCsv(text); } catch (error) { result.errors.push(error.message); return result; }
  if (!parsed.length) { result.errors.push('CSV 파일이 비어 있어요.'); return result; }
  const headers = parsed[0].cells.map(cell => aliases[cell.trim()] || cell.trim());
  if (new Set(headers).size !== headers.length) { result.errors.push('같은 이름의 열이 두 번 있어요.'); return result; }
  const required = ['이름', '행사유형', '날짜', '구분', '금액'];
  const missing = required.filter(key => !headers.includes(key));
  if (missing.length) { result.errors.push(`필수 열이 없어요: ${missing.join(', ')}. 양식을 내려받아 확인해 주세요.`); return result; }
  const rawRows = parsed.slice(1);
  result.totalCount = rawRows.length;
  if (!rawRows.length) { result.errors.push('가져올 금액 기록이 없어요.'); return result; }
  if (rawRows.length > 5000) { result.errors.push('한 번에 최대 5,000건까지 가져올 수 있어요.'); return result; }
  const existingIds = new Set(records.map(record => record.id));
  const seenIds = new Map();
  const seenRecords = new Set(records.map(fingerprint));
  const stagedPeople = new Map();
  for (const row of rawRows) {
    const fail = message => result.errors.push(`${row.line}행: ${message}`);
    if (row.cells.length !== headers.length) { fail(`열 개수가 맞지 않아요. ${headers.length}개 열을 확인해 주세요.`); continue; }
    const entry = Object.fromEntries(headers.map((key,index) => [key, restoreText(row.cells[index]).trim()]));
    const id = entry['기록ID'] || '';
    if (existingIds.has(id)) { result.duplicateCount++; continue; }
    const name = entry['이름'];
    const relation = entry['관계'] || '';
    const group = entry['그룹'] || '';
    const type = entry['행사유형'];
    const date = validDate(entry['날짜']);
    const direction = directions[entry['구분']];
    const rawAmount = entry['금액'].replace(/원$/, '').trim();
    const amount = Number(rawAmount.replaceAll(',', ''));
    if (!name || name.length > 40) { fail('이름은 1~40자로 입력해 주세요.'); continue; }
    if (relation.length > 40) { fail('관계는 40자 이내로 입력해 주세요.'); continue; }
    if (group.length > 40) { fail('그룹은 40자 이내로 입력해 주세요.'); continue; }
    if (!RECORD_TYPES.includes(type)) { fail('행사유형은 결혼식·돌잔치·장례식·생일·기타 중 선택해 주세요.'); continue; }
    if (!date) { fail('날짜를 확인해 주세요. 예: 2026-10-31'); continue; }
    if (!direction) { fail('구분은 보낸 마음·받은 마음(또는 지출·수입)으로 입력해 주세요.'); continue; }
    if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(rawAmount) || !Number.isSafeInteger(amount) || amount < 1 || amount > 1000000000) { fail('금액은 1원~10억 원의 정수로 입력해 주세요.'); continue; }
    if ((entry['메모'] || '').length > 1000 || id.length > 128 || (entry['인맥ID'] || '').length > 128 || (entry['행사ID'] || '').length > 128) { fail('ID 또는 메모가 너무 길어요.'); continue; }
    let target = people.find(person => person.id === entry['인맥ID']);
    if (target && target.name !== name) { fail('인맥ID와 이름이 서로 달라요. 이름 또는 인맥ID를 확인해 주세요.'); continue; }
    if (!target) {
      const matches = people.filter(person => person.name === name && (!relation || person.relation === relation) && (!group || person.group === group));
      if (matches.length > 1) { fail(`${name}님이 여러 명이에요. 인맥ID 또는 관계·그룹으로 구분해 주세요.`); continue; }
      target = matches[0];
    }
    let personKey = target?.id;
    if (!personKey) {
      const person = { name, relation:relation || '기타', group };
      const key = identity(person);
      if (!stagedPeople.has(key)) stagedPeople.set(key, { ...person, key:`new:${stagedPeople.size}` });
      personKey = stagedPeople.get(key).key;
    }
    let eventId = entry['행사ID'] || '';
    if (eventId) {
      const event = events.find(item => item.id === eventId);
      if (event && (event.personId !== personKey || event.type !== type)) { fail('연결할 행사ID의 인맥 또는 행사유형이 달라요.'); continue; }
      if (!event) { result.warnings.push(`${row.line}행: 행사ID를 찾을 수 없어 일정 연결 없이 가져와요.`); eventId = ''; }
    }
    const record = { ...(id ? {id} : {}), personKey, eventId, type, date, direction, amount, memo:entry['메모'] || '' };
    const key = fingerprint(record);
    if (id && seenIds.has(id)) {
      if (seenIds.get(id) !== key) fail('같은 기록ID에 다른 내용이 있어요. 기록ID를 확인해 주세요.');
      else result.duplicateCount++;
      continue;
    }
    if (!id && seenRecords.has(key)) { result.duplicateCount++; continue; }
    if (id) seenIds.set(id, key);
    seenRecords.add(key);
    result.rows.push({ ...record, personName:target?.name || name, line:row.line });
  }
  const used = new Set(result.rows.map(row => row.personKey));
  result.newPeople = [...stagedPeople.values()].filter(person => used.has(person.key));
  return result;
}

export function materializeImport(plan, idFactory, existingRecords = []) {
  if (plan.errors.length) throw new Error('오류가 있는 CSV는 저장할 수 없어요.');
  const ids = new Map();
  const people = plan.newPeople.map(({key, ...person}) => {
    const id = idFactory(); ids.set(key, id);
    return { ...person, id, importance:'보통', lastMet:'', memo:'', interactions:[] };
  });
  const seen = new Set(existingRecords.map(record => record.id));
  const records = plan.rows.map(({personKey, personName, line, ...record}) => {
    const id = record.id || idFactory();
    if (seen.has(id)) throw new Error('이미 있는 기록ID가 포함되어 있어요. CSV를 다시 확인해 주세요.');
    seen.add(id);
    return { ...record, id, personId:ids.get(personKey) || personKey };
  });
  return {people, records};
}
