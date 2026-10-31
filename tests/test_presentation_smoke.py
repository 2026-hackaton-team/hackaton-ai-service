"""Presentation gate: observable routes and deterministic offline v4 scenarios.

No external LLM calls, credentials, or user-private data are required.
"""
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app

client = TestClient(app)


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
    assert client.get("/v4/api/health").json()["policy_engine"] == "v4"


def test_presentation_both_frontends_served():
    for path in ("/v4/", "/v4/app.js", "/v4/style.css"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)


def test_presentation_offline_budget_never_exceeded():
    response = client.post("/v4/api/recommend", json=_request("public_exception", budget=30_000))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "RECOMMENDED"
    assert result["amount_krw"] <= 30_000


def test_presentation_conditional_cap_is_not_universal_permission():
    response = client.post("/v4/api/recommend", json=_request("public_exception"))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "RECOMMENDED"
    assert result["amount_krw"] == 50_000
    assert result["legal_assessment"]["status"] == "CONDITIONALLY_ALLOWED"
    assert result["legal_assessment"]["is_hypothetical"] is True


def test_presentation_contract_conflict_holds_transfer():
    response = client.post("/v4/api/recommend", json=_request("public_procurement"))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "POTENTIALLY_PROHIBITED"
    assert "amount_krw" not in result


def test_presentation_account_selection_required_for_chat_history():
    assert client.get("/api/conversations").status_code == 401
