"""Read-only integration contract smoke tests (no Codyssey calls)."""
import tempfile
import sqlite3
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai import integration_api
from gyeongjosa_ai.api import app


def test_integration_api_can_be_imported_first(tmp_path):
    """모듈을 어느 순서로 불러도 같은 서비스 의존성을 사용한다."""
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "import app.profile_store as profiles\n"
        "profiles.ROOT = Path(sys.argv[1])\n"
        "(profiles.ROOT / 'data').mkdir()\n"
        "import gyeongjosa_ai.integration_api as integrated\n"
        "import gyeongjosa_ai.api as api\n"
        "assert integrated.get_service is api.get_service\n"
    )
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr


def test_conversation_connection_closes_and_rolls_back(tmp_path, monkeypatch):
    """대화 연결을 반환할 때 파일 잠금과 미완료 트랜잭션을 남기지 않는다."""
    monkeypatch.setattr(integration_api, "_DB", tmp_path / "conversations.sqlite")
    with pytest.raises(RuntimeError):
        with integration_api._connect() as db:
            db.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, ?)", ("test", "U001", "{}", "now", "now"))
            raise RuntimeError("저장 중단")
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("SELECT 1")
    with integration_api._connect() as reopened:
        assert reopened.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0

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
