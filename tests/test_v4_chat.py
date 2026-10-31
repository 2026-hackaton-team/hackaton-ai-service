"""자유 상담에서 가상 시나리오의 정책·금액 경계와 선택 권한을 검증한다."""
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from gyeongjosa_ai import integration_api
from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService


class UnusedGateway:
    """오프라인 시연이 별도의 LLM 응답을 요구하지 않는지 검사한다."""

    def classify(self, *_args, **_kwargs):
        raise AssertionError("가상 시연 분류에 외부 모델 호출 금지")

    def generate(self, *_args, **_kwargs):
        raise AssertionError("가상 시연 금액 계산에 외부 모델 호출 금지")


def chat(text, context=None, user_id="U001"):
    """같은 가상 계정의 대화 상태를 전달한다."""
    return ChatService(load_data(), UnusedGateway()).chat_auto({
        "user_id": user_id, "question": text, "context": context or {},
    })


def test_general_three_man_budget_is_hard_ceiling():
    result = chat("가상 시나리오: 직장 동료 김도윤 결혼식에 참석해 식사해요. 예산은 3만원이에요")
    assert result["status"] == "answer"
    assert result["v4_analysis"]["scenario"] == "general"
    assert result["v4_analysis"]["person_id"] == "P001"
    assert result["v4_analysis"]["status"] == "RECOMMENDED"
    assert 0 < result["suggested_amount_krw"] <= 30000
    assert result["context"]["budget_krw"] == 30000
    assert result["evidence"]


def test_budget_change_rechecks_candidates_instead_of_repeating_old_amount():
    first = chat("가상 시나리오: 직장 동료 결혼식에 참석해 식사해요. 예산은 3만원")
    next_result = chat("예산을 2만원으로 바꿔", first["context"])
    assert next_result["context"]["budget_krw"] == 20000
    assert next_result["v4_analysis"]["status"] == "NO_AFFORDABLE_CANDIDATE"
    assert next_result["suggested_amount_krw"] is None
    assert next_result["v4_analysis"]["amount_krw"] is None


def test_public_exception_is_conditional_and_constrained():
    result = chat("가상 시나리오: 공직자 부조 예외 성립 가정, 장례식 예산은 10만원")
    analysis = result["v4_analysis"]
    assert analysis["scenario"] == "public_exception"
    assert analysis["person_id"] == "P004"
    assert analysis["legal_assessment"]["status"] == "CONDITIONALLY_ALLOWED"
    assert analysis["legal_assessment"]["is_hypothetical"] is True
    assert analysis["amount_krw"] is not None
    assert analysis["amount_krw"] <= 50000


def test_procurement_risk_never_becomes_payment_advice():
    result = chat("가상 시나리오: 계약 심사 거래처 직원의 부친상, 예산은 3만원")
    analysis = result["v4_analysis"]
    assert analysis["scenario"] == "procurement"
    assert analysis["person_id"] == "P005"
    assert analysis["status"] == "POTENTIALLY_PROHIBITED"
    assert analysis["amount_krw"] is None
    assert result["suggested_amount_krw"] is None
    assert "보류" in result["message"]


def test_unmarked_work_context_requires_fictional_confirmation():
    pending = chat("저는 심사하는 거래처의 부친상에 가고 싶어요.")
    assert pending["status"] == "need_more_info"
    assert pending["pending_field"] == "v4_scenario"
    assert pending["options"][0]["id"] == "procurement"
    assert pending["context"].get("v4_scenario") is None


def test_scenario_change_does_not_reuse_other_person_budget():
    first = chat("가상 시나리오: 직장 동료 결혼식에 참석해 식사해요. 예산은 3만원")
    prompt = chat("이번엔 계약 심사 거래처의 부친상이야", first["context"])
    assert prompt["status"] == "need_more_info"
    assert prompt["pending_field"] == "v4_scenario"
    assert prompt["context"].get("budget_krw") is None
    selected = chat("가상 계약 심사 시나리오로 전환", {"v4_scenario": "procurement"})
    assert selected["v4_analysis"]["status"] == "POTENTIALLY_PROHIBITED"
    assert selected["context"].get("budget_krw") is None


def test_unknown_and_other_account_cannot_link_u001_private_people():
    result = chat("가상 시나리오: 계약 심사 거래처 부친상", user_id="U002")
    assert "v4_analysis" not in result
    assert result["status"] == "need_more_info"
    assert "U001" in result["message"]


def test_unrelated_question_not_forced_into_existing_v4_state():
    from gyeongjosa_ai.v4_chat import try_v4_chat
    first = chat("가상 시나리오: 직장 동료 결혼식에 참석해 식사해요. 예산은 3만원")
    assert try_v4_chat("U001", "오늘 날씨 어때?", first["context"]) is None


def test_v4_scenario_choice_is_conversation_scoped_and_validated(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        monkeypatch.setattr(integration_api, "_DB", Path(directory) / "chat.sqlite3")
        with TestClient(app) as client:
            headers = {"X-Demo-User-Id": "U001"}
            cid = client.post("/api/conversations", headers=headers).json()["id"]
            endpoint = f"/api/conversations/{cid}/messages"
            first = client.post(endpoint, headers=headers, json={
                "requestId": "request-one", "text": "직장 동료 결혼식 예산은 3만원",
            })
            assert first.status_code == 200, first.text
            assert first.json()["pending_field"] == "v4_scenario"
            invalid = client.post(endpoint, headers=headers, json={
                "requestId": "request-two", "text": "가상 시나리오",
                "selection": {"field": "v4_scenario", "value": "public_procurement"},
            })
            assert invalid.status_code == 403
            selected = client.post(endpoint, headers=headers, json={
                "requestId": "request-three", "text": "가상 직장 동료 결혼식",
                "selection": {"field": "v4_scenario", "value": "general"},
            })
            assert selected.status_code == 200, selected.text
            assert selected.json()["pending_field"] == "v4_attendance"
            fake_attendance = client.post(endpoint, headers=headers, json={
                "requestId": "request-four", "text": "모름",
                "selection": {"field": "v4_attendance", "value": "admin"},
            })
            assert fake_attendance.status_code == 422
            attended = client.post(endpoint, headers=headers, json={
                "requestId": "request-five", "text": "참석하여 식사",
                "selection": {"field": "v4_attendance", "value": "yes"},
            })
            assert attended.status_code == 200, attended.text
            assert attended.json()["pending_field"] == "budget_krw"
            budget = client.post(endpoint, headers=headers, json={
                "requestId": "request-six", "text": "예산 3만원",
                "selection": {"field": "budget_krw", "value": 30000},
            })
            assert budget.status_code == 200, budget.text
            assert budget.json()["v4_analysis"]["amount_krw"] <= 30000
            assert client.get(f"/api/conversations/{cid}", headers=headers).json()["state"]["v4_scenario"] == "general"
            assert client.get(f"/api/conversations/{cid}", headers={"X-Demo-User-Id": "U002"}).status_code == 404
