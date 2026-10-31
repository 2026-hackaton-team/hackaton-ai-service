"""서버 세션·친구 관계·알림 상태가 브라우저 저장 없이 유지되는지 검증한다."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app


ROOT = Path(__file__).resolve().parents[1]


def _signup(client, username, email=None):
    return client.post("/api/auth/signup", json={
        "username": username, "name": username + " 사용자", "password": "a_secure_demo_password",
        "phone": "01012345678", "email": email or username + "@example.invalid",
        "workplace": "", "organization": "", "workType": "일반 회사원", "visibility": "전체 공개",
    })


@pytest.fixture
def client(tmp_path, monkeypatch):
    """시드 데이터에 영향을 주지 않는 독립 사용자 DB를 사용한다."""
    monkeypatch.setenv("GYEONGJOSA_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    from gyeongjosa_ai.dependencies import get_service
    get_service.cache_clear()
    with TestClient(app) as session:
        yield session
    get_service.cache_clear()


def test_login_session_cookie_and_logout(client):
    """세션 쿠키에 저장된 식별자만으로 사용자 기록을 복원한다."""
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"username": "test1234", "password": "wrong1234"}).status_code == 401
    login = client.post("/api/auth/login", json={"username": "test1234", "password": "test1234"})
    assert login.status_code == 200
    assert login.json()["userId"] == "TEST1234"
    assert login.cookies.get("maeum_session")
    assert client.get("/api/auth/me").json()["profile"]["username"] == "test1234"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_signup_and_preferences_survive_new_session(client):
    """새 계정과 설정을 서버에 저장하고 재로그인 후 복원한다."""
    response = _signup(client, "newuser")
    assert response.status_code == 201, response.text
    assert response.json()["userId"] == "ACC:newuser"
    assert _signup(client, "newuser").status_code == 409
    assert client.patch("/api/account/preferences", json={"theme": "dark", "sidebarCollapsed": True}).status_code == 200
    read = client.post("/api/account/read", json={"keys": ["notice-1", "notice-2"]})
    assert read.json()["readIds"] == ["notice-1", "notice-2"]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/login", json={"username": "newuser", "password": "a_secure_demo_password"}).status_code == 200
    prefs = client.get("/api/account/preferences").json()
    assert prefs["theme"] == "dark" and prefs["sidebarCollapsed"] is True
    assert prefs["readIds"] == ["notice-1", "notice-2"]


def test_new_and_test_accounts_start_empty(client):
    """test1234와 새 계정 모두 친구·공유·인맥·일정·장부 없이 시작한다."""
    assert client.post("/api/auth/login", json={"username": "test1234", "password": "test1234"}).status_code == 200
    social = client.get("/api/account/social").json()
    assert social["social"] == {"friendships": [], "shares": [], "receipts": {}}
    assert [member["username"] for member in social["members"]] == ["test1234"]
    workspace = client.get("/api/workspace/personal", headers={"X-Demo-User-Id": "TEST1234"}).json()
    assert workspace["people"] == workspace["events"] == workspace["records"] == []
    user_id = _signup(client, "blank_user").json()["userId"]
    mine = client.get("/api/workspace/personal", headers={"X-Demo-User-Id": user_id}).json()
    assert mine["initialized"] is False
    assert mine["people"] == mine["events"] == mine["records"] == []


def test_members_directory_hides_contact_details(client):
    _signup(client, "first_user")
    members = client.get("/api/account/social").json()["members"]
    assert members[0]["username"] == "first_user"
    assert "phone" not in members[0] and "email" not in members[0]


def test_social_cas_and_notification_dedup(client):
    """동시 쓰기 충돌은 덮어쓰지 않고 알림은 중복 기록하지 않는다."""
    _signup(client, "cas_user")
    social = client.get("/api/account/social").json()
    patch = {"revision": social["revision"], **social["social"]}
    assert client.put("/api/account/social", json=patch).status_code == 200
    assert client.put("/api/account/social", json=patch).status_code == 409
    assert client.post("/api/account/delivered", json={"key": "event-1"}).json()["send"] is True
    assert client.post("/api/account/delivered", json={"key": "event-1"}).json()["send"] is False


def test_cannot_read_or_mutate_without_login(client):
    """인증하지 않은 요청은 개인 기록을 조회·저장하지 못한다."""
    for path in ("/api/account/social", "/api/account/preferences"):
        assert client.get(path).status_code == 401
    assert client.put("/api/account/social", json={"revision": 0, "friendships": [], "shares": [], "receipts": {}}).status_code == 401
    assert client.patch("/api/account/preferences", json={"theme": "dark"}).status_code == 401
    assert client.post("/api/account/read", json={"keys": ["n"]}).status_code == 401
    assert client.get("/api/workspace/personal").status_code == 401


def test_saved_friendships_feed_ai_relation_graph(client):
    """서버에서 수락된 친구 연결이 AI 관계 그래프에 직접 반영된다."""
    from gyeongjosa_ai.dependencies import get_service
    _signup(client, "friend_one")
    client.post("/api/auth/login", json={"username": "test1234", "password": "test1234"})
    social = client.get("/api/account/social").json()
    link = {"id": "link-1", "from": "test1234", "to": "friend_one", "status": "accepted", "createdAt": "2026-10-31T00:00:00Z"}
    assert client.put("/api/account/social", json={"revision": social["revision"], "friendships": [link],
                                                    "shares": [], "receipts": {}}).status_code == 200
    graph = get_service().data.graph
    assert "ACC:friend_one" in graph["TEST1234"]
    assert "TEST1234" in graph["ACC:friend_one"]


def test_reserved_demo_username_cannot_be_claimed(client):
    """시연 계정의 기존 데이터 소유자를 회원가입으로 빼앗지 못한다."""
    assert _signup(client, "test1234").status_code == 400
    assert client.post("/api/auth/login", json={"username": "test1234", "password": "test1234"}).status_code == 200


@pytest.mark.parametrize("path", [
    "frontend/src/App.jsx",
    "frontend/src/Forms.jsx",
    "frontend/src/IntegratedAIPage.jsx",
    "frontend/src/Notifications.jsx",
    "frontend/src/Social.jsx",
    "frontend/src/SharedEventsPanel.jsx",
    "frontend/src/services/demoApi.js",
])
def test_active_react_views_do_not_access_browser_storage(path):
    """사용 중인 화면이 브라우저 영속 저장소에 접근하지 않도록 보장한다."""
    source = (ROOT / path).read_text(encoding="utf-8")
    assert "localStorage" not in source
    assert "sessionStorage" not in source
