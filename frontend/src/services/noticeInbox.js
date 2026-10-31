import { demoApi } from './demoApi.js';

// 공유 소식 읽음 정보가 다른 시연 계정이나 기존 일정 알림과 충돌하지 않도록 구분한다.
export function sharedNoticeId(userId, noticeId) {
  return `shared:${encodeURIComponent(userId)}:${encodeURIComponent(noticeId)}`;
}

export async function loadSharedNotices(userId, { signal, request = demoApi } = {}) {
  if (!userId) return [];
  const [legacy, shared] = await Promise.all([
    request('/notices', { userId, signal }),
    request('/shared-events/recommendations', { userId, signal }),
  ]);
  if (!Array.isArray(legacy.items) || !Array.isArray(shared.items)) {
    throw new Error('공유 소식 형식을 확인할 수 없어요. 다시 불러와 주세요.');
  }
  const sharedItems = shared.items.map(item => {
    if (typeof item?.id !== 'string' || !item.id || typeof item.title !== 'string' || typeof item.reason_code !== 'string') {
      throw new Error('공유 소식 형식을 확인할 수 없어요. 다시 불러와 주세요.');
    }
    return {
      relation_type: item.reason_code, publisher_name: item.publisher_name,
      notice: {
        id: item.id, category: item.category, title: item.title,
        start_date: item.start_date, end_date: item.end_date, region: item.region,
      },
    };
  });
  const ids = new Set();
  return [...legacy.items, ...sharedItems].map(item => {
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
