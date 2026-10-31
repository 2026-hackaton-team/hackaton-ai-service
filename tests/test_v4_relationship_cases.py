"""가상 감정·관계 시나리오 10개의 거래 해석·예산·개인정보 경계를 검증한다."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.relationship_insights import analyze_relationship_case
from gyeongjosa_ai.service import ChatService
from gyeongjosa_ai.v4_chat import SCENARIOS, try_v4_chat


class OfflineGateway:
    """오프라인 관계 사례가 외부 모델에 의존하면 테스트를 실패시킨다."""

    def classify(self, *_args, **_kwargs):
        raise AssertionError("외부 모델 호출 금지")

    def generate(self, *_args, **_kwargs):
        raise AssertionError("외부 모델 호출 금지")


def chat(text, context=None, user_id="U001"):
    """실제 서버의 자유 상담 로직으로 한 턴을 재현한다."""
    return ChatService(load_data(), OfflineGateway()).chat_auto({
        "user_id": user_id, "question": text, "context": context or {},
    })


def test_twenty_scenarios_and_63_private_transactions_are_registered():
    cases = [s for s in SCENARIOS.values() if s["id"].startswith("relation_")]
    assert len(SCENARIOS) == 20
    assert len(cases) == 10
    assert len({s["person_id"] for s in cases}) == 10
    dataset = load_data().dataset
    transactions = [t for t in dataset["transactions"] if t["id"].startswith("V4T")]
    assert len(transactions) == 63
    assert all(t["owner_user_id"] == "U001" for t in transactions)
    assert len({t["private_event_id"] for t in transactions}) == 63
    assert all(p["relationship_context"]["reference_provenance"] == "synthetic_comparison_not_survey"
               for p in dataset["people"] if p["id"] in {s["person_id"] for s in cases})


@pytest.mark.parametrize("case_id", [
    "relation_give_more", "relation_receive_more", "relation_close_friend",
    "relation_recent_large", "relation_recent_small", "relation_attendance",
    "relation_nonmonetary", "relation_drift", "relation_budget", "relation_peer_pressure",
])
def test_all_relationship_preset_questions_are_routed_to_their_own_person(case_id):
    result = chat(SCENARIOS[case_id]["example_question"])
    assert result["status"] == "answer"
    assert result["v4_analysis"]["scenario"] == case_id
    assert result["v4_analysis"]["person_id"] == SCENARIOS[case_id]["person_id"]
    assert result["v4_analysis"]["relationship_insights"]["paid_count"] >= 1
    assert result["evidence"]
    assert result["v4_analysis"]["demo_only"] is True
    assert "도덕적 의무" not in result["message"]


def test_asymmetric_giving_and_receiving_are_not_confused():
    giving = chat(SCENARIOS["relation_give_more"]["example_question"])
    receiving = chat(SCENARIOS["relation_receive_more"]["example_question"])
    for result, paid, received in ((giving, 100000, 50000), (receiving, 50000, 100000)):
        details = result["v4_analysis"]["relationship_insights"]
        assert details["paid_count"] == 4
        assert details["received_count"] == 4
        assert details["paid_average_krw"] == paid
        assert details["received_average_krw"] == received
        assert result["suggested_amount_krw"] is not None
        assert result["suggested_amount_krw"] <= 50000
    assert "의무" in receiving["message"]
    assert "인성" in giving["message"]


def test_recent_receipts_are_distinct_from_prior_average_and_intent_is_unknown():
    high = chat(SCENARIOS["relation_recent_large"]["example_question"])
    low = chat(SCENARIOS["relation_recent_small"]["example_question"])
    assert high["v4_analysis"]["status"] == "RELATIONSHIP_INSIGHT"
    assert low["v4_analysis"]["status"] == "RELATIONSHIP_INSIGHT"
    assert high["suggested_amount_krw"] is None
    assert low["suggested_amount_krw"] is None
    assert "200,000원" in high["message"] and "50,000원" in high["message"]
    assert "30,000원" in low["message"] and "100,000원" in low["message"]
    assert "확정할 수 없습니다" in high["message"]


def test_closeness_attendance_support_and_time_are_user_recorded_not_guesses():
    close = chat(SCENARIOS["relation_close_friend"]["example_question"])
    attendance = chat(SCENARIOS["relation_attendance"]["example_question"])
    support = chat(SCENARIOS["relation_nonmonetary"]["example_question"])
    drift = chat(SCENARIOS["relation_drift"]["example_question"])
    assert close["v4_analysis"]["relationship_insights"]["closeness_score"] == 5
    assert close["v4_analysis"]["amount_krw"] > close["v4_analysis"]["baseline_amount_krw"]
    assert any(row["signal"] == "closeness" for row in close["v4_analysis"]["relationship_adjustments"])
    assert "4/4회" in attendance["message"] and "0/4회" in attendance["message"]
    assert "이사할 때" in support["message"]
    assert "2025-04-30" in drift["message"]
    assert "인격" not in drift["message"]


def test_budget_uses_last_declared_budget_not_prior_amount_or_group_norm():
    budget = chat(SCENARIOS["relation_budget"]["example_question"])
    pressure = chat(SCENARIOS["relation_peer_pressure"]["example_question"])
    assert budget["context"]["budget_krw"] == 30000
    assert budget["suggested_amount_krw"] is not None
    assert budget["suggested_amount_krw"] <= 30000
    assert pressure["context"]["budget_krw"] == 50000
    assert pressure["suggested_amount_krw"] is not None
    assert pressure["suggested_amount_krw"] <= 50000
    assert "검증된 통계" in pressure["message"]


def test_followup_budget_updates_and_scenario_switch_does_not_reuse_prior_state():
    first = chat(SCENARIOS["relation_recent_large"]["example_question"])
    assert first["context"].get("budget_krw") is None
    second = chat("이번 예산을 3만원으로 바꿔", first["context"])
    assert second["context"]["budget_krw"] == 30000
    assert second["v4_analysis"]["status"] == "RECOMMENDED"
    assert second["suggested_amount_krw"] <= 30000
    third = chat("가상 시나리오: 상대가 늘 두 배를 준 관계야", second["context"])
    assert third["context"]["v4_scenario"] == "relation_receive_more"
    assert third["context"].get("budget_krw") is None
    assert third["v4_analysis"]["status"] == "RELATIONSHIP_INSIGHT"


def test_other_user_cannot_receive_relationship_history_or_private_notes():
    with pytest.raises(ValueError, match="계정"):
        analyze_relationship_case(user_id="U002", person_id="V4P011", scenario_id="relation_give_more")
    response = chat(SCENARIOS["relation_give_more"]["example_question"], user_id="U002")
    assert "relationship_insights" not in response
    assert "v4_analysis" not in response
    assert try_v4_chat("U002", SCENARIOS["relation_receive_more"]["example_question"], {})["context"] == {}


def test_api_exposes_grouped_twenty_presets_only_to_demo_account():
    with TestClient(app) as client:
        response = client.get("/api/demo/v4-scenarios", headers={"X-Demo-User-Id": "U001"})
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 20
        assert sum(item["category"] == "relationship" for item in items) == 10
        assert sum(item["category"] == "safety" for item in items) == 10
        assert client.get("/api/demo/v4-scenarios", headers={"X-Demo-User-Id": "U002"}).json()["items"] == []


def test_original_dashboard_is_not_inflated_by_relationship_fixtures():
    data = load_data()
    assert data.dashboard("U001")["paid_total_krw"] == 420000
    history = data.history("U001", "V4P011")
    assert history is not None
    assert len(history["transactions"]) == 8
    assert history["paid_total_krw"] == 400000
    assert history["received_total_krw"] == 200000


def test_existing_dataset_bytes_remain_unmodified():
    root = Path(__file__).resolve().parents[1] / "data"
    original = json.loads((root / "original_demo.json").read_text(encoding="utf-8"))
    generated = json.loads((root / "demo.json").read_text(encoding="utf-8"))
    for dataset in (original, generated):
        assert not any(p["id"].startswith("V4P") for p in dataset["people"])
        assert not any(t["id"].startswith("V4T") for t in dataset["transactions"])
