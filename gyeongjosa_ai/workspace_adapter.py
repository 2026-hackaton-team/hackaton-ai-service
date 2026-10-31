"""SQLite 작업공간 기록을 일반 상담 엔진의 계정별 입력 형태로 변환한다."""
from __future__ import annotations

from .data import DemoData
from .workspace_store import load_workspace


EVENT_TYPES = {
    "결혼식": "결혼", "장례식": "장례", "돌잔치": "돌",
    "백일잔치": "백일", "생일": "생일", "환갑잔치": "환갑",
    "칠순잔치": "칠순", "팔순잔치": "팔순",
}


def _category(value: str) -> str:
    """프런트 표시 명칭을 추천 엔진의 행사 분류로 통일한다."""
    return EVENT_TYPES.get(value, value)


def data_for_chat(base: DemoData, user_id: str) -> DemoData:
    """해당 사용자의 SQLite가 초기화된 경우에만 합성 개인 기록을 교체한다."""
    workspace = load_workspace(user_id)
    if not workspace["initialized"]:
        return base

    people = []
    for row in workspace["people"]:
        person = {
            "id": row["id"], "owner_user_id": user_id, "linked_user_id": None,
            "name": row["name"], "relationship": row.get("relation") or "기타",
            "fictional_affiliation": row.get("group") or "",
        }
        closeness = row.get("closeness_score")
        if type(closeness) is int and 1 <= closeness <= 5:
            person["relationship_context"] = {"closeness_score": closeness}
        people.append(person)

    events = []
    for row in workspace["events"]:
        events.append({
            "id": row["id"], "owner_user_id": user_id,
            "contact_person_id": row["personId"],
            "title": row["title"], "subject_relation": "확인되지 않음",
            "category": _category(row["type"]), "start_date": row["date"],
            "actual_attendance": row.get("attendance") or "unknown",
        })
    event_ids = {row["id"] for row in events}

    transactions = []
    for row in workspace["records"]:
        event_id = row.get("eventId")
        if not event_id:
            event_id = "workspace-record:" + row["id"]
            if event_id not in event_ids:
                events.append({
                    "id": event_id, "owner_user_id": user_id,
                    "contact_person_id": row["personId"],
                    "title": row["type"] + " 금액 기록",
                    "subject_relation": "확인되지 않음",
                    "category": _category(row["type"]),
                    "start_date": row["date"], "actual_attendance": "unknown",
                })
                event_ids.add(event_id)
        transactions.append({
            "id": row["id"], "owner_user_id": user_id,
            "contact_person_id": row["personId"], "private_event_id": event_id,
            "direction": "paid" if row["direction"] == "보낸 마음" else "received",
            "amount_krw": row["amount"],
        })

    source = dict(base.dataset)
    occupied = {p["id"] for p in people}
    source["people"] = [p for p in source["people"]
                        if p["owner_user_id"] != user_id and p["id"] not in occupied] + people
    source["private_events"] = [e for e in source["private_events"]
                                if e["owner_user_id"] != user_id] + events
    source["transactions"] = [t for t in source["transactions"]
                              if t["owner_user_id"] != user_id] + transactions
    return DemoData(source)
