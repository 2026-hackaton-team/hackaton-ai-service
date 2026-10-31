"""시연 계정의 22개 상담 자료와 세션·데이터 보존을 검증한다."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai import integration_api
from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.dependencies import get_service
from gyeongjosa_ai.service import ChatService
from gyeongjosa_ai.test_account_seed import (
    TEST_USER_ID, demo_cases, demo_workspace, ensure_test_workspace,
)
from gyeongjosa_ai.workspace_store import WorkspaceInput, load_workspace, save_workspace


def _headers(user=TEST_USER_ID):
    """가상 계정 API 헤더를 구성한다."""
    return {"X-Demo-User-Id": user}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """시연 계정에만 영향을 주는 임시 SQLite와 로그인 세션을 사용한다."""
    monkeypatch.setenv("GYEONGJOSA_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "personal.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_SHARED_EVENTS_DB", str(tmp_path / "shares.sqlite3"))
    monkeypatch.setattr(integration_api, "_DB", tmp_path / "conversations.sqlite3")
    get_service.cache_clear()
    with TestClient(app) as value:
        assert value.post("/api/auth/login", json={"username": "test1234", "password": "test1234"}).status_code == 200
        yield value
    get_service.cache_clear()


def test_demo_workspace_has_twenty_two_people(client):
    """22명의 상담 기록만 제공하고 친구·공유·테스트 화면용 목록은 만들지 않는다."""
    workspace = client.get("/api/workspace/personal", headers=_headers()).json()
    items = demo_cases()
    assert workspace["initialized"]
    assert len(workspace["people"]) == len(items) == 22
    assert client.get("/api/demo/kim-scenarios", headers=_headers()).status_code == 403
    assert {p["id"] for p in workspace["people"]} == {c["person_id"] for c in items}
    assert len(workspace["records"]) == 100
    assert len(workspace["events"]) == 122
    assert client.get("/api/shared-events/recommendations", headers=_headers()).json()["items"] == []
    assert client.get("/api/shared-events/mine", headers=_headers()).json()["items"] == []
    assert client.get("/api/workspace/personal", headers=_headers("U002")).json()["initialized"] is False


def test_upcoming_dates_are_relative_to_first_seed_day():
    """첫 적용일에 예정 일정 22개가 모두 미래로 등록된다."""
    snapshot = demo_workspace(date(2026, 10, 31))
    upcoming = [e for e in snapshot.events if e.id.startswith("TEST-UPCOMING-")]
    assert len(upcoming) == 22
    assert min(e.date for e in upcoming) == date(2026, 11, 1)
    assert max(e.date for e in upcoming) == date(2026, 11, 22)


def test_migration_preserves_existing_records_and_only_runs_once(client):
    """이미 초기화된 계정에 기존 기록을 보존하며 시드하고 삭제한 자료를 복원하지 않는다."""
    person = {"id": "P1", "name": "홍길동", "relation": "친구"}
    save_workspace(TEST_USER_ID, WorkspaceInput(revision=0, people=[person]))
    seeded = ensure_test_workspace()
    assert seeded["revision"] == 2
    assert len(seeded["people"]) == 23
    assert seeded["people"][0]["name"] == "홍길동"
    assert ensure_test_workspace()["revision"] == 2
    changed = {**seeded, "people": [dict(p) for p in seeded["people"]]}
    changed["people"][1]["memo"] = "사용자가 수정한 메모"
    save_workspace(TEST_USER_ID, WorkspaceInput.model_validate(changed))
    assert ensure_test_workspace()["people"][1]["memo"] == "사용자가 수정한 메모"
    save_workspace(TEST_USER_ID, WorkspaceInput(revision=3))
    assert ensure_test_workspace()["people"] == []
    assert ensure_test_workspace()["revision"] == 4


def test_existing_empty_workspace_is_seeded(client):
    """이전 버전에서 빈 상태로 초기화된 계정에도 시연 자료를 추가한다."""
    save_workspace(TEST_USER_ID, WorkspaceInput(revision=0))
    snapshot = client.get("/api/workspace/personal", headers=_headers()).json()
    assert snapshot["revision"] == 2
    assert len(snapshot["people"]) == 22


def test_seed_preserves_same_id_user_edits(client):
    """시드 ID가 이미 있어도 사용자가 저장한 메모·금액을 덮어쓰지 않는다."""
    snapshot = demo_workspace().model_dump(mode="json")
    snapshot["people"][0]["memo"] = "기존 사용자 메모"
    snapshot["records"][0]["amount"] = 12345
    save_workspace(TEST_USER_ID, WorkspaceInput.model_validate(snapshot))
    seeded = ensure_test_workspace()
    assert seeded["people"][0]["memo"] == "기존 사용자 메모"
    assert seeded["records"][0]["amount"] == 12345
    assert len(seeded["people"]) == 22
    assert len(seeded["records"]) == 100


@pytest.mark.parametrize("value", [0, 6])
def test_invalid_closeness_is_rejected(client, value):
    """친밀도 경계값 오류는 저장되지 않는다."""
    first = client.get("/api/workspace/personal", headers=_headers()).json()
    person = {"id": "P1", "name": "홍길동", "relation": "친구", "closeness_score": value}
    response = client.put("/api/workspace/personal", headers=_headers(),
                          json={"revision": first["revision"], "people": [person], "events": [], "records": []})
    assert response.status_code == 422
    assert load_workspace(TEST_USER_ID)["revision"] == first["revision"]


def test_test_account_requires_own_login_session(client):
    """헤더만 지정한 비로그인 요청과 다른 회원 세션을 거부한다."""
    client.post("/api/auth/logout")
    for path in ("/api/workspace/personal", "/api/demo/kim-scenarios", "/api/conversations"):
        assert client.get(path, headers=_headers()).status_code == 401
    for suffix in ("people", "notices", "dashboard"):
        assert client.get(f"/api/users/{TEST_USER_ID}/{suffix}").status_code == 401
    assert client.post("/api/chat", json={"user_id": TEST_USER_ID, "question": "주고받은 기록"}).status_code == 401
    assert client.post("/api/conversations", headers=_headers()).status_code == 401
    assert client.post("/api/auth/signup", json={
        "username": "other_user", "name": "다른 회원", "password": "password123",
        "phone": "01012345678", "email": "other@example.invalid", "workplace": "",
        "organization": "", "workType": "일반 회사원", "visibility": "전체 공개",
    }).status_code == 201
    assert client.get("/api/workspace/personal", headers=_headers()).status_code == 401


def test_concurrent_seed_is_applied_only_once(client):
    """동시에 시드 요청이 들어와도 기록과 적용 버전이 중복되지 않는다."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        snapshots = list(pool.map(lambda _: ensure_test_workspace(), range(2)))
    assert all(s["revision"] == 1 and len(s["people"]) == 22 for s in snapshots)


class Gateway:
    """외부 모델 대신 의도·설명만 고정하고 실제 추천 엔진을 실행한다."""

    def classify(self, context, people_ids, notice_ids):
        return {"intent": "amount", "person_id": None, "notice_id": None,
                "event_type": "장례" if "장례" in context["question"] else "결혼", "model": "test-model"}

    def generate(self, context, allowed_ids, preferred_model=None):
        return {"answer": "확인된 계정 기록과 예산을 참고해 주세요.", "model": "test-model",
                "evidence_ids": sorted(allowed_ids), "suggested_amount_krw": 999999}


def test_same_name_followup_keeps_event_budget_and_meal(client):
    """동명이인을 확인하는 사이에도 처음 질문의 행사·예산·식사 조건을 유지한다."""
    app.dependency_overrides[get_service] = lambda: ChatService(load_data(), Gateway())
    try:
        cid = client.post("/api/conversations", headers=_headers()).json()["id"]
        first = client.post(f"/api/conversations/{cid}/messages", headers=_headers(), json={
            "requestId": "same-name-first", "text": "문지훈 결혼식에 식사하지 않고 참석해. 예산은 10만원이야. 얼마가 좋을까?",
        }).json()
        assert first["pending_field"] == "person_id"
        assert first["context"]["event_type"] == "결혼"
        second = client.post(f"/api/conversations/{cid}/messages", headers=_headers(), json={
            "requestId": "same-name-reply", "text": "운영팀 문지훈이야.",
        }).json()
        assert second["status"] == "answer"
        assert second["context"]["person_id"] == "KIMP018"
        assert second["context"]["event_type"] == "결혼"
        assert second["context"]["budget_krw"] == 100000
        assert second["context"]["attendance_with_meal"] is False
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_all_twenty_two_scenarios_use_logged_in_account_records(client):
    """22건을 실제 세션·저장·추천 경로로 실행해 근거 계정과 예산을 검사한다."""
    app.dependency_overrides[get_service] = lambda: ChatService(load_data(), Gateway())
    try:
        items = demo_cases()
        assert len(items) == 22
        for item in items:
            cid = client.post("/api/conversations", headers=_headers()).json()["id"]
            response = client.post(f"/api/conversations/{cid}/messages", headers=_headers(), json={
                "requestId": "test-account-" + item["id"], "text": item["question"],
            })
            assert response.status_code == 200, (item["id"], response.text)
            result = response.json()
            assert result["status"] in {"answer", "need_more_info"}, item["id"]
            if item["focus"] not in {"legal_recipient", "legal_sender"}:
                assert result["status"] == "answer", (item["id"], result)
                assert result["context"]["person_id"] == item["person_id"]
                assert 0 < result["suggested_amount_krw"] <= item["budget_krw"]
                assert result["suggested_amount_krw"] == result["v4_analysis"]["amount_krw"]
                assert result["history_stats"] and result["budget_analysis"]
            else:
                assert result.get("suggested_amount_krw") is None
            assert len(client.get(f"/api/conversations/{cid}", headers=_headers()).json()["messages"]) == 2
        client.post("/api/auth/logout")
        assert client.get(f"/api/conversations/{cid}", headers=_headers()).status_code == 401
    finally:
        app.dependency_overrides.pop(get_service, None)
