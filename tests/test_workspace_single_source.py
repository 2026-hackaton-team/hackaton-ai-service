"""서버 단일 작업공간의 계정 격리·이전·AI 조회 경로 회귀 검증."""

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app
from gyeongjosa_ai.dependencies import get_service
from gyeongjosa_ai.workspace_adapter import data_for_chat


@pytest.fixture
def client(tmp_path, monkeypatch):
    """테스트마다 서버 SQLite 파일을 격리한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    with TestClient(app) as session:
        yield session


def _headers(user_id="U001"):
    return {"X-Demo-User-Id": user_id}


def _snapshot(revision=0, closeness=5):
    """본인 행사와 타인 경조사·양방향 기록을 포함한다."""
    return {
        "revision": revision,
        "people": [{
            "id": "p-person", "name": "테스트 지인", "relation": "친구", "importance": "중요",
            "closeness_score": closeness, "special": True, "group": "동아리",
        }],
        "events": [
            {"id": "e-other", "personId": "p-person", "title": "결혼식", "type": "결혼식",
             "date": "2026-10-01"},
            {"id": "e-mine", "personId": "", "owner": "me", "title": "내 결혼식", "type": "결혼식",
             "date": "2026-10-02"},
        ],
        "records": [
            {"id": "r-paid", "personId": "p-person", "eventId": "e-other", "type": "결혼식",
             "date": "2026-10-01", "direction": "보낸 마음", "amount": 100000},
            {"id": "r-received", "personId": "p-person", "type": "장례식",
             "date": "2025-10-01", "direction": "받은 마음", "amount": 200000},
        ],
    }


def test_initial_migration_preserves_source_and_ai_relationship_data(client):
    """친밀도·특별 관리·지급 수령 기록이 같은 서버 원천을 사용한다."""
    response = client.get("/api/workspace/personal", headers=_headers())
    assert response.status_code == 200
    assert response.json()["initialized"] is False

    source = _snapshot()
    assert client.post("/api/workspace/migrations/preview", headers=_headers(), json=source).status_code == 200
    saved = client.put("/api/workspace/personal", headers=_headers(), json=source)
    assert saved.status_code == 200, saved.text
    snapshot = client.get("/api/workspace/personal", headers=_headers()).json()
    assert snapshot["initialized"] is True
    assert snapshot["revision"] == 1
    assert snapshot["people"][0]["closeness_score"] == 5
    assert snapshot["people"][0]["special"] is True
    assert len(snapshot["people"]) == 1
    assert any(event["owner"] == "me" for event in snapshot["events"])

    data = data_for_chat(get_service().data, "U001")
    person = next(p for p in data.people("U001") if p["id"] == "p-person")
    assert person["relationship_context"]["closeness_score"] == 5
    assert person["special"] is True
    history = data.history("U001", "p-person")
    assert history["paid_total_krw"] == 100000
    assert history["received_total_krw"] == 200000
    assert all(event["id"] != "e-mine" for event in data.events("U001"))


def test_account_separation_and_cas_conflict(client):
    """다른 계정의 기록은 공개되지 않고 이전 버전으로 덮어쓸 수 없다."""
    assert client.put("/api/workspace/personal", headers=_headers(), json=_snapshot()).status_code == 200
    other = client.get("/api/workspace/personal", headers=_headers("U002")).json()
    assert other["initialized"] is False
    assert other["people"] == []
    assert client.put("/api/workspace/personal", headers=_headers(), json=_snapshot()).status_code == 409
    assert client.get("/api/workspace/personal", headers=_headers()).json()["revision"] == 1

    updated = _snapshot(revision=1, closeness=2)
    assert client.put("/api/workspace/personal", headers=_headers(), json=updated).status_code == 200
    assert client.get("/api/workspace/personal", headers=_headers()).json()["people"][0]["closeness_score"] == 2


@pytest.mark.parametrize("closeness", [0, 6, -1])
def test_out_of_range_closeness_is_rejected(client, closeness):
    """잘못된 친밀도는 저장되지 않는다."""
    assert client.put("/api/workspace/personal", headers=_headers(),
                      json=_snapshot(closeness=closeness)).status_code == 422
    assert client.get("/api/workspace/personal", headers=_headers()).json()["initialized"] is False


def test_bad_reference_does_not_create_partial_workspace(client):
    """인물과 금액의 행사 연결이 잘못되면 전체 쓰기를 취소한다."""
    snapshot = _snapshot()
    snapshot["records"][0]["eventId"] = "unknown"
    response = client.put("/api/workspace/personal", headers=_headers(), json=snapshot)
    assert response.status_code == 422
    state = client.get("/api/workspace/personal", headers=_headers()).json()
    assert state["initialized"] is False
    assert state["records"] == []


def test_unselected_profile_cannot_write(client):
    """가상 계정 없이 서버 자료를 생성할 수 없다."""
    assert client.put("/api/workspace/personal", json=_snapshot()).status_code == 401
