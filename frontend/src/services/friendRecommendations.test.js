import test from 'node:test';
import assert from 'node:assert/strict';
import { recommendFriends, scoreFriendRecommendation } from './friendRecommendations.js';
import { normalizeSocial, searchMembers } from './socialStore.js';

const accounts = (...names) => names.map(username => ({ username, name: username, visibility: '전체 공개' }));
const graph = (...pairs) => normalizeSocial({ friendships: pairs.map(([from, to, status = 'accepted'], index) => ({ id: String(index), from, to, status })) });
const person = (linkedUsername, relation = '친구', importance = '보통', special = false) => ({ linkedUsername, relation, importance, special });


test('an important mutual friend recommends an unfamiliar registered member', () => {
  const state = graph(['me', 'bridge'], ['bridge', 'hong'], ['me', 'ordinary'], ['ordinary', 'low']);
  const result = recommendFriends(state, accounts('me', 'bridge', 'hong', 'ordinary', 'low'), 'me', [person('bridge', '친구', '매우 중요', true)]);
  assert.deepEqual(result.map(member => member.username), ['hong']);
  assert.equal(result[0].recommendation.score, 80);
  assert.equal(result[0].recommendation.connections[0].username, 'bridge');
});

test('relation weights follow the requested family, friend, other and custom categories', () => {
  for (const [relation, expected] of [['가족', 60], ['친구', 30], ['직장동료', 20], ['거래처', 20], ['친척', 20], ['선배', 20], ['기타', 10]]) {
    assert.equal(scoreFriendRecommendation(['bridge'], [person('bridge', relation)]).score, expected, relation);
  }
  assert.equal(scoreFriendRecommendation(['bridge'], [person('bridge', '친구', '중요')]).score, 45);
});

test('70 points is included and scores below 70 are excluded', () => {
  const state = graph(['me', 'a'], ['me', 'b'], ['a', 'hong'], ['b', 'hong']);
  const members = accounts('me', 'a', 'b', 'hong');
  const below = [person('a', '친구', '중요'), person('b', '직장동료')];
  assert.equal(scoreFriendRecommendation(['a', 'b'], below).score, 65);
  assert.deepEqual(recommendFriends(state, members, 'me', below), []);
  const boundary = [person('a', '친구', '보통', true), person('b', '직장동료')];
  assert.equal(scoreFriendRecommendation(['a', 'b'], boundary).score, 70);
  assert.equal(recommendFriends(state, members, 'me', boundary)[0].recommendation.score, 70);
});

test('recommendations are sorted by score and then mutual count', () => {
  const state = graph(['me', 'a'], ['me', 'b'], ['me', 'family'], ['a', 'multi'], ['b', 'multi'], ['family', 'single']);
  const members = accounts('me', 'a', 'b', 'family', 'multi', 'single');
  const result = recommendFriends(state, members, 'me', [person('a', '친구', '매우 중요'), person('family', '가족', '중요')]);
  assert.deepEqual(result.map(member => [member.username, member.recommendation.score]), [['multi', 90], ['single', 75]]);
  const tied = recommendFriends(state, members, 'me', [person('a', '친구', '매우 중요'), person('family', '가족', '매우 중요')]);
  assert.deepEqual(tied.map(member => [member.username, member.recommendation.score]), [['multi', 90], ['single', 90]]);
});

test('only accepted mutual friendships count, never unrelated highly rated contacts', () => {
  const state = graph(['me', 'bridge', 'pending'], ['bridge', 'hong']);
  const members = accounts('me', 'bridge', 'hong');
  assert.deepEqual(recommendFriends(state, members, 'me', [person('bridge', '가족', '매우 중요')]), []);
  const accepted = graph(['me', 'bridge'], ['bridge', 'hong']);
  assert.deepEqual(recommendFriends(accepted, members, 'me', [person('hong', '가족', '매우 중요', true)]), []);
});

test('existing friends and both directions of pending requests stay outside recommendations', () => {
  const state = graph(['me', 'bridge'], ['bridge', 'friend'], ['me', 'friend'], ['bridge', 'sent'], ['me', 'sent', 'pending'], ['bridge', 'incoming'], ['incoming', 'me', 'pending']);
  assert.deepEqual(recommendFriends(state, accounts('me', 'bridge', 'friend', 'sent', 'incoming'), 'me', [person('bridge', '가족', '매우 중요')]), []);
});

test('private members are not recommended but exact username search still works', () => {
  const state = graph(['me', 'bridge'], ['bridge', 'hidden']);
  const members = [...accounts('me', 'bridge'), { username: 'hidden', name: '비공개', visibility: '비공개' }];
  assert.deepEqual(recommendFriends(state, members, 'me', [person('bridge', '가족', '매우 중요')]), []);
  assert.equal(searchMembers(state, members, 'me', 'hidden')[0].username, 'hidden');
});

test('both candidate and mutual friends must be registered members', () => {
  const state = graph(['me', 'ghost'], ['ghost', 'hong']);
  assert.deepEqual(recommendFriends(state, accounts('me', 'hong'), 'me', [person('ghost', '가족', '매우 중요')]), []);
  const known = graph(['me', 'bridge'], ['bridge', 'missing']);
  assert.deepEqual(recommendFriends(known, accounts('me', 'bridge'), 'me', [person('bridge', '가족', '매우 중요')]), []);
});

test('duplicate friendship edges and duplicate linked contacts cannot multiply the score', () => {
  const state = graph(['ME', 'Bridge'], ['bridge', 'me'], ['bridge', 'hong']);
  const contacts = [person('BRIDGE', '친구', '매우 중요', true), person('bridge', '친구', '중요')];
  const result = recommendFriends(state, accounts('me', 'bridge', 'hong'), 'ME', contacts);
  assert.deepEqual(result[0].mutual, ['bridge']);
  assert.equal(result[0].recommendation.score, 80);
});

test('same names never inherit importance without an explicit member link', () => {
  const state = graph(['me', 'bridge'], ['bridge', 'hong']);
  const contacts = [{ name: 'bridge', relation: '가족', importance: '매우 중요', special: true }];
  assert.deepEqual(recommendFriends(state, accounts('me', 'bridge', 'hong'), 'me', contacts), []);
});

test('mutual count bonus is capped and unlinked accepted friends retain the friend baseline', () => {
  const result = scoreFriendRecommendation(['a', 'b', 'c', 'd']);
  assert.equal(result.mutualBonus, 30);
  assert.equal(result.score, 110);
  assert.equal(scoreFriendRecommendation([]).score, 0);
  assert.deepEqual(recommendFriends(graph(['a', 'b']), accounts('a', 'b'), ''), []);
});

test('direct member search is retained below the recommendation threshold', () => {
  const state = graph(['me', 'bridge'], ['bridge', 'low']);
  const members = accounts('me', 'bridge', 'low');
  assert.deepEqual(recommendFriends(state, members, 'me'), []);
  assert.deepEqual(searchMembers(state, members, 'me', 'low').map(member => member.username), ['low']);
});
