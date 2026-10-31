import { useState } from 'react';
import { Icon, Modal, EmptyState } from './ui.jsx';
import './feature-preview.css';

// 실제 회원·요청·수신 일정과 분리된 화면 설명용 가상 자료다. 저장하거나 API에 전송하지 않는다.
const suggestedMembers = [
  { id: 'preview-member-1', name: '김서연', organization: '가온디자인', occupation: '디자이너', role: '브랜드 디자인', mutualCount: 2 },
  { id: 'preview-member-2', name: '박지훈', organization: '새봄연구소', occupation: '연구원', role: '서비스 연구', mutualCount: 1 },
  { id: 'preview-member-3', name: '이서현', organization: '다정한책방', occupation: '자영업', role: '책방 운영', mutualCount: 3 },
];
const incomingRequests = [
  { id: 'preview-request-1', name: '정다은', organization: '작은숲모임', occupation: '기획자', role: '행사 기획', mutualCount: 2 },
  { id: 'preview-request-2', name: '한도윤', organization: '가온디자인', occupation: '개발자', role: '웹 개발', mutualCount: 1 },
];

export function SectionTabs({ tabs, value, onChange, prefix, label }) {
  function move(event, index) {
    const offsets = { ArrowRight: 1, ArrowLeft: -1 };
    let next;
    if (event.key in offsets) next = (index + offsets[event.key] + tabs.length) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    onChange(tabs[next].id);
    document.getElementById(`${prefix}-${tabs[next].id}-tab`)?.focus();
  }
  return <div className="feature-tabs" role="tablist" aria-label={label}>
    {tabs.map((item, index) => <button type="button" role="tab" key={item.id}
      id={`${prefix}-${item.id}-tab`} aria-controls={`${prefix}-${item.id}-panel`}
      aria-selected={value === item.id} tabIndex={value === item.id ? 0 : -1}
      onKeyDown={event => move(event, index)} onClick={() => onChange(item.id)}>
      <Icon name={item.icon} size={17} />{item.label}
    </button>)}
  </div>;
}

function PreviewNotice({ children }) {
  return <div className="feature-preview-notice" role="note"><Icon name="Info" size={19} /><div><strong>화면 미리보기</strong><p>{children}</p></div></div>;
}

export function FriendPreview({ kind }) {
  const isRequests = kind === 'requests';
  const [showExamples, setShowExamples] = useState(true);
  const [query, setQuery] = useState('');
  const [profile, setProfile] = useState(null);
  const source = isRequests ? incomingRequests : suggestedMembers;
  const members = source.filter(person => `${person.name} ${person.organization} ${person.role}`.includes(query.trim()));
  return <div className="feature-preview-panel">
    <PreviewNotice>{isRequests ? '아래는 받은 요청의 가상 예시예요. 실제 요청 수신과 수락·거절은 아직 연결되지 않았어요.' : '아래는 친구의 친구 추천을 보여 주는 가상 예시예요. 실제 회원 검색과 친구 요청은 아직 연결되지 않았어요.'}</PreviewNotice>
    <div className="feature-section-heading"><div><h2>{isRequests ? '새로운 인연의 시작' : '함께 아는 인연에서 시작해요'}</h2><p>{isRequests ? '나에게 연결을 요청한 사람을 확인하고 결정할 수 있어요.' : '공통 친구가 있는 사람을 살펴보고 새로운 인연을 이어가세요.'}</p></div>
      <button type="button" className="button button-secondary" aria-pressed={showExamples} onClick={() => setShowExamples(value => !value)}>{showExamples ? '가상 예시 숨기기' : '가상 예시 보기'}</button>
    </div>
    {showExamples && <label className="pl-search feature-search"><Icon name="Search" size={18} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="가상 예시의 이름·소속으로 검색" aria-label={isRequests ? '받은 요청 예시 검색' : '친구 예시 검색'} />{query && <button type="button" aria-label="예시 검색 지우기" onClick={() => setQuery('')}><Icon name="X" size={16} /></button>}</label>}
    {showExamples && members.length > 0 ? <div className="feature-member-grid">
      {members.map(person => <article className="card feature-member-card" key={person.id}>
        <div className="feature-member-top"><span className="avatar">{person.name.slice(0, 1)}</span><div><h3>{person.name}</h3><p>{person.occupation} · {person.organization}</p></div><span className="feature-example-tag">가상 예시</span></div>
        <p className="feature-mutual"><Icon name="UsersRound" size={17} />공통 친구 {person.mutualCount}명</p>
        <p className="feature-member-description">{isRequests ? '이 회원이 나에게 친구 연결을 요청했어요.' : '친구와 연결된 또 다른 인연이에요.'}</p>
        <div className="feature-member-actions"><button type="button" className="button button-secondary" onClick={() => setProfile(person)}>프로필 보기</button>
          {isRequests ? <><button type="button" className="button button-secondary" disabled>거절</button><button type="button" className="button button-primary" disabled>수락</button></> : <button type="button" className="button button-primary" disabled><Icon name="UserPlus" size={16} />친구 요청</button>}
        </div><p className="feature-pending-note">{isRequests ? '수락·거절 기능 준비 중' : '친구 요청 기능 준비 중'}</p>
      </article>)}
    </div> : <div className="card feature-empty"><EmptyState icon={isRequests ? 'Mail' : 'UsersRound'} title={showExamples ? '검색에 맞는 예시가 없어요' : isRequests ? '받은 요청함을 준비하고 있어요' : '친구 추천을 준비하고 있어요'} description={showExamples ? '다른 이름으로 검색하거나 검색어를 지워 보세요.' : '가상 예시를 열면 앞으로 사용할 화면을 미리 살펴볼 수 있어요.'} /></div>}
    {profile && <Modal title={`${profile.name}님의 프로필 예시`} subtitle="실제 회원이 아닌 화면 설명용 가상 프로필입니다." onClose={() => setProfile(null)}>
      <dl className="feature-detail-list"><div><dt>이름</dt><dd>{profile.name}</dd></div><div><dt>직업</dt><dd>{profile.occupation}</dd></div><div><dt>기관</dt><dd>{profile.organization}</dd></div><div><dt>직무</dt><dd>{profile.role}</dd></div><div><dt>추천 이유</dt><dd>공통 친구 {profile.mutualCount}명</dd></div></dl>
      <p className="feature-pending-note">실제 연결된 회원이 아니며, 친구 요청은 전송되지 않아요.</p>
    </Modal>}
  </div>;
}

function futureDay(today, offset) {
  const value = new Date(`${today}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + offset);
  return value.toISOString().slice(0, 10).replaceAll('-', '.');
}

export function ReceivedScheduleDialog({ today, onClose }) {
  const [showExamples, setShowExamples] = useState(false);
  const [selected, setSelected] = useState(null);
  const samples = [
    { id: 'preview-invitation-1', sender: '김서연', title: '김서연·한도윤의 결혼식', type: '결혼식', date: futureDay(today, 14), time: '오후 1시', location: '가온 웨딩홀 2층', message: '소중한 날에 함께해 주시면 기쁘겠습니다.' },
    { id: 'preview-invitation-2', sender: '정다은', title: '정다은님의 생일 모임', type: '생일', date: futureDay(today, 21), time: '오후 6시', location: '작은숲 모임 공간', message: '오랜만에 함께 모여 안부를 나누어요.' },
  ];
  return <Modal title="받은 일정" subtitle="다른 사람이 보내 준 경조사를 한곳에서 확인해요." onClose={onClose} wide>
    <div className="feature-preview-panel"><PreviewNotice>일정 수신 기능을 준비하고 있어요. 아래 가상 예시는 실제로 발송되거나 내 달력에 저장된 일정이 아니에요.</PreviewNotice>
      {selected ? <>
        <button type="button" className="text-button feature-back" onClick={() => setSelected(null)}><Icon name="ArrowLeft" size={17} />받은 일정 목록</button>
        <div className="feature-invitation-detail"><span className="feature-example-tag">가상 수신 예시</span><h3>{selected.title}</h3><p>{selected.message}</p>
          <dl className="feature-detail-list"><div><dt>보낸 사람</dt><dd>{selected.sender}</dd></div><div><dt>행사 유형</dt><dd>{selected.type}</dd></div><div><dt>일시</dt><dd>{selected.date} · {selected.time}</dd></div><div><dt>장소</dt><dd>{selected.location}</dd></div></dl>
          <button type="button" className="button button-primary" disabled><Icon name="CalendarPlus" size={17} />내 일정에 추가</button><p className="feature-pending-note">받은 일정 저장 기능 준비 중</p>
        </div>
      </> : <>
        <div className="feature-section-heading"><div><h3>나에게 전해진 소중한 날</h3><p>직접 등록한 일정, 공유 부고 추천과 구분해서 확인할 공간이에요.</p></div><button type="button" className="button button-secondary" aria-pressed={showExamples} onClick={() => setShowExamples(value => !value)}>{showExamples ? '가상 예시 숨기기' : '가상 일정 미리보기'}</button></div>
        {showExamples ? <div className="feature-invitation-list">{samples.map(item => <article className="feature-invitation-card" key={item.id}><span className="feature-invitation-icon"><Icon name={item.type === '결혼식' ? 'Heart' : 'Cake'} size={23} /></span><div><span className="feature-example-tag">가상 수신 예시</span><h3>{item.title}</h3><p>{item.sender}님이 보낸 일정 · {item.date} · {item.time}</p><p>{item.location}</p></div><button type="button" className="button button-secondary" onClick={() => setSelected(item)} aria-label={`${item.title} 예시 상세 보기`}>상세 보기</button></article>)}</div> : <div className="feature-empty"><EmptyState icon="Mail" title="받은 일정을 모아볼 공간이에요" description="앞으로 지인이 보낸 초대와 경조사 소식을 이곳에서 확인할 수 있어요. 가상 일정으로 화면을 미리 살펴보세요." /></div>}
      </>}
    </div>
  </Modal>;
}
