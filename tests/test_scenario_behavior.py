"""새 가상 인물과 소식으로 주요 경계 동작을 검증한다."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.ai import ModelUnavailable, parse_response
from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService


CASES = json.loads((Path(__file__).resolve().parents[1] / "data" / "scenario_cases.json").read_text(encoding="utf-8-sig"))["scenarios"]


class ScenarioGateway:
    """실제 모델 호출 없이 시나리오의 서버 분기를 확인한다."""

    def __init__(self, intent="history", person_id="SCP001", notice_id=None, fail=False):
        self.intent = intent
        self.person_id = person_id
        self.notice_id = notice_id
        self.fail = fail
        self.generated = []

    def classify(self, context, people_ids, notice_ids):
        return {"intent": self.intent, "person_id": self.person_id, "notice_id": self.notice_id,
                "event_type": None, "model": "시나리오 대역"}

    def generate(self, context, allowed_ids, preferred_model=None):
        if self.fail:
            raise ModelUnavailable("가상 모델 연결 실패")
        self.generated.append(context)
        return {"answer": "확인된 기록을 살펴보세요.", "evidence_ids": sorted(allowed_ids),
                "suggested_amount_krw": None, "model": "시나리오 대역"}


@pytest.mark.parametrize("case", [item for item in CASES if item["primary_group"] == "기존 행사"], ids=lambda item: item["id"])
def test_existing_event_scenarios_return_their_own_evidence(case):
    gateway = ScenarioGateway()
    contract = case["execution"]
    result = ChatService(load_data(), gateway).chat(contract["request"])
    assert contract["target"] == "ChatService.chat"
    assert result["status"] == contract["expected_status"]
    assert set(case["expected"]["evidence_ids"]) <= {item["id"] for item in result["evidence"]}
    assert gateway.generated[0]["history"]["person_id"] == contract["request"]["person_id"]
    assert all(item["contact_person_id"] == contract["request"]["person_id"]
               for item in gateway.generated[0]["history"]["transactions"])


def test_same_name_requires_selection_before_a_history_answer():
    gateway = ScenarioGateway()
    result = ChatService(load_data(), gateway).chat_auto({
        "user_id": "SCU001", "question": "김가람과 주고받은 내역을 보여줘."
    })
    assert result["status"] == "need_more_info"
    assert result["pending_field"] == "person_id"
    assert {item["id"] for item in result["options"]} == {"SCP001", "SCP002"}
    assert gateway.generated == []


def test_mourner_requires_confirmation_even_when_name_and_affiliation_match():
    gateway = ScenarioGateway()
    result = ChatService(load_data(), gateway).chat({
        "user_id": "SCU001", "mode": "history", "question": "상주의 기록을 보여줘",
        "notice_id": "SCN001", "person_id": "SCP001",
    })
    assert result["status"] == "need_more_info"
    assert result["pending_field"] == "person_confirmed"
    assert gateway.generated == []


def test_confirmed_history_keeps_received_and_paid_amounts_separate():
    gateway = ScenarioGateway()
    result = ChatService(load_data(), gateway).chat({
        "user_id": "SCU001", "mode": "history", "question": "직장 동료 김가람의 이력",
        "person_id": "SCP001",
    })
    assert result["status"] == "answer"
    assert "받은 금액 170,000원" in result["message"]
    assert "낸 금액 100,000원" in result["message"]
    assert {"SCT001", "SCT005", "SCT006", "SCT025"} <= {item["id"] for item in result["evidence"]}
    assert all(item["contact_person_id"] == "SCP001" for item in gateway.generated[0]["history"]["transactions"])


def test_zero_budget_and_missing_history_do_not_produce_an_amount():
    gateway = ScenarioGateway()
    service = ChatService(load_data(), gateway)
    zero = service.chat({"user_id": "SCU001", "mode": "amount", "question": "0원이에요",
                         "person_id": "SCP001", "event_type": "장례", "budget_krw": 0})
    missing = service.chat({"user_id": "SCU002", "mode": "amount", "question": "얼마가 좋을까요?",
                            "person_id": "SCP004", "event_type": "팔순", "budget_krw": 30000})
    assert zero["status"] == "answer" and zero["suggested_amount_krw"] is None
    assert missing["status"] == "answer" and missing["suggested_amount_krw"] is None
    assert "금액 이력" in missing["message"]
    assert gateway.generated == []


def test_ambiguous_budget_followup_does_not_turn_into_a_zero_budget():
    gateway = ScenarioGateway(intent="amount", notice_id="SCN001")
    service = ChatService(load_data(), gateway)
    first = service.chat_auto({"user_id": "SCU001", "question": "얼마를 내면 좋을까?",
                               "context": {"person_id": "SCP001", "notice_id": "SCN001", "person_confirmed": True}})
    assert first["pending_field"] == "budget_krw"
    followup = service.chat_auto({"user_id": "SCU001", "question": "없어", "context": first["context"]})
    assert followup["pending_field"] == "budget_clarification"
    assert followup["context"].get("budget_krw") is None
    final = service.chat_auto({"user_id": "SCU001", "question": "지금은 지출이 어려워요", "context": followup["context"]})
    assert final["status"] == "answer" and final.get("suggested_amount_krw") is None
    assert gateway.generated == []


@pytest.mark.parametrize("notice_id", ["SCN003", "SCN004", "SCN005", "SCN006", "SCN007"])
def test_unavailable_notice_is_not_returned_by_api(notice_id):
    with TestClient(app) as client:
        result = client.get(f"/api/notices/{notice_id}", headers={"X-Demo-User-Id": "SCU001"})
        assert result.status_code == 404
        assert "비공개상주" not in result.text


def test_new_accounts_are_available_to_demo_api_without_changing_old_notice_results():
    with TestClient(app) as client:
        users = client.get("/api/demo/users").json()["items"]
        assert {f"SCU{i:03}" for i in range(1, 7)} <= {item["id"] for item in users}
        notices = client.get("/api/notices", headers={"X-Demo-User-Id": "U001"}).json()["items"]
        assert {item["notice"]["id"] for item in notices} == {"N001", "N002"}
        new_notices = client.get("/api/notices", headers={"X-Demo-User-Id": "SCU001"}).json()["items"]
        assert {"SCN001", "SCN002"} <= {item["notice"]["id"] for item in new_notices}


def test_wrong_owner_cannot_request_another_persons_history():
    gateway = ScenarioGateway()
    result = ChatService(load_data(), gateway).chat({
        "user_id": "SCU002", "mode": "history", "question": "거래 내역을 보여줘", "person_id": "SCP001"
    })
    assert result["status"] == "error" and result["evidence"] == []
    assert gateway.generated == []


def test_provider_failure_does_not_create_a_successful_answer():
    gateway = ScenarioGateway(fail=True)
    result = ChatService(load_data(), gateway).chat({
        "user_id": "SCU005", "mode": "history", "question": "이수안 생일 이력",
        "person_id": "SCP015",
    })
    assert result["status"] == "error"
    assert result["model"] is None and result["evidence"] == []


def test_model_output_rejects_unknown_evidence_and_over_budget_amount():
    context = {"mode": "amount", "budget_krw": 30000,
               "history": {"transactions": [{"id": "SCT001", "amount_krw": 100000}]}}
    unknown = json.dumps({"answer": "확인했습니다.", "evidence_ids": ["SCT001", "SCT999"], "suggested_amount_krw": 30000})
    over_budget = json.dumps({"answer": "확인했습니다.", "evidence_ids": ["SCT001"], "suggested_amount_krw": 100000})
    with pytest.raises(ValueError):
        parse_response(unknown, context, {"SCT001"})
    with pytest.raises(ValueError):
        parse_response(over_budget, context, {"SCT001"})
