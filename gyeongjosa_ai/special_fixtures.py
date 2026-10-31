"""기존 데이터는 보존하며 고정 특별 시연 자료만 메모리에서 결합한다."""
from __future__ import annotations

import copy

from . import seed_db

COLLECTIONS = ("users", "friendships", "people", "private_events", "transactions", "shared_notices")


def merge_special_fixtures(original: dict) -> dict:
    """원본을 수정하지 않고 추가 자료의 ID·소유자·연결을 검사한다."""
    result = copy.deepcopy(original)
    fixtures = seed_db.load("v4_special_fixtures")
    for field in COLLECTIONS:
        existing = {row["id"] for row in result[field]}
        ids = [row["id"] for row in fixtures[field]]
        if len(ids) != len(set(ids)) or any(identifier in existing for identifier in ids):
            raise ValueError(f"특별 시연 {field} 식별자가 중복됩니다.")
        result[field].extend(copy.deepcopy(fixtures[field]))
    users = {row["id"] for row in result["users"]}
    people = {row["id"]: row for row in result["people"]}
    events = {row["id"]: row for row in result["private_events"]}
    for person in fixtures["people"]:
        if person["owner_user_id"] not in users or person["linked_user_id"] not in users:
            raise ValueError("특별 시연 인물 참조가 잘못되었습니다.")
    for link in fixtures["friendships"]:
        if link["user_a_id"] not in users or link["user_b_id"] not in users or (
            link["status"] not in ("accepted", "pending")
            or type(link["allow_connection_for_recommendation"]) is not bool
        ):
            raise ValueError("특별 시연 계정 연결이 잘못되었습니다.")
    for event in fixtures["private_events"]:
        if people[event["contact_person_id"]]["owner_user_id"] != event["owner_user_id"] or (
            event["category"] not in original["event_categories"]
        ):
            raise ValueError("특별 시연 행사 소유자가 잘못되었습니다.")
    for record in fixtures["transactions"]:
        event = events.get(record["private_event_id"])
        if event is None or event["owner_user_id"] != record["owner_user_id"] or (
            event["contact_person_id"] != record["contact_person_id"]
            or type(record["amount_krw"]) is not int or record["amount_krw"] < 0
        ):
            raise ValueError("특별 시연 거래 참조가 잘못되었습니다.")
    return result
