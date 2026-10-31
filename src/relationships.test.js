import test from 'node:test';
import assert from 'node:assert/strict';
import { relationDraft, resolveRelation, matchesRelation, normalizeImportance, importanceRank, normalizePerson } from './relationships.js';

test('custom relationship drafts round trip and an empty other label uses 기타', () => {
  assert.deepEqual(relationDraft(' 동호회 선배 '), { relation:'기타', customRelation:'동호회 선배' });
  assert.equal(resolveRelation('기타', ' 동호회 선배 '), '동호회 선배');
  assert.equal(resolveRelation('기타', '  '), '기타');
  assert.equal(resolveRelation('친구', '지워지지 않은 입력'), '친구');
  assert.deepEqual(relationDraft('기타'), { relation:'기타', customRelation:'' });
  assert.equal(matchesRelation('동호회 선배', '기타'), true);
  assert.equal(matchesRelation('가족', '기타'), false);
});

test('three importance levels preserve legacy very-important spelling and ordering', () => {
  assert.equal(normalizeImportance('매우중요'), '매우 중요');
  assert.equal(normalizeImportance('매우 중요'), '매우 중요');
  assert.equal(normalizeImportance(undefined), '보통');
  assert.ok(importanceRank('매우 중요') > importanceRank('중요'));
  assert.ok(importanceRank('중요') > importanceRank('보통'));
  const original = {id:'p1', name:'이웃', relation:' 동호회 선배 ', importance:'매우중요', memo:'보존', interactions:[{id:'i1'}]};
  assert.deepEqual(normalizePerson(original), {...original, relation:'동호회 선배', importance:'매우 중요'});
  assert.equal(original.relation, ' 동호회 선배 ');
  assert.equal(normalizePerson({}).relation, '기타');
});
