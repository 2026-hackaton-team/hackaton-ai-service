"""일반 시연 로그인이 서버 단일 사용자 ID를 사용하는지 검증한다."""

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """계정별 저장 검증에 독립 SQLite를 사용한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    with TestClient(app) as session:
        yield session


@pytest.mark.parametrize(("username", "expected"), [
    ("test1234", "TEST1234"),
    ("demo_seojin", "U001"),
    ("kim_scenario", "SCENARIO_KIM"),
    ("new_demo", "LOCAL_NEW_DEMO"),
])
def test_login_resolves_one_server_identity(client, username, expected):
    """가상 프로필 선택 없이 로그인 ID로 서버 소유자를 결정한다."""
    response = client.post("/api/demo/accounts/resolve", json={"username": username})
    assert response.status_code == 200
    assert response.json()["user_id"] == expected


@pytest.mark.parametrize("username", ["", "abc", "UPPERCASE", "bad-name", "x" * 21, "synthetic_kim_scenario"])
def test_invalid_login_identity_is_rejected(client, username):
    """계정 ID 경계를 벗어난 문자열은 거부한다."""
    assert client.post("/api/demo/accounts/resolve", json={"username": username}).status_code == 422


def test_new_login_uses_isolated_sqlite_workspace(client):
    """신규 로그인 자료와 기존 가상 계정 자료를 혼합하지 않는다."""
    first = client.post("/api/demo/accounts/resolve", json={"username": "new_demo"}).json()["user_id"]
    assert first == "LOCAL_NEW_DEMO"
    headers = {"X-Demo-User-Id": first}
    original = client.get("/api/workspace/personal", headers=headers)
    assert original.status_code == 200
    assert original.json()["initialized"] is True
    assert len(original.json()["people"]) >= 20
    assert len(original.json()["records"]) >= 20
    before = original.json()
    saved = client.put("/api/workspace/personal", headers=headers, json={
        "revision": before["revision"], "people": before["people"],
        "events": before["events"], "records": before["records"][1:],
    })
    assert saved.status_code == 200
    assert len(client.get("/api/workspace/personal", headers=headers).json()["records"]) == len(before["records"]) - 1
    other = client.get("/api/workspace/personal", headers={"X-Demo-User-Id": "LOCAL_ANOTHER"}).json()
    assert other["initialized"] is True
    assert len(other["records"]) == len(before["records"])
    assert client.get("/api/conversations", headers=headers).status_code == 200
    assert client.get("/api/workspace/personal").status_code == 401
