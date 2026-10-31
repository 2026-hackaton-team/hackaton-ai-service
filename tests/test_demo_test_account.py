"""테스트 계정이 빈 상태로 시작하고 저장한 기록을 유지하는지 검증한다."""

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.test_account_seed import TEST_USER_ID


def _headers(user=TEST_USER_ID):
    """가상 계정 API 헤더를 구성한다."""
    return {"X-Demo-User-Id": user}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """시연 계정에만 영향을 주는 임시 SQLite를 사용한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "personal.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_SHARED_EVENTS_DB", str(tmp_path / "shares.sqlite3"))
    with TestClient(app) as value:
        yield value


def test_account_exists_without_friends_or_notices(client):
    """계정은 선택할 수 있지만 친구·받은 소식·내 소식은 비어 있다."""
    accounts = client.get("/api/demo/users").json()["items"]
    assert any(item["id"] == TEST_USER_ID for item in accounts)
    assert not load_data().graph[TEST_USER_ID]
    assert client.get("/api/shared-events/recommendations", headers=_headers()).json()["items"] == []
    assert client.get("/api/shared-events/mine", headers=_headers()).json()["items"] == []


def test_workspace_starts_empty_and_keeps_saved_records(client):
    """서버 작업공간은 자동으로 채우지 않고, 사용자가 저장한 내용만 남긴다."""
    first = client.get("/api/workspace/personal", headers=_headers()).json()
    assert first["initialized"] is False
    assert first["people"] == first["events"] == first["records"] == []

    person = {"id": "P1", "name": "홍길동", "relation": "친구", "importance": "보통", "interactions": []}
    saved = client.put("/api/workspace/personal", headers=_headers(),
                       json={"revision": 0, "people": [person], "events": [], "records": []})
    assert saved.status_code == 200, saved.text
    again = client.get("/api/workspace/personal", headers=_headers()).json()
    assert again["revision"] == 1
    assert [item["name"] for item in again["people"]] == ["홍길동"]
    assert client.get("/api/workspace/personal", headers=_headers("U002")).json()["initialized"] is False


@pytest.mark.parametrize("value", [0, 6])
def test_invalid_closeness_is_rejected(client, value):
    """친밀도 경계값 오류는 저장되지 않는다."""
    person = {"id": "P1", "name": "홍길동", "relation": "친구", "closeness_score": value, "interactions": []}
    response = client.put("/api/workspace/personal", headers=_headers(),
                          json={"revision": 0, "people": [person], "events": [], "records": []})
    assert response.status_code == 422
    assert client.get("/api/workspace/personal", headers=_headers()).json()["initialized"] is False
