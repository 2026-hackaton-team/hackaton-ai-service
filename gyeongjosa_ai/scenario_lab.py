"""김시나리오의 합성 인맥을 실제 SQLite 작업공간에 최초 1회 등록한다."""

import json
from pathlib import Path

from .data import DemoData
from .workspace_store import WorkspaceInput, load_workspace, save_workspace


USER_ID = "SCENARIO_KIM"
USER = {
    "id": USER_ID, "name": "김시나리오", "login_id": "synthetic_kim_scenario",
    "demo_account": True, "fictional_affiliation": "AI 추천 검증용 가상 계정",
    "preferred_region": "서울", "preferred_event_types": ["결혼", "장례"],
}
CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "kim_scenario_cases.json"


def cases():
    """금액 결과를 저장하지 않는 질문·인물 테스트 명세를 읽는다."""
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def with_scenario_user(base: DemoData) -> DemoData:
    """기존 사용자와 장부를 변경하지 않고 전용 계정을 추가한다."""
    return DemoData({**base.dataset, "users": [*base.dataset["users"], USER]})


def scenario_workspace():
    """20개 인물·행사·양방향 장부의 검증 가능한 SQLite 입력을 구성한다."""
    people, events, records = [], [], []
    for case in cases():
        person = {
            "id": case["person_id"], "name": case["name"], "relation": case["relation"],
            "group": case["group"], "importance": "중요" if case["closeness_score"] >= 4 else "보통",
            "closeness_score": case["closeness_score"], "memo": case["memo"],
        }
        if case["focus"] == "relationship_drift":
            person["closeness_history"] = [{"score": 5}, {"score": 1}]
        if case["focus"] == "closeness_rise":
            person["closeness_history"] = [{"score": 2}, {"score": 5}]
        if case["focus"] == "support":
            person["non_monetary_support"] = ["행사 참석", "행사 준비 도움"]
        people.append(person)

        for direction, key in (("보낸 마음", "paid"), ("받은 마음", "received")):
            for index, amount in enumerate(case[key]):
                event_id = f"KIME-{case['id']}-{key}-{index + 1}"
                # 합성 거래 날짜는 수령액 급증 사례의 순서를 보존한다.
                year = 2021 if case["focus"] == "relationship_drift" else 2023 + min(index, 3)
                date = f"{year}-{index % 12 + 1:02d}-{10 + index:02d}"
                event_type = ("장례식" if case["focus"] == "mixed_categories" and index % 2
                              else "결혼식")
                events.append({
                    "id": event_id, "personId": case["person_id"],
                    "title": f"{case['name']} 관련 합성 경조사",
                    "type": event_type, "date": date,
                    "attendance": "attended" if direction == "보낸 마음" else "unknown",
                })
                records.append({
                    "id": f"KIMT-{case['id']}-{key}-{index + 1}",
                    "personId": case["person_id"], "eventId": event_id,
                    "type": event_type, "date": date, "direction": direction,
                    "amount": amount,
                })
    return WorkspaceInput.model_validate({
        "revision": 0, "people": people, "events": events, "records": records,
    })


def ensure_scenario_workspace():
    """빈 전용 계정에만 시드하며 사용자가 수정한 기록은 다시 덮어쓰지 않는다."""
    current = load_workspace(USER_ID)
    if current["initialized"]:
        return current
    return save_workspace(USER_ID, scenario_workspace())


def catalog():
    """검증 UI에 질문과 예상 검증 포인트만 전달한다."""
    return {
        "userId": USER_ID,
        "items": [
            {key: item[key] for key in (
                "id", "person_id", "name", "title", "question", "budget_krw", "focus", "group"
            )}
            for item in cases()
        ],
    }
