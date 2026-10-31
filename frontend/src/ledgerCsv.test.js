import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCsv, exportRecordsCsv, prepareRecordImport, materializeImport, csvTemplate, decodeCsv } from './ledgerCsv.js';

const people = [{id:'p1', name:'김도윤', relation:'친구', group:'대학 동기'}];
const record = {id:'r1', personId:'p1', eventId:'e1', type:'결혼식', date:'2026-10-31', direction:'보낸 마음', amount:100000, memo:'축하, 마음을 전해요'};
const events = [{id:'e1', personId:'p1', type:'결혼식'}];
const csv = (...lines) => ['이름,행사유형,날짜,구분,금액,메모', ...lines].join('\r\n');

test('CSV reader handles BOM, CRLF, embedded commas, quotes and newlines', () => {
  const rows = parseCsv('\uFEFF이름,메모\r\n김도윤,"첫 줄, \"\"축하\"\"\n다음 줄"\r\n\r\n');
  assert.deepEqual(rows[1].cells, ['김도윤','첫 줄, "축하"\n다음 줄']);
  assert.equal(rows.length, 2);
  assert.throws(() => parseCsv('이름,메모\n김도윤,"미완성'), /따옴표/);
  assert.throws(() => parseCsv('이름\n"이름"잘못'), /쉼표/);
});

test('export/import round trip preserves IDs, direction, quoted memo and formula-like text', () => {
  for (const memo of ['여러 줄\n"축하", 마음', '=1+1', '+SUM(A1)', '\t@formula', "'시작하는 메모"]) {
    const source = {...record, memo};
    const text = exportRecordsCsv([source], people);
    assert.ok(text.startsWith('\uFEFF'));
    const plan = prepareRecordImport(text, {people, events});
    assert.deepEqual(plan.errors, []);
    const restored = materializeImport(plan, () => 'unused');
    // Import follows the same surrounding-whitespace normalization as manual input.
    assert.deepEqual(restored.records, [{...source, memo:memo.trim()}]);
    if (/^[=+@]/.test(memo)) assert.ok(text.includes(`"'${memo}"`));
    assert.equal(source.memo, memo);
  }
});

test('exported IDs and identical ID-less records are excluded without overwriting', () => {
  const changed = {...record, amount:50000};
  const byId = prepareRecordImport(exportRecordsCsv([changed], people), {people, events, records:[record]});
  assert.equal(byId.duplicateCount, 1);
  assert.equal(byId.rows.length, 0);
  const noId = {...record, id:''};
  const byContent = prepareRecordImport(exportRecordsCsv([noId], people), {people, events, records:[record]});
  assert.equal(byContent.duplicateCount, 1);
  assert.equal(record.amount, 100000);
});

test('invalid financial rows block the entire import instead of silently saving partial data', () => {
  const plan = prepareRecordImport(csv('김도윤,결혼식,2026-10-31,지출,50000,정상', '새인맥,결혼식,2026-02-30,수입,100000,잘못된 날짜'), {people});
  assert.equal(plan.rows.length, 1);
  assert.ok(plan.errors[0].includes('3행'));
  assert.throws(() => materializeImport(plan, () => 'id'), /오류/);
});

test('new contacts are staged once and correctly linked only on confirmation', () => {
  const plan = prepareRecordImport(csv('이새봄,생일,2026-10-30,받음,50000,생일', '이새봄,돌잔치,2026-10-31,보냄,100000,첫돌'), {people});
  assert.equal(plan.newPeople.length, 1);
  let i=0;
  const added = materializeImport(plan, () => `id-${++i}`);
  assert.equal(added.people[0].name, '이새봄');
  assert.equal(added.records[0].personId, added.people[0].id);
  assert.equal(added.records[1].personId, added.people[0].id);
  assert.equal(people.length, 1);
  assert.equal(added.records[0].direction, '받은 마음');
});

test('ambiguous names need an ID or relationship/group disambiguation', () => {
  const names = [...people, {id:'p2', name:'김도윤', relation:'직장동료', group:'회사'}];
  const ambiguous = prepareRecordImport(csv('김도윤,결혼식,2026-10-31,지출,50000,'), {people:names});
  assert.ok(ambiguous.errors[0].includes('여러 명'));
  const clear = prepareRecordImport('이름,관계,그룹,행사유형,날짜,구분,금액\n김도윤,직장동료,회사,결혼식,2026-10-31,지출,50000', {people:names});
  assert.equal(clear.rows[0].personKey, 'p2');
  const mismatch = exportRecordsCsv([record], people).replace('김도윤', '다른사람');
  assert.ok(prepareRecordImport(mismatch, {people, events}).errors[0].includes('인맥ID와 이름'));
});

test('event links are validated and unknown external event IDs are left unlinked', () => {
  const bad = prepareRecordImport(exportRecordsCsv([record], people), {people, events:[{id:'e1',personId:'other',type:'결혼식'}]});
  assert.ok(bad.errors[0].includes('행사ID'));
  const external = prepareRecordImport(exportRecordsCsv([record], people), {people});
  assert.deepEqual(external.errors, []);
  assert.equal(external.warnings.length, 1);
  assert.equal(external.rows[0].eventId, '');
});

test('conflicting duplicate IDs are rejected, distinct IDs may represent distinct transactions', () => {
  const conflict = prepareRecordImport(exportRecordsCsv([record,{...record,amount:50000}], people), {people, events});
  assert.ok(conflict.errors[0].includes('같은 기록ID'));
  const distinct = prepareRecordImport(exportRecordsCsv([record,{...record,id:'r2'}], people), {people,events});
  assert.equal(distinct.rows.length, 2);
  assert.throws(() => materializeImport(distinct, () => 'id', [record]), /이미 있는 기록ID/);
});

test('CSV validates dates, amounts, required headers and duplicate header aliases', () => {
  for (const amount of ['0','-100','1.5','5e4','1000000001','"10,00"']) {
    assert.ok(prepareRecordImport(csv(`김도윤,결혼식,2026-10-31,보냄,${amount},`),{people}).errors.length);
  }
  assert.ok(prepareRecordImport('이름,금액\n김도윤,100000').errors[0].includes('필수 열'));
  assert.ok(prepareRecordImport('이름,name\n김도윤,김도윤').errors[0].includes('두 번'));
  const formatted = prepareRecordImport('amount,direction,date,type,name\n"100,000원",수입,2026.10.31,생일,김도윤',{people});
  assert.equal(formatted.rows[0].amount,100000);
  assert.equal(formatted.rows[0].date,'2026-10-31');
});

test('a template also works with no existing people and UTF-16 CSV can be decoded', () => {
  const plan = prepareRecordImport(csvTemplate([], '2026-10-31'));
  assert.deepEqual(plan.errors, []);
  assert.equal(plan.newPeople[0].name,'홍길동');
  const text='이름,금액\r\n김도윤,100000';
  const bytes=new Uint8Array(2+text.length*2); const view=new DataView(bytes.buffer);
  view.setUint16(0,0xfeff,true);
  for(let i=0;i<text.length;i++) view.setUint16(2+i*2,text.charCodeAt(i),true);
  assert.equal(decodeCsv(bytes.buffer),text);
});

test('custom relationships survive CSV round trips for existing and new people', () => {
  const customPeople = [{...people[0], relation:'동호회 선배'}];
  const exported = exportRecordsCsv([record], customPeople);
  const existing = prepareRecordImport(exported, {people:customPeople, events});
  assert.deepEqual(existing.errors, []);
  assert.equal(existing.rows[0].personKey, 'p1');
  assert.equal(existing.newPeople.length, 0);
  const fresh = prepareRecordImport(exported);
  assert.deepEqual(fresh.errors, []);
  assert.equal(fresh.newPeople[0].relation, '동호회 선배');
  assert.equal(materializeImport(fresh, () => 'new-id').people[0].relation, '동호회 선배');
  const tooLong = exported.replace('동호회 선배', '관'.repeat(41));
  assert.ok(prepareRecordImport(tooLong).errors[0].includes('40자'));
});
