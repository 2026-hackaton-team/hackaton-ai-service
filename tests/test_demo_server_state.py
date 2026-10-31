"""서버 세션·친구 관계·알림 상태가 브라우저 저장 없이 유지되는지 검증한다."""

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """시드 데이터에 영향을 주지 않는 독립 사용자 DB를 사용한다."""
    monkeypatch.setenv("GYEONGJOSA_ACCOUNT_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    with TestClient(app) as session:
        yield session


def test_login_session_and_logout(client):
    """세션 쿠키에 저장된 식별자만으로 사용자 기록을 복원한다."""
    assert client.get("/api/account/session").json()["profile"] is None
    wrong = client.post("/api/account/login", json={"username": "test1234", "password": "wrong1234"})
    assert wrong.status_code == 401
    login = client.post("/api/account/login", json={"username": "test1234", "password": "test1234"})
    assert login.status_code == 200
    assert login.json()["userId"] == "TEST1234"
    assert login.cookies.get("maeum_session")
    assert client.get("/api/account/session").json()["profile"]["username"] == "test1234"
    assert client.post("/api/account/logout").status_code == 200
    assert client.get("/api/account/session").json()["profile"] is None


def test_signup_and_preferences_survive_new_session(client):
    """새 시연 계정과 설정을 서버에 저장하고 재로그인 후 복원한다."""
    user = {
        "username": "newuser", "name": "테스트 사용자", "password": "a_secure_demo_password",
        "phone": "01012345678", "email": "newuser@example.invalid",
        "workType": "일반 회사원", "visibility": "전체 공개",
    }
    response = client.post("/api/account/signup", json=user)
    assert response.status_code == 200, response.text
    assert response.json()["userId"] == "LOCAL_NEWUSER"
    assert client.post("/api/account/signup", json=user).status_code == 409
    assert client.patch("/api/account/preferences", json={"theme": "dark", "sidebarCollapsed": True}).status_code == 200
    read = client.post("/api/account/read", json={"keys": ["notice-1", "notice-2"]})
    assert read.status_code == 200
    assert read.json()["readIds"] == ["notice-1", "notice-2"]
    assert client.post("/api/account/logout").status_code == 200
    assert client.post("/api/account/login", json={"username": "newuser", "password": user["password"]}).status_code == 200
    prefs = client.get("/api/account/preferences").json()
    assert prefs["theme"] == "dark"
    assert prefs["sidebarCollapsed"] is True
    assert prefs["readIds"] == ["notice-1", "notice-2"]


def test_test1234_friends_and_shares_are_idempotent(client):
    """시연 시드가 재로그인마다 친구·공유 자료를 복제하지 않는다."""
    credentials = {"username": "test1234", "password": "test1234"}
    assert client.post("/api/account/login", json=credentials).status_code == 200
    first = client.get("/api/account/social").json()
    assert len(first["members"]) == 13
    assert len(first["social"]["friendships"]) == 12
    assert len(first["social"]["shares"]) == 3
    assert client.post("/api/account/logout").status_code == 200
    assert client.post("/api/account/login", json=credentials).status_code == 200
    second = client.get("/api/account/social").json()
    assert second == first


def test_social_cas_and_notification_dedup(client):
    """동시 쓰기 충돌은 덮어쓰지 않고 알림은 중복 기록하지 않는다."""
    assert client.post("/api/account/login", json={"username": "test1234", "password": "test1234"}).status_code == 200
    social = client.get("/api/account/social").json()
    patch = {"revision": social["revision"], **social["social"]}
    saved = client.put("/api/account/social", json=patch)
    assert saved.status_code == 200
    assert client.put("/api/account/social", json=patch).status_code == 409
    assert client.post("/api/account/delivered", json={"key": "event-1"}).json()["send"] is True
    assert client.post("/api/account/delivered", json={"key": "event-1"}).json()["send"] is False


def test_cannot_read_or_mutate_without_login(client):
    """인증하지 않은 요청은 개인 기록을 조회·저장하지 못한다."""
    for path in ("/api/account/social", "/api/account/preferences"):
        assert client.get(path).status_code == 401
    assert client.put("/api/account/social", json={
        "revision": 0, "friendships": [], "shares": [], "receipts": {},
    }).status_code == 401
    assert client.patch("/api/account/preferences", json={"theme": "dark"}).status_code == 401
    assert client.post("/api/account/read", json={"keys": ["n"]}).status_code == 401


def test_saved_friendships_feed_ai_relation_graph(client):
    """서버에서 수락된 친구 연결이 AI 관계 그래프에 직접 반영된다."""
    from gyeongjosa_ai.dependencies import get_service

    assert client.post("/api/account/login", json={
        "username": "test1234", "password": "test1234",
    }).status_code == 200
    service = get_service()
    assert "LOCAL_TEST_FRIEND01" in service.data.graph["TEST1234"]
    assert "TEST1234" in service.data.graph["LOCAL_TEST_FRIEND01"]
