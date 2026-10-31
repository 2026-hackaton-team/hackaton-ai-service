"""로그인 계정이 하나의 서버 사용자 ID로 모든 기록을 쓰고, 다른 계정 기록에 접근하지 못하는지 검증한다."""

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.account_store import workspace_owner
from gyeongjosa_ai.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GYEONGJOSA_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_DEMO_DB", str(tmp_path / "conversations.sqlite3"))
    with TestClient(app) as session:
        yield session


@pytest.mark.parametrize(("username", "expected"), [
    ("test1234", "TEST1234"),
    ("kim_scenario", "SCENARIO_KIM"),
    (" New_Demo ", "ACC:new_demo"),
])
def test_login_maps_to_one_server_identity(username, expected):
    assert workspace_owner(username) == expected


def test_member_identity_is_usable_only_with_its_own_session(client):
    body = {"name": "회원", "password": "a_secure_demo_password", "phone": "01012345678",
            "workplace": "", "organization": "", "workType": "일반 회사원", "visibility": "전체 공개"}
    first = client.post("/api/auth/signup", json={**body, "username": "member_a", "email": "a@example.invalid"}).json()
    headers = {"X-Demo-User-Id": first["userId"]}
    assert client.get("/api/conversations", headers=headers).status_code == 200
    assert client.get("/api/notices", headers=headers).status_code == 200

    client.post("/api/auth/signup", json={**body, "username": "member_b", "email": "b@example.invalid"})
    assert client.get("/api/workspace/personal", headers=headers).status_code == 401
    assert client.get("/api/conversations", headers=headers).status_code == 401

    client.post("/api/auth/logout")
    assert client.get("/api/workspace/personal", headers=headers).status_code == 401
    assert client.get("/api/workspace/personal", headers={"X-Demo-User-Id": "LOCAL_MEMBER_A"}).status_code == 401
