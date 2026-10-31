from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal['금액 참고', '참석 대응', '메시지 작성', '우선순위']
ProviderName = Literal['mock', 'openai']


class AdviceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1000)
    mode: Mode = '금액 참고'
    personId: str = Field(min_length=1, max_length=128)
    eventId: str | None = Field(default=None, max_length=128)


class Evidence(BaseModel):
    label: str
    value: str


class AdviceResponse(BaseModel):
    title: str
    text: str
    evidence: list[Evidence]
    suggestions: list[str]
    amount: int | None = Field(default=None, gt=0)
    isMessage: bool = False
    provider: ProviderName = 'mock'
    dataSource: Literal['mock'] = 'mock'
    demo: bool = True


class Person(BaseModel):
    id: str
    name: str
    relation: str
    group: str = ''
    importance: Literal['매우 중요', '중요', '보통'] = '보통'
    lastMet: str = ''


class Event(BaseModel):
    id: str
    personId: str
    title: str
    type: str
    date: str
    time: str = '14:00'
    location: str = '가상 행사장'
    attendance: str = ''


class Record(BaseModel):
    id: str
    personId: str
    type: str
    date: str
    direction: Literal['보낸 마음', '받은 마음']
    amount: int = Field(gt=0)


class WorkspaceSnapshot(BaseModel):
    people: list[Person]
    events: list[Event]
    records: list[Record]
