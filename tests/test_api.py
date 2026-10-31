"""가상 계정 API와 기능 선택 없는 웹 대화를 확인한다."""

from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app, get_service
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService


class TestGateway:
    """네트워크 없이 API 계약을 확인하는 응답 대역이다."""

    def classify(self, context, people_ids, notice_ids):
        return {"intent": "history", "person_id": "P001", "notice_id": None, "event_type": None, "model": "claude-opus-4-8"}

    def generate(self, context, allowed_ids, preferred_model=None):
        return {"answer": "확인한 기록을 참고해 주세요.", "evidence_ids": sorted(allowed_ids), "suggested_amount_krw": None, "model": "claude-opus-4-8"}


def test_local_api_and_web_contract():
    service = ChatService(load_data(), TestGateway())
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            root = client.get("/")
            assert root.status_code == 200
            assert "가상" in root.text and "질문" in root.text
            assert 'name="mode"' not in root.text
            assert client.get("/api/health").json()["status"] == "ok"
            users = client.get("/api/users").json()["users"]
            assert len(users) == 118
            assert any(item["id"] == "TEST1234" for item in users)
            notices = client.get("/api/users/U001/notices").json()["notices"]
            assert {item["notice"]["id"] for item in notices} == {"N001", "N002"}
            assert all(item["notice"]["id"] != "N003" for item in notices)
            assert client.get("/api/users/UNKNOWN/people").status_code == 404
            response = client.post("/api/chat", json={"user_id": "U001", "question": "해든기획팀 김도윤과 주고받은 기록"})
            assert response.status_code == 200
            assert response.json()["status"] == "answer"
            assert response.json()["intent"] == "history"
    finally:
        app.dependency_overrides.clear()
