"""테스트 계정의 데이터 생성, 격리 및 재접속 보존을 검증한다."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.test_account_seed import TEST_USER_ID, test_workspace
from gyeongjosa_ai.workspace_store import WorkspaceInput


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


def test_workspace_fixture_links_and_boundaries():
    """24명·18개 일정·120개 거래의 소유 관계가 유효하다."""
    payload = test_workspace()
    assert len(payload["people"]) == 24
    assert len(payload["events"]) == 18
    assert len(payload["records"]) == 120
    WorkspaceInput.model_validate(payload)
    assert {record["direction"] for record in payload["records"]} == {"보낸 마음", "받은 마음"}
    assert {event["owner"] for event in payload["events"] if "owner" in event} == {"me"}


def test_account_is_initialized_once_and_keeps_changes(client):
    """최초 1회만 시드하며 나중의 수정과 다른 사용자 데이터를 보존한다."""
    accounts = client.get("/api/demo/users").json()["items"]
    assert any(item["id"] == TEST_USER_ID for item in accounts)
    original = client.get("/api/workspace/personal", headers=_headers()).json()
    assert original["initialized"] is True
    assert original["revision"] == 1
    assert len(original["people"]) == 24
    assert len(original["events"]) == 18
    assert len(original["records"]) == 120
    assert client.get("/api/workspace/personal", headers=_headers("U002")).json()["initialized"] is False

    changed = {"revision": original["revision"], "people": original["people"],
               "events": original["events"], "records": deepcopy(original["records"])}
    changed["records"][0]["amount"] = 90000
    saved = client.put("/api/workspace/personal", headers=_headers(), json=changed)
    assert saved.status_code == 200, saved.text
    again = client.get("/api/workspace/personal", headers=_headers()).json()
    assert again["revision"] == 2
    assert again["records"][0]["amount"] == 90000


def test_recommendations_include_nonfriends_but_respect_scope(client):
    """직접 친구·친구의 친구·지정된 비친구를 구분한다."""
    data = load_data()
    assert "SCU006" not in data.graph[TEST_USER_ID]
    assert data.graph[TEST_USER_ID] & data.graph["SCU006"]
    items = client.get("/api/shared-events/recommendations", headers=_headers()).json()["items"]
    reasons = {item["id"]: item["reason_code"] for item in items}
    assert reasons["TEST-SHARED-01"] == "direct_friend"
    assert reasons["TEST-SHARED-02"] == "friend_of_friend"
    assert reasons["TEST-SHARED-03"] == "friend_of_friend"
    assert reasons["TEST-SHARED-04"] == "designated"
    assert client.get("/api/shared-events/TEST-SHARED-04", headers=_headers("U004")).status_code == 404


def test_own_shared_events_are_persistent_and_revocable(client):
    """내 공유 소식은 세 건이며 철회 후에도 비공개 상태를 유지한다."""
    mine = client.get("/api/shared-events/mine", headers=_headers()).json()["items"]
    assert {item["id"] for item in mine} == {"TEST-MINE-1", "TEST-MINE-2", "TEST-MINE-3"}
    event_id = "TEST-MINE-1"
    assert client.get("/api/shared-events/" + event_id, headers=_headers()).status_code == 200
    assert client.patch("/api/shared-events/" + event_id, headers=_headers("U001"),
                        json={"audience_scope": "private"}).status_code == 404
    assert client.patch("/api/shared-events/" + event_id, headers=_headers(),
                        json={"audience_scope": "private"}).status_code == 200
    mine_again = client.get("/api/shared-events/mine", headers=_headers()).json()["items"]
    assert next(item for item in mine_again if item["id"] == event_id)["audience_scope"] == "private"


@pytest.mark.parametrize("field,value", [
    ("closeness_score", 0),
    ("closeness_score", 6),
])
def test_invalid_closeness_cannot_replace_fixture(client, field, value):
    """친밀도 경계값 오류로 합성 서버 원본이 사라지지 않는다."""
    current = client.get("/api/workspace/personal", headers=_headers()).json()
    bad = deepcopy(current)
    bad["people"][0][field] = value
    response = client.put("/api/workspace/personal", headers=_headers(), json=bad)
    assert response.status_code == 422
    assert client.get("/api/workspace/personal", headers=_headers()).json()["revision"] == 1
