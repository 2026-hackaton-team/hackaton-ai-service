// 친구 추천 전용 점수. 받은 경조사 순서와 금액 추천에는 적용하지 않는다.
import { normalizeImportance } from '../relationships.js';
import { searchMembers } from './socialStore.js';

export const FRIEND_RECOMMENDATION_WEIGHTS = Object.freeze({
  threshold: 70, // 70점 미만 제외, 70점부터 자동 추천
  importance: Object.freeze({ '매우 중요': 30, '중요': 15, '보통': 0 }),
  relation: Object.freeze({ '가족': 50, '친구': 20, '기타': 0 }),
  otherRelation: 10,
  mutualFriend: 10,
  mutualBonusCap: 30,
  special: 20,
});

const usernameKey = value => String(value || '').trim().toLowerCase();

function connectionScore(username, person) {
  // 아직 내 인맥과 연결하지 않았어도, 수락된 공통 친구라는 관계는 확인돼 있다.
  const relation = String(person?.relation || '친구').trim();
  const importance = normalizeImportance(person?.importance);
  const weights = FRIEND_RECOMMENDATION_WEIGHTS;
  const relationScore = Object.hasOwn(weights.relation, relation) ? weights.relation[relation] : weights.otherRelation;
  const importanceScore = weights.importance[importance];
  const specialScore = person?.special === true ? weights.special : 0;
  return { username, relation, importance, relationScore, importanceScore, specialScore,
    score: relationScore + importanceScore + specialScore };
}

/** 내 계정의 인맥 기록만 사용하며, 이름이 같다는 이유로 회원을 자동 연결하지 않는다. */
export function scoreFriendRecommendation(mutualUsernames, people = []) {
  const mutual = [...new Set(mutualUsernames.map(usernameKey).filter(Boolean))];
  const connections = mutual.map(username => {
    const linked = people.filter(person => usernameKey(person.linkedUsername) === username);
    // 같은 회원에 중복 연결된 인맥은 가장 높은 한 건만 반영한다.
    return linked.length
      ? linked.map(person => connectionScore(username, person)).sort((a, b) => b.score - a.score)[0]
      : connectionScore(username);
  }).sort((a, b) => b.score - a.score || a.username.localeCompare(b.username));
  const mutualBonus = Math.min(mutual.length * FRIEND_RECOMMENDATION_WEIGHTS.mutualFriend,
    FRIEND_RECOMMENDATION_WEIGHTS.mutualBonusCap);
  return { score: connections.reduce((sum, item) => sum + item.score, 0) + mutualBonus,
    mutualBonus, connections };
}

/** 가입된 회원·수락된 친구 관계만 사용한다. 기존 친구, 진행 중인 요청, 비공개 회원은 추천에서 제외한다. */
export function recommendFriends(state, accounts, me, people = []) {
  if (!usernameKey(me)) return [];
  const registered = new Set(accounts.map(account => usernameKey(account.username)).filter(Boolean));
  return searchMembers(state, accounts, me).filter(member => member.status === 'none').map(member => {
    const mutual = [...new Set(member.mutual.map(usernameKey))].filter(username => registered.has(username));
    return { ...member, mutual, recommendation: scoreFriendRecommendation(mutual, people) };
  }).filter(member => member.mutual.length > 0 && member.recommendation.score >= FRIEND_RECOMMENDATION_WEIGHTS.threshold)
    .sort((a, b) => b.recommendation.score - a.recommendation.score
      || b.mutual.length - a.mutual.length || a.name.localeCompare(b.name, 'ko'));
}
