"""한 줄로 적은 경조사 문장을 일정 입력값으로 제안한다.

- AI(코디세이 API)가 있으면 먼저 해석하고, 실패하거나 키가 없으면 규칙 기반으로 해석한다.
- 결과는 '제안'일 뿐이며 사용자가 확인한 뒤 저장한다. 서버에 저장하지 않는다.
- AI에는 사용자가 입력한 문장과 기준 날짜만 보낸다.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

# 화면의 행사 유형과 맞춘다. 목록에 없는 유형은 화면에서 '직접 입력'으로 채운다.
TYPE_KEYWORDS = [
    ("장례식", r"장례|부고|빈소|발인|조문|부친상|모친상|빙부상|빙모상|별세|상을\s*당"),
    ("결혼식", r"결혼|웨딩|혼례|예식"),
    ("돌잔치", r"돌잔치|첫\s*돌|돌\s*잔치"),
    ("백일", r"백일"),
    ("환갑", r"환갑|회갑"),
    ("칠순", r"칠순|고희"),
    ("팔순", r"팔순|산수연"),
    ("생일", r"생일|생신"),
    ("졸업", r"졸업"),
    ("집들이", r"집들이"),
]
RELATIONS = ["외할머니", "외할아버지", "할머니", "할아버지", "외삼촌", "작은아버지", "큰아버지", "작은어머니", "큰어머니",
             "아버지", "어머니", "부모님", "고모부", "이모부", "고모", "이모", "삼촌", "숙모", "사촌", "조카", "형님", "형수",
             "누나", "언니", "오빠", "형", "동생", "처제", "처남", "시누이", "친구", "동기", "동료", "선배", "후배",
             "팀장님", "부장님", "과장님", "대표님", "교수님", "선생님", "거래처"]
WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
PLACE_SUFFIX = r"(?:웨딩홀|웨딩|홀|장례식장|병원|호텔|레스토랑|식당|한정식|교회|성당|센터|컨벤션|하우스|가든|채플|회관)"


def _date(text: str, today: date):
    if m := re.search(r"(20\d{2})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})", text):
        return _safe(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text) or re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", text):
        value = _safe(today.year, int(m[1]), int(m[2]))
        if value and value < today - timedelta(days=30):
            value = _safe(today.year + 1, int(m[1]), int(m[2]))
        return value
    offsets = {"오늘": 0, "내일": 1, "모레": 2, "글피": 3}
    for word, offset in offsets.items():
        if word in text:
            return today + timedelta(days=offset)
    if m := re.search(r"(\d{1,2})\s*일\s*(?:뒤|후)", text):
        return today + timedelta(days=int(m[1]))
    if m := re.search(r"(다다음\s*주|다음\s*주|담주|이번\s*주|이번주)?\s*([월화수목금토일])요일", text):
        target = WEEKDAYS[m[2]]
        week = (m[1] or "").replace(" ", "")
        start = today - timedelta(days=today.weekday())
        if week in ("다음주", "담주"):
            start += timedelta(days=7)
        elif week == "다다음주":
            start += timedelta(days=14)
        value = start + timedelta(days=target)
        if not week and value < today:
            value += timedelta(days=7)
        return value
    if m := re.search(r"(?<![\d월])(\d{1,2})\s*일(?!\s*(?:뒤|후|전))", text):
        value = _safe(today.year, today.month, int(m[1]))
        if value and value < today:
            month = today.month % 12 + 1
            value = _safe(today.year + (today.month == 12), month, int(m[1]))
        return value
    return None


def _safe(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _time(text: str):
    periods = r"(오전|오후|저녁|밤|아침|낮)?"
    # 숫자 전체를 읽어 범위를 검사한다. 25시를 1시로 바꾸거나 일부 숫자만 읽지 않는다.
    colon = re.search(r"(?<!\d)" + periods + r"\s*(\d+):(\d+)(?!\d)", text)
    korean = None if colon else re.search(
        r"(?<!\d)" + periods + r"\s*(\d+)\s*시\s*(?:(\d+)\s*분|(반))?", text
    )
    match = colon or korean
    if match:
        period, raw_hour, raw_minute = match[1], match[2], match[3]
        hour = int(raw_hour)
        minute = int(raw_minute) if raw_minute else (30 if match[4] else 0)
        if len(raw_hour) > 2 or (raw_minute and len(raw_minute) > 2):
            return None
        if colon and len(raw_minute) != 2:
            return None
        if hour > 23 or minute > 59:
            return None
        if period:
            if not 1 <= hour <= 12:
                return None
            if period in ("오전", "아침"):
                hour %= 12
            elif period == "밤" and hour == 12:
                hour = 0
            else:
                hour = hour % 12 + 12
        elif korean and 1 <= hour <= 6:
            hour += 12  # '2시 결혼식'처럼 쓰면 보통 오후를 뜻한다.
        return f"{hour:02d}:{minute:02d}"
    if "정오" in text:
        return "12:00"
    return None


def _place(text: str):
    if m := re.search(r"([가-힣A-Za-z0-9·&\- ]{1,30}?" + PLACE_SUFFIX + r"(?:\s*[0-9]+\s*(?:층|호실|호))?)", text):
        place = re.sub(r"^(?:은|는|이|가|에|서|에서|으로|로)\s+", "", m[1].strip())
        words = place.split()
        # 앞쪽의 날짜·관계 단어는 장소에서 뺀다.
        noise = r"^(?:[\d/.:]+|\d+\s*(?:월|일|시|분)\S*|오전|오후|저녁|밤|아침|낮|정오|반|\S*요일|내일|모레|오늘|글피|다음|이번|담주|이번주|다음주)$"
        while words and (re.search(noise, words[0]) or words[0] in RELATIONS):
            words.pop(0)
        place = " ".join(words).strip()
        return place[:150] or None
    return None


def _who(text: str):
    relation = next((word for word in RELATIONS if word in text), None)
    name = None
    if m := re.search(r"([가-힣]{2,4})(?:님|씨)?(?:의|네)\s", text):
        candidate = m[1]
        if candidate not in RELATIONS and not re.search(r"다음|이번|오늘|내일|모레", candidate):
            name = candidate
    return name, relation


def rule_based(text: str, today: date) -> dict:
    """정규식만으로 문장에서 행사 정보를 찾는다."""
    text = str(text or "")
    event_type = next((label for label, pattern in TYPE_KEYWORDS if re.search(pattern, text)), None)
    when = _date(text, today)
    name, relation = _who(text)
    who = name or relation
    return {
        "type": event_type,
        "date": when.isoformat() if when else None,
        "time": _time(text),
        "location": _place(text),
        "person_name": name,
        "relation": relation,
        "title": f"{who} {event_type}".strip() if who and event_type else None,
    }


PROMPT = """너는 한국어 경조사 일정 입력 도우미다. 사용자가 한 줄로 적은 문장에서 일정 정보를 뽑아 JSON 하나만 출력한다.
키: type, date, time, location, person_name, relation, title
- type: 결혼식, 장례식, 돌잔치, 생일, 백일, 환갑, 칠순, 팔순, 졸업, 집들이 중 하나. 없으면 짧은 한국어 명사(최대 10자) 또는 null
- date: today 기준으로 계산한 YYYY-MM-DD 또는 null
- time: 24시간 HH:MM 또는 null (예: 오후 1시 → 13:00)
- location: 장소 이름 또는 null
- person_name: 문장에 이름이 직접 나오면 그 이름, 아니면 null (추측 금지)
- relation: 사촌, 고모, 친구, 동료 같은 관계 단어 또는 null
- title: "이름 또는 관계 + 행사 유형" 형태의 짧은 일정 이름 또는 null
문장에 없는 정보는 만들지 말고 null로 둔다. 설명 없이 JSON만 출력한다."""


def _validate_ai(raw: dict, today: date) -> dict:
    result = {}
    if isinstance(raw.get("type"), str) and 0 < len(raw["type"].strip()) <= 10:
        result["type"] = raw["type"].strip()
    if isinstance(raw.get("date"), str):
        try:
            value = date.fromisoformat(raw["date"])
            if today - timedelta(days=366) <= value <= today + timedelta(days=731):
                result["date"] = value.isoformat()
        except ValueError:
            pass
    if isinstance(raw.get("time"), str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", raw["time"]):
        result["time"] = raw["time"]
    for key, limit in (("location", 150), ("person_name", 20), ("relation", 20), ("title", 80)):
        if isinstance(raw.get(key), str) and raw[key].strip():
            result[key] = raw[key].strip()[:limit]
    return result


def parse_event_text(text: str, today: date, gateway=None) -> dict:
    """AI로 먼저 해석하고, 실패하면 규칙 기반 결과를 돌려준다. 두 결과를 합쳐 빈칸을 줄인다."""
    rules = rule_based(text, today)
    if gateway is None:
        try:
            from .ai import ModelGateway
            gateway = ModelGateway(timeout=20)
        except Exception:  # 의존성이 없는 환경에서도 규칙 기반은 동작해야 한다.
            gateway = None
    if gateway is not None and getattr(gateway, "api_key", ""):
        try:
            from .ai import FALLBACK_MODEL, PRIMARY_MODEL
            models = (PRIMARY_MODEL, FALLBACK_MODEL)
        except Exception:
            models = ("default",)
        for model in models:
            try:
                content = gateway._request({"today": today.isoformat(), "text": str(text)[:300]}, PROMPT, model)
                match = re.search(r"\{.*\}", content, re.S)
                ai = _validate_ai(json.loads(match[0] if match else content), today)
            except Exception:
                continue
            merged = {**rules, **{key: value for key, value in ai.items() if value}}
            return {"suggestion": merged, "source": "ai", "model": model}
    return {"suggestion": rules, "source": "rules", "model": None}
