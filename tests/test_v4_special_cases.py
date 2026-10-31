"""신규 일곱 가지 가상 경조사 시나리오와 데이터·법적 안전 경계를 검증한다."""
import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app as v4_app
from app.special_cases import assess_special
from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.special_fixtures import merge_special_fixtures
from gyeongjosa_ai.v4_chat import SCENARIOS
from gyeongjosa_ai.service import ChatService


ROOT = Path(__file__).resolve().parents[1]


class OfflineGateway:
    """시나리오 검증 중 외부 모델 호출을 허용하지 않는다."""

    def classify(self, *_args, **_kwargs):
        raise AssertionError("외부 모델을 호출하면 안 됩니다.")

    def generate(self, *_args, **_kwargs):
        raise AssertionError("외부 모델을 호출하면 안 됩니다.")


def chat(question, context=None):
    """가상 시연 채팅 한 턴을 실행한다."""
    return ChatService(load_data(), OfflineGateway()).chat_auto({
        "user_id": "U001", "question": question, "context": context or {},
    })


def test_ten_scenarios_have_distinct_synthetic_person_mapping():
    assert len(SCENARIOS) == 20
    assert {key for key in SCENARIOS if not key.startswith("relation_") and key not in ("general", "public_exception", "procurement")} == {
        "teacher_parent", "sender_public", "private_occupation", "cash_and_wreath",
        "public_dol", "duplicate_mourner", "ended_contract",
    }
    dataset = load_data()
    expected = {f"V4P{i:03}" for i in range(1, 7)}
    assert expected <= {person["id"] for person in dataset.people("U001")}
    for person_id in expected:
        assert not any(person["id"] == person_id for person in dataset.people("U002"))
    assert len({s["person_id"] for s in SCENARIOS.values()}) == 19


def test_original_datasets_remain_unchanged_and_new_links_are_valid():
    original = json.loads((ROOT / "data" / "original_demo.json").read_text(encoding="utf-8"))
    untouched = copy.deepcopy(original)
    combined = merge_special_fixtures(original)
    assert original == untouched
    for key, n in (("users", 16), ("people", 16), ("friendships", 16),
                   ("private_events", 79), ("transactions", 63), ("shared_notices", 0)):
        assert len(combined[key]) == len(original[key]) + n
        assert len({entry["id"] for entry in combined[key]}) == len(combined[key])
    assert all(person["owner_user_id"] == "U001" for person in combined["people"] if person["id"].startswith("V4P"))


def test_teacher_parent_holds_even_three_man():
    result = chat(SCENARIOS["teacher_parent"]["example_question"])
    assert result["v4_analysis"]["scenario"] == "teacher_parent"
    assert result["v4_analysis"]["status"] == "POTENTIALLY_PROHIBITED"
    assert result["suggested_amount_krw"] is None
    assert "ACRC-TEACHER-PARENT" in {row["id"] for row in result["evidence"]}


def test_sender_public_private_recipient_requires_own_job_review():
    result = chat(SCENARIOS["sender_public"]["example_question"])
    assert result["v4_analysis"]["status"] == "NEEDS_EXPERT_REVIEW"
    assert result["v4_analysis"]["person_id"] == "V4P002"
    assert result["v4_analysis"]["legal_assessment"]["sender_profile_used"] is True
    assert result["suggested_amount_krw"] is None


def test_private_job_is_not_used_without_consent():
    result = chat(SCENARIOS["private_occupation"]["example_question"])
    assert result["v4_analysis"]["person_id"] == "V4P003"
    assert result["v4_analysis"]["status"] == "NEEDS_FACTS"
    assert result["v4_analysis"]["legal_assessment"]["profile_access"] in ("not_authorized", "not_shared")
    assert result["suggested_amount_krw"] is None
    assert not any("실제 직업" in row["text"] for row in result["evidence"])


def test_combined_cash_and_wreath_total_is_constrained():
    excessive = chat(SCENARIOS["cash_and_wreath"]["example_question"])
    assert excessive["v4_analysis"]["status"] == "POTENTIALLY_PROHIBITED"
    assert excessive["suggested_amount_krw"] is None
    assert "150,000원" in excessive["message"]
    safe = chat("가상 시나리오: 직무 관련 공직자 조의금 5만원과 조화 5만원")
    assert safe["v4_analysis"]["scenario"] == "cash_and_wreath"
    assert safe["v4_analysis"]["status"] == "CONDITIONALLY_ALLOWED"
    assert safe["suggested_amount_krw"] is None
    assert assess_special("cash_and_wreath", cash_krw=50001, wreath_krw=49999)["status"] == "POTENTIALLY_PROHIBITED"
    assert assess_special("cash_and_wreath", cash_krw=50000, wreath_krw=50000)["status"] == "CONDITIONALLY_ALLOWED"


def test_public_dol_does_not_get_wedding_ceremony_exception():
    result = chat(SCENARIOS["public_dol"]["example_question"])
    assert result["v4_analysis"]["scenario"] == "public_dol"
    assert result["v4_analysis"]["status"] == "NEEDS_EXPERT_REVIEW"
    assert result["suggested_amount_krw"] is None
    assert "돌잔치" in result["message"]
    assert "ACRC-DOL-EXCEPTION" in {row["id"] for row in result["evidence"]}


def test_duplicate_mourner_requires_explicit_person_selection():
    first = chat(SCENARIOS["duplicate_mourner"]["example_question"])
    assert first["pending_field"] == "v4_person"
    assert {row["id"] for row in first["options"]} == {"P001", "P002"}
    assert "v4_analysis" not in first
    state = {**first["context"], "v4_person": "P001"}
    confirmed = chat("직장 동료 김도윤을 선택했어요", state)
    assert confirmed["v4_analysis"]["person_id"] == "P001"


def test_ended_contract_does_not_prove_current_relation_is_none():
    result = chat(SCENARIOS["ended_contract"]["example_question"])
    assert result["v4_analysis"]["scenario"] == "ended_contract"
    assert result["v4_analysis"]["status"] in ("NEEDS_FACTS", "NEEDS_EXPERT_REVIEW")
    assert result["suggested_amount_krw"] is None
    assert result["v4_analysis"]["legal_assessment"]["relationship_status"] != "confirmed_by_user"


def test_api_lists_ten_only_for_designated_demo_account():
    with TestClient(app) as client:
        rows = client.get("/api/demo/v4-scenarios", headers={"X-Demo-User-Id": "U001"})
        assert rows.status_code == 200
        assert len(rows.json()["items"]) == 20
        other = client.get("/api/demo/v4-scenarios", headers={"X-Demo-User-Id": "U002"})
        assert other.json()["items"] == []


def test_v4_original_preset_options_do_not_expose_chat_only_scenarios():
    with TestClient(v4_app) as client:
        ids = [row["id"] for row in client.get("/api/demo/scenarios", params={"person_id": "V4P004"}).json()]
        assert ids == ["default"]


def test_no_unverified_special_policy_permission(monkeypatch):
    from app.knowledge import KB
    original = KB.by_id["ACRC-CASH-WREATH"]
    corrupted = {**original, "text": original["text"] + "검증 불가"}
    monkeypatch.setitem(KB.by_id, "ACRC-CASH-WREATH", corrupted)
    result = assess_special("cash_and_wreath", cash_krw=50000, wreath_krw=50000)
    assert result["status"] == "NEEDS_EXPERT_REVIEW"
    assert not result["source_ids"]
