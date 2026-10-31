"""발표용 test1234 계정과 22개 상담용 합성 기록을 준비한다."""

from datetime import datetime, timedelta, timezone

TEST_USER_ID = "TEST1234"
TEST_LOGIN = "test1234"


def extend_test_dataset(dataset):
    """기존 가상 사용자에 시연 전용 계정을 추가한다."""
    if any(user["id"] == TEST_USER_ID for user in dataset["users"]):
        raise ValueError("테스트 계정 ID가 기존 데이터와 충돌합니다.")
    user = {
        "id": TEST_USER_ID, "name": "테스트 사용자", "login_id": TEST_LOGIN,
        "demo_account": True, "fictional_affiliation": "마음결 시연팀",
        "preferred_region": "서울",
        "preferred_event_types": ["결혼", "장례", "돌"],
    }
    return {**dataset, "users": [*dataset["users"], user]}


def demo_cases():
    """기존 20개 관계 사례에 식사 참석과 소액 예산 사례를 더한다."""
    from .scenario_lab import cases
    return [*cases(), {
        "id": "TEST-21", "person_id": "TESTP021", "name": "한예린",
        "title": "식사 참석과 예산 상한", "relation": "친구", "closeness_score": 3,
        "paid": [50000, 50000], "received": [50000, 50000], "budget_krw": 70000,
        "question": "친구 한예린 결혼식에 참석해서 식사해요. 예산은 7만원이고 과거에 서로 5만원씩 주고받았어요. 얼마를 참고하면 좋을까요?",
        "focus": "meal_attendance", "group": "합성 시연", "memo": "식사 참석도 예산 상한을 넘기지 않는다.",
    }, {
        "id": "TEST-22", "person_id": "TESTP022", "name": "차유진",
        "title": "과거 고액과 1만원 예산", "relation": "친구", "closeness_score": 3,
        "paid": [100000, 100000], "received": [100000, 100000], "budget_krw": 10000,
        "question": "친구 차유진 장례식에 이번 예산은 최대 1만원이에요. 서로 10만원씩 주고받았지만 무리할 수 없어요. 얼마가 좋을까요?",
        "focus": "budget_cap", "group": "합성 시연", "memo": "과거 거래보다 현재 지출 가능 예산을 우선한다.",
    }]


def demo_workspace(today=None):
    """상담 장부와 첫 적용일 기준 향후 22개 일정을 같은 인맥에 연결한다."""
    from .scenario_lab import scenario_workspace
    from .workspace_store import WorkspaceInput
    today = today or datetime.now(timezone(timedelta(hours=9))).date()
    items = demo_cases()
    snapshot = scenario_workspace(items).model_dump(mode="json")
    for index, case in enumerate(items):
        funeral = "장례식" in case["question"]
        snapshot["events"].append({
            "id": "TEST-UPCOMING-" + case["id"], "personId": case["person_id"],
            "title": f"[합성 시연] {case['name']} {'장례식' if funeral else '결혼식'}",
            "type": "장례식" if funeral else "결혼식",
            "date": (today + timedelta(days=index + 1)).isoformat(),
            "time": "13:00", "location": "가상 시연 장소", "attendance": "",
            "memo": case["title"],
        })
    return WorkspaceInput.model_validate(snapshot)


def ensure_test_workspace():
    """이미 빈 상태로 초기화된 계정에도 1회 추가하고 이후 수정·삭제를 보존한다."""
    from .workspace_store import seed_workspace_once
    return seed_workspace_once(TEST_USER_ID, "test1234-scenarios-v1", demo_workspace())
