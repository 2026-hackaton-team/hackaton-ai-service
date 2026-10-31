import test from 'node:test';
import assert from 'node:assert/strict';
import { daysBetween, priorityFor, priorityFromServer } from './relationshipPriority.js';

test('priority score matches the server rule and explains itself', () => {
  assert.deepEqual(priorityFor(null, 30), { score: 0, reasons: [] });
  assert.deepEqual(priorityFor({ importance: '매우 중요', special: true, relation: '가족' }, 5), { score: 60, reasons: ['‘매우 중요’로 기록한 가족', '특별히 챙길 사람', '5일 남음'] });
  assert.equal(priorityFor({ importance: '중요' }, 0).score, 25);
  assert.equal(daysBetween('2026-11-07', '2026-10-31'), 7);
});

test('server day bonus is recalculated against today', () => {
  const entry = { priority_score: 60, priority_reasons: ['‘매우 중요’로 기록한 사촌', '특별히 챙길 사람', '6일 남음'] };
  assert.deepEqual(priorityFromServer(entry, 20), { score: 50, reasons: ['‘매우 중요’로 기록한 사촌', '특별히 챙길 사람'] });
  assert.deepEqual(priorityFromServer({ priority_score: 0, priority_reasons: [] }, 3), { score: 10, reasons: ['3일 남음'] });
});
