export const SHARED_EVENT_CATEGORIES = ['결혼', '장례', '백일', '돌', '생일', '환갑', '칠순', '팔순'];

export function sharedReasonLabel(reason) {
  return {
    confirmed_colleague: '확인된 직장동료와 관련된 소식',
    direct_friend: '직접 연결된 친구가 공유한 소식',
    friend_of_friend: '친구의 친구가 공유한 소식',
  }[reason] || '공유된 소식';
}

export function sharedScopeLabel(scope) {
  return {
    private: '나만 보기',
    friends_only: '직접 친구',
    friends_and_friends_of_friends: '직접 친구와 친구의 친구',
  }[scope] || '공개 범위 미확인';
}

function validDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}

export function prepareSharedEvent(form) {
  const title = String(form.title || '').trim();
  if (!title) throw new Error('소식 제목을 입력해 주세요.');
  if (!validDate(form.start_date) || !validDate(form.end_date) || form.start_date > form.end_date) {
    throw new Error('시작일과 종료일을 확인해 주세요.');
  }
  if (form.audience_scope !== 'private' && !form.sharing_confirmed) {
    throw new Error('소식을 공유할 권한을 확인해 주세요.');
  }
  const role = form.related_role || null;
  return {
    category: form.category,
    title,
    start_date: form.start_date,
    end_date: form.end_date,
    region: String(form.region || '').trim() || null,
    venue: String(form.venue || '').trim() || null,
    audience_scope: form.audience_scope,
    sharing_authorization: form.audience_scope !== 'private' && form.sharing_confirmed ? 'confirmed' : 'unknown',
    direct_friend_attendance: form.audience_scope === 'private' ? 'unknown' : form.direct_friend_attendance,
    friend_of_friend_attendance: form.audience_scope === 'friends_and_friends_of_friends' ? form.friend_of_friend_attendance : 'unknown',
    publisher_name_visible: Boolean(form.publisher_name_visible),
    related_role: role,
    related_user_recommendation_allowed: Boolean(role && form.related_user_recommendation_allowed),
  };
}
