"""Presentation gate: observable routes and deterministic offline v4 scenarios.

No external LLM calls, credentials, or user-private data are required.
"""
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app
from app.main import app as policy_app

client = TestClient(app)
policy_client = TestClient(policy_app)


def _request(scenario="public_exception", budget=150_000):
    return {
        "demo_user_id": "U001",
        "person_id": "P001",
        "identity_confirmed": True,
        "event_type": "결혼",
        "attendance_with_meal": True,
        "budget_krw": budget,
        "scenario_id": scenario,
        "explanation_mode": "offline",
        "allow_llm_analysis": False,
    }


def test_presentation_main_server_and_v4_health():
    assert client.get("/api/health").json()["status"] == "ok"
    assert policy_client.get("/api/health").json()["policy_engine"] == "v4"


def test_presentation_single_chat_entry():
    """사용자 화면에서 별도 정책 분석 페이지를 제공하지 않는다."""
    assert client.get("/").status_code == 200
    assert client.get("/v4/").status_code == 404
    assert client.get("/v4/api/health").status_code == 404


def test_presentation_offline_budget_never_exceeded():
    response = policy_client.post("/api/recommend", json=_request("public_exception", budget=30_000))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "RECOMMENDED"
    assert result["amount_krw"] <= 30_000


def test_presentation_conditional_cap_is_not_universal_permission():
    response = policy_client.post("/api/recommend", json=_request("public_exception"))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "RECOMMENDED"
    assert result["amount_krw"] == 50_000
    assert result["legal_assessment"]["status"] == "CONDITIONALLY_ALLOWED"
    assert result["legal_assessment"]["is_hypothetical"] is True


def test_presentation_contract_conflict_holds_transfer():
    response = policy_client.post("/api/recommend", json=_request("public_procurement"))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "POTENTIALLY_PROHIBITED"
    assert "amount_krw" not in result


def test_presentation_account_selection_required_for_chat_history():
    assert client.get("/api/conversations").status_code == 401
