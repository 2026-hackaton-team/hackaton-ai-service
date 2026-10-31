"""Read-only integration contract smoke tests (no Codyssey calls)."""
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from gyeongjosa_ai import integration_api
from gyeongjosa_ai.api import app

def test_unselected_demo_account_cannot_see_conversations():
    with TestClient(app) as c:
        assert c.get("/api/conversations").status_code == 401
        assert c.get("/api/workspace").status_code == 401
        assert c.get("/api/notices").status_code == 401

def test_demo_accounts_and_single_process_health():
    with TestClient(app) as c:
        users=c.get("/api/demo/users")
        assert users.status_code == 200
        assert users.json()["items"]
        assert c.get("/api/health").status_code == 200

def test_private_conversations_persist_and_are_account_scoped(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        monkeypatch.setattr(integration_api, "_DB", Path(directory) / "conversations.sqlite")
        with TestClient(app) as c:
            users=c.get("/api/demo/users").json()["items"]
            assert len(users)>=2
            a,b=users[0]["id"],users[1]["id"]
            headers_a={"X-Demo-User-Id":a}
            headers_b={"X-Demo-User-Id":b}
            result=c.post("/api/conversations",headers=headers_a)
            assert result.status_code==201
            cid=result.json()["id"]
            assert c.get(f"/api/conversations/{cid}",headers=headers_a).status_code==200
            assert c.get(f"/api/conversations/{cid}",headers=headers_b).status_code==404
            assert c.delete(f"/api/conversations/{cid}",headers=headers_b).status_code==404
            assert len(c.get("/api/conversations",headers=headers_a).json()["items"])==1
            assert c.delete(f"/api/conversations/{cid}",headers=headers_a).status_code==204
            assert c.get(f"/api/conversations/{cid}",headers=headers_a).status_code==404

def test_notice_access_requires_explicit_sharing():
    with TestClient(app) as c:
        users=c.get("/api/demo/users").json()["items"]
        h={"X-Demo-User-Id":users[0]["id"]}
        assert c.get("/api/notices/unknown",headers=h).status_code==404
        assert c.get("/api/notices",headers=h).status_code==200
