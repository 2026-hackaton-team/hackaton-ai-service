"""서버 회원가입·로그인과 회원 작업공간 접근을 검증한다."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app


SIGNUP = {"username": "Hong_gd", "name": "홍길동", "password": "secret123", "phone": "010-1234-5678",
          "email": "Hong@Example.com", "workplace": "마음전자", "organization": "", "workType": "일반 회사원",
          "visibility": "전체 공개"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GYEONGJOSA_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "personal.sqlite3"))
    with TestClient(app) as value:
        value.db_path = tmp_path / "accounts.sqlite3"
        yield value


def _auth(token):
    return {"Authorization": "Bearer " + token}


def test_signup_stores_account_in_sqlite_without_plain_password(client):
    response = client.post("/api/auth/signup", json=SIGNUP)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["profile"]["username"] == "hong_gd"
    assert body["profile"]["email"] == "hong@example.com"
    assert body["profile"]["phone"] == "01012345678"
    assert body["workspaceOwner"] == "ACC:hong_gd"
    assert "password" not in str(body["profile"])
    with sqlite3.connect(client.db_path) as db:
        row = db.execute("SELECT password_hash, password_salt FROM accounts WHERE username='hong_gd'").fetchone()
        sessions = db.execute("SELECT token_hash FROM sessions").fetchall()
    assert row and "secret123" not in row[0] and len(row[1]) == 32
    assert sessions and sessions[0][0] != body["token"]


@pytest.mark.parametrize("change,status", [
    ({"username": "HONG_GD", "email": "other@example.com"}, 409),
    ({"username": "other_id", "email": "hong@example.com"}, 409),
    ({"username": "ab"}, 400),
    ({"password": "short"}, 400),
    ({"username": "test1234"}, 400),
    ({"workType": "없는 직무"}, 400),
])
def test_signup_rejects_duplicates_and_invalid_input(client, change, status):
    assert client.post("/api/auth/signup", json=SIGNUP).status_code == 201
    assert client.post("/api/auth/signup", json={**SIGNUP, **change}).status_code == status


def test_login_me_update_and_logout(client):
    client.post("/api/auth/signup", json=SIGNUP)
    assert client.post("/api/auth/login", json={"username": "hong_gd", "password": "wrong-pass"}).status_code == 401
    token = client.post("/api/auth/login", json={"username": " HONG_gd ", "password": "secret123"}).json()["token"]
    assert client.get("/api/auth/me", headers=_auth(token)).json()["profile"]["name"] == "홍길동"

    update = {k: SIGNUP[k] for k in ("phone", "email", "workplace", "organization", "workType", "visibility")}
    wrong = client.put("/api/auth/me", headers=_auth(token), json={**update, "password": "newpass123", "currentPassword": "nope"})
    assert wrong.status_code == 400
    saved = client.put("/api/auth/me", headers=_auth(token),
                       json={**update, "visibility": "비공개", "password": "newpass123", "currentPassword": "secret123"})
    assert saved.status_code == 200 and saved.json()["profile"]["visibility"] == "비공개"
    assert client.post("/api/auth/login", json={"username": "hong_gd", "password": "newpass123"}).status_code == 200

    assert client.post("/api/auth/logout", headers=_auth(token)).status_code == 204
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401


def test_test_account_is_created_on_first_login_only_with_demo_password(client):
    assert client.post("/api/auth/login", json={"username": "test1234", "password": "wrong"}).status_code == 401
    first = client.post("/api/auth/login", json={"username": "test1234", "password": "test1234"})
    assert first.status_code == 200 and first.json()["profile"]["name"] == "테스트 사용자"
    assert client.post("/api/auth/login", json={"username": "test1234", "password": "test1234"}).status_code == 200


def test_member_workspace_requires_its_own_session(client):
    token = client.post("/api/auth/signup", json=SIGNUP).json()["token"]
    other = client.post("/api/auth/signup", json={**SIGNUP, "username": "kim_cs", "email": "kim@example.com"}).json()["token"]
    mine = {"X-Demo-User-Id": "ACC:hong_gd", **_auth(token)}
    assert client.get("/api/workspace/personal", headers=mine).json()["initialized"] is False
    person = {"id": "P1", "name": "김철수", "relation": "친구", "interactions": []}
    saved = client.put("/api/workspace/personal", headers=mine,
                       json={"revision": 0, "people": [person], "events": [], "records": []})
    assert saved.status_code == 200, saved.text
    assert client.get("/api/workspace/personal", headers=mine).json()["people"][0]["name"] == "김철수"
    assert client.get("/api/workspace/personal", headers={"X-Demo-User-Id": "ACC:hong_gd"}).status_code == 401
    assert client.get("/api/workspace/personal", headers={"X-Demo-User-Id": "ACC:hong_gd", **_auth(other)}).status_code == 401
    assert client.get("/api/workspace/personal", headers={"X-Demo-User-Id": "U001"}).status_code == 200
