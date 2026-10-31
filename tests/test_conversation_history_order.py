"""최근 대화 8개가 시간순으로 다음 상담에 전달되는지 API 경로로 확인한다."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai import integration_api
from gyeongjosa_ai.api import app
from gyeongjosa_ai.dependencies import get_service


@pytest.mark.parametrize("same_timestamp", [False, True])
def test_chat_passes_latest_eight_messages_in_chronological_order(tmp_path, monkeypatch, same_timestamp):
    """오래된 턴 제외, 역할 순서, 같은 시각의 삽입 순서를 함께 검사한다."""
    received = []

    class RecordingService:
        data = SimpleNamespace(users={"U001": {}})

        def chat_auto(self, request):
            received.append(request["history"])
            return {"status": "answer", "message": "다음 응답", "context": {}}

    monkeypatch.setattr(integration_api, "_DB", tmp_path / "conversations.sqlite3")
    monkeypatch.setattr(integration_api, "load_workspace", lambda _uid: {"initialized": False})
    monkeypatch.setenv("GYEONGJOSA_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setitem(app.dependency_overrides, get_service, lambda: RecordingService())
    with integration_api._connect() as db:
        db.execute("INSERT INTO conversations VALUES (?,?,?,?,?)",
                   ("history-case", "U001", "{}", "2026-11-01", "2026-11-01"))
        for turn in range(1, 7):
            timestamp = "2026-11-01T00:00:00+00:00" if same_timestamp else f"2026-11-01T00:00:{turn:02d}+00:00"
            for role in ("user", "assistant"):
                db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (
                    f"{turn}-{role}", "history-case", f"request-{turn}" if role == "user" else None,
                    role, f"turn-{turn}-{role}", None, timestamp,
                ))
    with TestClient(app) as client:
        response = client.post("/api/conversations/history-case/messages",
                               headers={"X-Demo-User-Id": "U001"},
                               json={"requestId": "history-check", "text": "이어서 설명해 줘"})
    assert response.status_code == 200, response.text
    assert received == [[{"role": role, "content": f"turn-{turn}-{role}"}
                         for turn in range(3, 7) for role in ("user", "assistant")]]
