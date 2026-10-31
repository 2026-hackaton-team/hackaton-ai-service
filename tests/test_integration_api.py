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


def test_conversation_api_recalculates_budget_after_no_cash_candidate(tmp_path, monkeypatch):
    """실제 대화 API와 SQLite 상태에서 999원에서 99,999원으로 수정한다."""
    from gyeongjosa_ai.dependencies import get_service
    from gyeongjosa_ai.data import load_data
    from gyeongjosa_ai.service import ChatService

    class SessionGateway:
        """최초 상담만 금액 의도로 분류하는 모델 대역이다."""

        def __init__(self):
            self.classify_calls = 0
            self.answer_contexts = []

        def classify(self, context, people_ids, notice_ids):
            self.classify_calls += 1
            return {"intent": "amount" if self.classify_calls == 1 else "out_of_scope",
                    "person_id": None, "notice_id": None,
                    "event_type": "장례" if self.classify_calls == 1 else None,
                    "model": "test-model", "requested_aspects": []}

        def generate(self, context, allowed_ids, preferred_model=None):
            self.answer_contexts.append(context)
            return {"answer": "검은색의 단정한 복장으로 방문하고 유족에게 짧게 위로를 전하세요.",
                    "evidence_ids": sorted(allowed_ids),
                    "suggested_amount_krw": None, "model": "test-model"}

    gateway = SessionGateway()
    service = ChatService(load_data(), gateway)
    monkeypatch.setattr(integration_api, "_DB", tmp_path / "conversation.sqlite")
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            headers = {"X-Demo-User-Id": "U001"}
            created = client.post("/api/conversations", headers=headers)
            assert created.status_code == 201
            cid = created.json()["id"]

            def send(text, index):
                response = client.post(f"/api/conversations/{cid}/messages", headers=headers,
                                       json={"requestId": f"message-{index}", "text": text})
                assert response.status_code == 200, response.text
                return response.json()

            first = send("회사 동료 부친상, 조의금과 조문 예절이 궁금해", 1)
            assert first["pending_field"] == "person_id"
            second = send("해든기획팀 김도윤", 2)
            assert second["pending_field"] == "budget_krw"
            low = send("999", 3)
            assert low["status"] == "answer"
            assert low["budget_analysis"]["budget_krw"] == 999
            assert low["suggested_amount_krw"] is None
            assert "위로" in low["message"]
            high = send("99999", 4)
            assert high["status"] == "answer"
            assert high["context"]["budget_krw"] == 99999
            assert high["budget_analysis"]["budget_krw"] == 99999
            assert "예산 99,999원" in high["message"]
            assert high["suggested_amount_krw"] is None or high["suggested_amount_krw"] <= 99999
            assert "위로" in high["message"]
            assert gateway.classify_calls == 3
            saved = client.get(f"/api/conversations/{cid}", headers=headers)
            assert saved.status_code == 200
            assert saved.json()["state"]["budget_krw"] == 99999
            assert saved.json()["state"]["requested_aspects"] == ["amount", "funeral_etiquette"]
    finally:
        app.dependency_overrides.pop(get_service, None)
