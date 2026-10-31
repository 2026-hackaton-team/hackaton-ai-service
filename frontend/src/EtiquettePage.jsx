import { useState } from 'react';
import { Icon } from './ui.jsx';
import './etiquette.css';

const guides = [
  {id:'wedding',title:'결혼식',subtitle:'두 사람의 시작을 축하하는 자리',icon:'Heart',tips:[['가기 전에','참석 여부를 미리 전하고, 초대장에 적힌 시간과 장소를 확인해 여유 있게 도착하세요.'],['복장과 현장','단정하게 입고, 신랑·신부보다 눈에 띄는 복장이나 과한 흰색 예복은 피하는 편이 좋아요. 예식 중 이동·통화는 삼가고 사진은 진행 안내에 맞춰 촬영하세요.'],['축하 한마디','“결혼을 진심으로 축하해요. 두 분의 앞날을 응원합니다.”처럼 두 사람을 함께 축하해 보세요.']],avoid:'외모·결혼 비용·출산 계획처럼 사적인 질문은 삼가세요.'},
  {id:'funeral',title:'장례식 · 조문',subtitle:'유족의 마음과 종교를 먼저 살펴요',icon:'Flower2',tips:[['가기 전에','빈소와 조문 가능한 시간을 확인하고, 어두운 계열의 단정한 옷을 준비하세요.'],['빈소에서','조용히 인사한 뒤 분향·헌화·절·묵념은 유족의 종교와 현장 안내를 따르세요. 익숙하지 않으면 장례식장 직원에게 물어봐도 괜찮아요.'],['위로 한마디','“삼가 조의를 표합니다.”처럼 짧고 정중하게 마음을 전하세요. 긴 설명보다 조용히 곁을 지키는 배려가 도움이 될 수 있어요.']],avoid:'사망 경위를 캐묻거나 슬픔을 비교하지 마세요. 큰 소리·건배·동의 없는 빈소 촬영은 삼가세요.'},
  {id:'elders',title:'어른 생신 · 장수 축하',subtitle:'환갑·회갑 · 칠순·고희 · 팔순을 함께 안내해요',icon:'Gift',tips:[['가기 전에','잔치 날짜와 형식을 가족에게 확인하세요. 만 나이·음력 여부 등은 가정마다 달라 행사 날짜를 임의로 계산해 단정하지 않는 편이 좋아요.'],['축하하는 자리','어른께 먼저 인사하고 가족의 식사·사진 촬영·축하 순서에 맞춰 참여하세요. 선물과 술 권하기는 당사자의 취향과 상황을 존중하세요.'],['축하 한마디','“생신을 진심으로 축하드립니다. 늘 건강하고 행복하시길 바랍니다.”처럼 감사와 축하를 전하세요.']],avoid:'나이·건강·재산을 소재로 한 농담이나 부담스러운 장수 표현은 상대의 마음을 살펴 사용하세요.'},
  {id:'baby',title:'아기 축하 자리',subtitle:'돌잔치 · 백일을 함께 안내해요',icon:'Cake',tips:[['가기 전에','참석 인원과 시간을 부모에게 알려 준비를 돕고, 선물을 고민한다면 필요한 물건을 먼저 물어보세요.'],['현장에서','아기를 안거나 만지기 전에는 부모에게 물어보세요. 돌잡이·사진 촬영 등은 진행 순서를 따르고 아기의 휴식 시간을 배려하세요.'],['축하 한마디','“첫 생일(또는 백일)을 축하해요. 아기와 온 가족의 행복을 응원합니다.”처럼 아기와 가족을 함께 축하해 보세요.']],avoid:'사진을 SNS에 올리기 전 보호자에게 확인하고, 성장·외모를 다른 아이와 비교하지 마세요.'},
];

export default function EtiquettePage() {
  const [selected,setSelected] = useState('all');
  return <div className="etiquette-page">
    <div className="page-heading"><div><span className="eyebrow">함께하는 자리의 작은 배려</span><h1>경조사 예절</h1><p>마음을 전할 때 필요한 준비와 인사말을 살펴보세요.</p></div></div>
    <section className="card etiquette-common"><Icon name="HandHeart" size={24}/><div><h2>정해진 형식보다, 상대를 살피는 마음</h2><p>예절은 가족·지역·종교에 따라 달라질 수 있어요. 초대한 분과 현장의 안내를 먼저 따라 주세요. 축의금과 조의금, 선물에 하나의 정답은 없어요. 관계와 내 형편을 함께 살펴 결정해 주세요.</p><p>함께하기 어렵다면 미리 연락해 축하나 위로의 마음을 전해 보세요. 조문 연락은 짧고 정중하게 전하고, 유족에게 답장을 재촉하지 않아요.</p></div></section>
    <div className="etiquette-filters" aria-label="예절 유형 선택"><button className={`filter-chip ${selected === 'all' ? 'active' : ''}`} aria-pressed={selected === 'all'} onClick={() => setSelected('all')}>전체</button>{guides.map(guide => <button key={guide.id} aria-pressed={selected === guide.id} className={`filter-chip ${selected === guide.id ? 'active' : ''}`} onClick={() => setSelected(guide.id)}>{guide.title}</button>)}</div>
    <div className="etiquette-grid">{guides.filter(guide => selected === 'all' || selected === guide.id).map(guide => <section className={`card etiquette-card oc oc-${guide.id === 'elders' ? 'other' : guide.id}`} key={guide.id}><header><span className="etiquette-icon"><Icon name={guide.icon} size={22}/></span><div><h2>{guide.title}</h2><p>{guide.subtitle}</p></div></header><dl>{guide.tips.map(([title,text]) => <div key={title}><dt>{title}</dt><dd>{text}</dd></div>)}</dl><div className="etiquette-avoid"><strong>한 번 더 배려하기</strong><p>{guide.avoid}</p></div></section>)}</div>
    <p className="etiquette-sources">일상적인 방문을 위한 서비스 편집 체크리스트입니다. 문상 방식은 <a href="https://www.samsunghospital.com/home/funerals/info/sense.do?tab=1" target="_blank" rel="noreferrer">삼성서울병원 장례식장 안내</a>를, 상황별 말의 차이는 <a href="https://www.korean.go.kr/nkview/news/8/55.htm" target="_blank" rel="noreferrer">국립국어원 언어 예절 자료</a>를 참고했습니다. 구체적인 의례는 현장에 확인하세요.</p>
  </div>;
}
