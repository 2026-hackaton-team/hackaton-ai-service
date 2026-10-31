"""Grounded facts and mock replies. Model providers cannot replace evidence/amount."""
from datetime import date
import re

from .schemas import AdviceRequest, AdviceResponse, Event, Person, WorkspaceSnapshot


def detect_intent(question: str, mode: str) -> str:
    patterns = [
        ('message', r'메시지|문구|문자|답장|써\s*줘|작성해|위로해\s*줘|축하해\s*줘'),
        ('attendance', r'불참|못\s*가|못\s*갈|못\s*오|참석|참여|가야'),
        ('amount', r'금액|얼마|축의금|조의금|부의금|예산'),
        ('priority', r'우선|놓치|먼저'),
    ]
    for intent, pattern in patterns:
        if re.search(pattern, question):
            return intent
    return {'메시지 작성': 'message', '참석 대응': 'attendance', '우선순위': 'priority'}.get(mode, 'amount')


def money(amount: int) -> str:
    return f'{amount:,}원'


def selected_event(snapshot: WorkspaceSnapshot, person_id: str, today: date, event_id: str | None = None) -> Event | None:
    events = [event for event in snapshot.events if event.personId == person_id]
    if event_id:
        return next((event for event in events if event.id == event_id), None)
    upcoming = sorted((event for event in events if event.date >= today.isoformat()), key=lambda event: (event.date, event.time))
    return upcoming[0] if upcoming else max(events, key=lambda event: event.date, default=None)


def build_advice(request: AdviceRequest, snapshot: WorkspaceSnapshot, today: date) -> AdviceResponse:
    person = next(person for person in snapshot.people if person.id == request.personId)
    intent = detect_intent(request.question, request.mode)
    event = selected_event(snapshot, person.id, today, request.eventId)
    records = sorted((record for record in snapshot.records if record.personId == person.id), key=lambda record: record.date, reverse=True)
    incoming = next((record for record in records if record.direction == '받은 마음'), None)
    outgoing = next((record for record in records if record.direction == '보낸 마음' and event and record.type == event.type), None)
    evidence = [{'label': '관계', 'value': f'{person.relation} · {person.group or "그룹 없음"} · {person.importance}'}]
    if incoming:
        evidence.append({'label': '최근 받은 마음', 'value': f'{incoming.date} · {incoming.type} · {money(incoming.amount)}'})
    if outgoing:
        evidence.append({'label': '같은 유형에 보낸 마음', 'value': f'{outgoing.date} · {outgoing.type} · {money(outgoing.amount)}'})
    if person.lastMet:
        evidence.append({'label': '최근 만남', 'value': person.lastMet})
    if event:
        evidence.append({'label': '참고한 일정', 'value': f'{event.date} · {event.title} · {event.attendance or "참석 여부 선택"}'})
    funeral = bool(event and event.type == '장례식') or bool(re.search(r'부고|조문|조의|애도|추모', request.question)) or ('위로' in request.question and '축하' not in request.question)
    cannot = bool(re.search(r'불참|못\s*가|못\s*갈|못\s*오|참석.{0,8}(?:못|어려|없)', request.question))
    explicitly_attending = not cannot and bool(re.search(r'참석할|참석해|참석.{0,4}가능|갈\s*수|갈게', request.question))
    cannot = cannot or (not explicitly_attending and bool(event and event.attendance == '불참'))
    if intent == 'message':
        if funeral:
            text = f'{person.name}님, 갑작스러운 소식에 마음이 무겁습니다. 깊은 애도의 마음을 전하며, 어려운 시간 잘 추스르시길 바랍니다. 필요한 일이 있다면 말씀해 주세요.'
        elif event and event.type == '돌잔치':
            text = f'{person.name}님, 아이의 첫 번째 생일을 진심으로 축하해요. 온 가족의 건강과 행복을 응원합니다.'
        elif event and event.type == '생일':
            text = f'{person.name}님, 생일을 진심으로 축하해요. 새로운 한 해도 건강하고 행복한 순간들로 가득하길 바랍니다.'
        elif (event and event.type == '결혼식') or re.search(r'결혼|축의', request.question):
            text = f'{person.name}님, 결혼을 진심으로 축하해요. 서로에게 든든한 편이 되어 다정하고 행복한 날들을 함께하시길 응원합니다.'
        else:
            text = f'{person.name}님, 소중한 날을 함께 기억하며 진심 어린 마음을 전합니다. 늘 건강하고 평안하시길 바랍니다. 어떤 행사인지 알려 주시면 그 상황에 맞는 문구를 더 구체적으로 준비할 수 있어요.'
        if cannot:
            text += ' 직접 찾아뵙지 못해 죄송한 마음입니다. 멀리서나마 함께 애도하겠습니다.' if funeral else ' 소중한 날에 함께하지 못해 아쉬워요. 멀리서나마 축하하고 조만간 따로 인사드릴게요.'
        return AdviceResponse(title='조심스럽게 전하는 위로' if funeral else '마음을 담은 메시지 초안', text=text, evidence=evidence, suggestions=['불참할 때 보낼 메시지', '금액도 참고하고 싶어요'], isMessage=True)
    if intent == 'attendance':
        if cannot:
            text = f'{person.name}님께 참석이 어려운 사정을 짧게 전하고 {"위로" if funeral else "축하"}의 마음을 함께 표현해 보세요. '
            text += '답장을 재촉하지 않고, 시간이 지난 뒤 안부를 전해 보세요.' if funeral else '행사가 끝난 뒤 따로 만나거나 안부를 전하면 좋겠습니다.'
        elif event:
            text = f'{person.name}님의 {event.type}는 {event.date} {event.time}, {event.location}에 예정되어 있어요. '
            text += '빈소와 조문 가능 시간을 확인하고 조용히 위로를 전해 주세요.' if funeral else '장소와 시간을 확인하고 참석 여부를 미리 알려 주세요.'
        else:
            text = f'{person.name}님의 행사 날짜와 장소를 먼저 확인해 주세요. 참석이 어려우면 사정을 미리 전하고 마음을 담은 메시지를 보내 보세요.'
        return AdviceResponse(title='함께하지 못할 때의 대응' if cannot else '참석 전 준비할 마음', text=text, evidence=evidence, suggestions=['보낼 메시지를 작성해 주세요', '금액 참고하기'])
    if intent == 'priority':
        by_id = {candidate.id: candidate for candidate in snapshot.people}
        ranks = {'매우 중요': 2, '중요': 1, '보통': 0}
        ranked = sorted((candidate for candidate in snapshot.events if candidate.date >= today.isoformat() and candidate.personId in by_id), key=lambda candidate: (candidate.type != '장례식', candidate.date, -ranks[by_id[candidate.personId].importance], candidate.time))
        if not ranked:
            return AdviceResponse(title='예정된 경조사가 없어요', text='다가오는 일정이 없어 우선순위를 정할 수 없어요.', evidence=[], suggestions=['참석 대응 가이드'])
        first = ranked[0]
        target = by_id[first.personId]
        days = (date.fromisoformat(first.date) - today).days
        text = f'{first.title}{"이 오늘이에요" if days == 0 else f"까지 {days}일 남았어요"}. '
        text += '갑작스러운 조사인 만큼 빈소와 조문 가능 시간을 먼저 확인해 주세요.' if first.type == '장례식' else '참석 여부와 장소를 먼저 확인해 주세요.'
        if len(ranked) > 1:
            text += f' 그다음은 {ranked[1].title}({ranked[1].date})입니다.'
        return AdviceResponse(title='가장 먼저 챙길 마음', text=text, evidence=[{'label': '선정 기준', 'value': '조사 우선 · 가까운 날짜 · 같은 날은 매우 중요 → 중요 → 보통'}, {'label': '참고한 일정', 'value': f'{first.date} · {first.title}'}, {'label': '관계 중요도', 'value': target.importance}], suggestions=['참석 대응 가이드', '메시지 작성하기'])
    amount = incoming.amount if incoming else outgoing.amount if outgoing else None
    if amount:
        source = '받은 기록' if incoming else '같은 유형에 보낸 기록'
        text = f'{person.name}님과 주고받은 내역에 {money(amount)}을 {source}이 있어요. 이 금액을 하나의 참고점으로 살펴볼 수 있습니다. 관계 중요도만으로 금액을 올리지 않으며, 현재의 친밀도·참석 여부·본인의 예산에 맞게 결정해 주세요.'
        if incoming and event and incoming.type != event.type:
            text += f' 받은 기록은 {incoming.type}이며 이번 행사와 유형이 다르다는 점도 함께 참고해 주세요.'
    else:
        text = f'{person.name}님과 비교할 금액 기록이 충분하지 않아 금액을 제안하지 않았어요. 관계와 참석 여부, 예산을 먼저 살펴보고 과거 내역을 추가해 주세요.'
    return AdviceResponse(title=f'{person.name}님께 전할 마음, 기록을 참고해 보세요', text=text, evidence=evidence, suggestions=['참석하지 못한다면?', '축하·위로 메시지 작성'], amount=amount)
