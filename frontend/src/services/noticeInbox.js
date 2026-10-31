import { demoApi } from './demoApi.js';

// 공유 소식 읽음 정보가 다른 시연 계정이나 기존 일정 알림과 충돌하지 않도록 구분한다.
export function sharedNoticeId(userId, noticeId) {
  return `shared:${encodeURIComponent(userId)}:${encodeURIComponent(noticeId)}`;
}

export async function loadSharedNotices(userId, { signal, request = demoApi } = {}) {
  if (!userId) return [];
  const result = await request('/notices', { userId, signal });
  if (!Array.isArray(result.items)) throw new Error('공유 소식 형식을 확인할 수 없어요. 다시 불러와 주세요.');
  const ids = new Set();
  return result.items.map(item => {
    if (!item?.notice || typeof item.notice.id !== 'string' || !item.notice.id || typeof item.notice.title !== 'string') {
      throw new Error('공유 소식 형식을 확인할 수 없어요. 다시 불러와 주세요.');
    }
    return item;
  }).filter(item => {
    if (ids.has(item.notice.id)) return false;
    ids.add(item.notice.id);
    return true;
  });
}
