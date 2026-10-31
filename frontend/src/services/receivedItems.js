// 받은 일정 = 친구가 보낸 일정(friend) + 함께 아는 사람 소식(mutual)
// 출처는 두 가지: 마음결 친구가 공유한 일정(local) · 서버의 공유 부고 추천(server)
import { receivedShares, receiptOf } from './socialStore.js';

/** 서버 예시 데이터의 '가상' 접두어 등을 화면에서 정리한다. */
export const cleanText = value => String(value ?? '').replace(/가상\s*(주소:\s*)?/g, '').replace(/\s{2,}/g, ' ').trim();

const firstTime = value => (String(value || '').match(/(\d{1,2}):(\d{2})/) || []).slice(1, 3).map(part => part.padStart(2, '0')).join(':');

export function shareToItem({ share, kind, mutual }, { receipt, nameOf = name => name } = {}) {
  return {
    key: `share:${share.id}`, source: 'local', kind,
    title: share.event.title, type: share.event.type, date: share.event.date, time: share.event.time || '',
    location: share.event.location || '', message: share.message || '', memo: share.event.memo || '',
    senderName: share.ownerName || share.owner, senderUsername: share.owner,
    mutualNames: mutual.map(nameOf), mutualCount: mutual.length,
    person: { name: share.ownerName || share.owner, relation: kind === 'friend' ? '친구' : '지인', group: '마음결 친구', linkedUsername: share.owner },
    receivedAt: share.updatedAt || share.createdAt, receipt,
  };
}

export function noticeToItem(entry, { profileId = '', receipt } = {}) {
  const notice = entry.notice || {};
  const mourner = notice.mourner || {};
  const venue = [cleanText(notice.venue), cleanText(notice.room)].filter(Boolean).join(' · ');
  const relation = mourner.deceased_relation ? `${cleanText(mourner.name)}님 ${cleanText(mourner.deceased_relation)}상` : '';
  return {
    key: `notice:${profileId}:${notice.id}`, source: 'server', kind: entry.relation_type === 'direct_friend' ? 'friend' : 'mutual',
    title: cleanText(notice.title) || '부고', type: notice.category === '장례' ? '장례식' : cleanText(notice.category) || '기타',
    date: notice.start_date || '', endDate: notice.end_date || '', time: firstTime(notice.visiting_hours),
    location: venue || cleanText(notice.region), region: cleanText(notice.region),
    visitingHours: cleanText(notice.visiting_hours), message: relation,
    memo: [relation, notice.visiting_hours ? `조문 ${cleanText(notice.visiting_hours)}` : ''].filter(Boolean).join(' · '),
    senderName: cleanText(entry.publisher_name) || '함께 아는 친구', senderUsername: '',
    mutualNames: [], mutualCount: Number(entry.mutual_count || 0),
    person: mourner.name ? { name: cleanText(mourner.name), relation: '지인', group: cleanText(mourner.affiliation) } : { name: cleanText(entry.publisher_name) || '지인', relation: '지인', group: '' },
    receivedAt: notice.registered_at || '', receipt, raw: entry,
  };
}

/** 화면에 보여 줄 받은 일정 목록. 숨긴 항목은 제외하고, 달력 추가 여부를 함께 계산한다. */
export function buildReceivedItems({ social, me, notices = [], profileId = '', events = [], members = [] }) {
  const nameOf = username => members.find(member => String(member.username).toLowerCase() === username)?.name || username;
  const local = receivedShares(social, me).map(entry => shareToItem(entry, { receipt: receiptOf(social, me, `share:${entry.share.id}`), nameOf }));
  const server = notices.map(entry => {
    const item = noticeToItem(entry, { profileId });
    return { ...item, receipt: receiptOf(social, me, item.key) };
  });
  return [...local, ...server].map(item => {
    const linked = events.find(event => event.source?.key === item.key) || (item.receipt?.eventId && events.find(event => event.id === item.receipt.eventId));
    return { ...item, addedEventId: linked?.id || '', status: linked ? 'added' : item.receipt?.status === 'hidden' ? 'hidden' : 'new' };
  }).filter(item => item.status !== 'hidden')
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

/** 받은 일정을 내 달력 일정으로 바꾼다. */
export function itemToEvent(item, personId) {
  return {
    personId, title: item.title, type: item.type, date: item.date, time: item.time || '', location: item.location || '',
    memo: [item.message && item.source === 'local' ? `“${item.message}”` : '', item.memo !== item.message ? item.memo : ''].filter(Boolean).join(' · '),
    attendance: '', reminderDays: item.type === '장례식' ? 0 : 3,
    source: { key: item.key, kind: item.kind, from: item.senderName },
  };
}
