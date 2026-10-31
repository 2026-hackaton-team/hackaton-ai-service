import test from 'node:test';
import assert from 'node:assert/strict';
import { prepareSharedEvent, sharedReasonLabel, sharedScopeLabel } from './sharedEvents.js';

const form = {
  category: '결혼', title: ' 가상 결혼식 ', start_date: '2026-11-14', end_date: '2026-11-14',
  region: ' 서울 ', venue: '', audience_scope: 'friends_and_friends_of_friends', sharing_confirmed: true,
  direct_friend_attendance: 'allowed', friend_of_friend_attendance: 'allowed', publisher_name_visible: true,
  related_role: 'subject', related_user_recommendation_allowed: true,
};

test('공유 권한과 관련 인물 설정을 확인된 값으로 전달한다', () => {
  const result = prepareSharedEvent(form);
  assert.equal(result.title, '가상 결혼식');
  assert.equal(result.region, '서울');
  assert.equal(result.venue, null);
  assert.equal(result.sharing_authorization, 'confirmed');
  assert.equal(result.related_role, 'subject');
  assert.equal(result.related_user_recommendation_allowed, true);
  assert.equal(Object.hasOwn(result, 'publisher_user_id'), false);
});

test('비공개 소식은 이전 공유 선택과 관련 인물 확인을 물려받지 않는다', () => {
  const result = prepareSharedEvent({ ...form, audience_scope: 'private', related_role: '' });
  assert.equal(result.sharing_authorization, 'unknown');
  assert.equal(result.direct_friend_attendance, 'unknown');
  assert.equal(result.friend_of_friend_attendance, 'unknown');
  assert.equal(result.related_user_recommendation_allowed, false);
});

test('공유 확인 누락과 잘못된 날짜는 저장 요청 전에 거부한다', () => {
  assert.throws(() => prepareSharedEvent({ ...form, sharing_confirmed: false }), /공유할 권한/);
  assert.throws(() => prepareSharedEvent({ ...form, start_date: '2026-02-30' }), /시작일과 종료일/);
  assert.throws(() => prepareSharedEvent({ ...form, end_date: '2026-11-13' }), /시작일과 종료일/);
  assert.throws(() => prepareSharedEvent({ ...form, title: '  ' }), /제목/);
});

test('확인되지 않은 추천 이유나 공개 범위를 추측하지 않는다', () => {
  assert.equal(sharedReasonLabel('confirmed_colleague'), '확인된 직장동료와 관련된 소식');
  assert.equal(sharedReasonLabel('unknown'), '공유된 소식');
  assert.equal(sharedScopeLabel('private'), '나만 보기');
  assert.equal(sharedScopeLabel('unknown'), '공개 범위 미확인');
});
