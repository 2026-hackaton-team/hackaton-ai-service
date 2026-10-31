"""자유 상담의 단일 검토 엔진·SQLite 반영·법률·예산 회귀 검사."""
from copy import deepcopy

import pytest

from gyeongjosa_ai.ai import ModelUnavailable
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService, parse_budget, parse_meal_attendance
from gyeongjosa_ai.workspace_adapter import data_for_chat
from gyeongjosa_ai.workspace_store import WorkspaceInput, save_workspace


class FixedGateway:
    """모델이 잘못된 금액을 반환해도 서버 추천액이 바뀌지 않음을 검사한다."""

    def __init__(self):
        self.contexts = []

    def generate(self, context, allowed_ids, preferred_model=None):
        self.contexts.append(context)
        return {"answer": "설명만 제공합니다.", "model": "fixed-model",
                "evidence_ids": list(allowed_ids), "suggested_amount_krw": 200000}

    def classify(self, context, people_ids, notice_ids):
        return {"intent": "amount", "person_id": None,
                "notice_id": None, "event_type": "장례", "model": "fixed-model"}


@pytest.mark.parametrize(("question", "expected"), [
    ("지난번에 20만 원을 받았고 이번 예산은 3만 원이에요", 30000),
    ("예산 3만원인데 이전에는 20만원 냈어요", 30000),
    ("지난번에 20만원 받았어요", None),
    ("예전에 5만원 줬는데 상대는 20만원 줬어", None),
    ("3만 원", 30000),
    ("예산은 0원", 0),
])
def test_budget_disambiguates_recorded_amounts(question, expected):
    """금액이 여러 개일 때 예산 표현을 우선한다."""
    assert parse_budget(question) == expected


@pytest.mark.parametrize(("question", "expected"), [
    ("식사는 하지 않아", False), ("식사를 하지 않을 예정이야", False),
    ("식사하지 않고 참석해", False), ("식사는 못 해", False),
    ("참석해서 식사해요", True), ("이번 예산은 3만원이야", None),
])
def test_meal_attendance_understands_particles_and_negation(question, expected):
    """조사가 들어간 식사 부정과 명시하지 않은 상태를 구분한다."""
    assert parse_meal_attendance(question) is expected



def test_model_meal_interpretation_precedes_regex_fallback(tmp_path, monkeypatch):
    """정규식이 놓치는 식사 거절도 모델의 명시 판단으로 해석한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    save_workspace("U001", _workspace(100000))
    gateway = FixedGateway()
    gateway.classify = lambda *args: {
        "intent": "amount", "person_id": None, "notice_id": None,
        "event_type": "결혼", "attendance_with_meal": False, "model": "fixed-model",
    }
    service = ChatService(data_for_chat(load_data(), "U001"), gateway)
    question = "친구A 결혼식에 참석하지만 밥은 사양할게. 예산은 12만원이야."
    assert parse_meal_attendance(question) is True
    result = service.chat_auto({"user_id": "U001", "question": question})
    assert result["status"] == "answer"
    assert result["context"]["attendance_with_meal"] is False


def test_previous_model_without_meal_field_still_uses_regex(tmp_path, monkeypatch):
    """기존 분류 모델 형식은 안전하게 이전 식사 해석을 유지한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    save_workspace("U001", _workspace(100000))
    gateway = FixedGateway()
    gateway.classify = lambda *args: {
        "intent": "amount", "person_id": None, "notice_id": None,
        "event_type": "결혼", "model": "fixed-model",
    }
    service = ChatService(data_for_chat(load_data(), "U001"), gateway)
    result = service.chat_auto({"user_id": "U001",
        "question": "친구A 결혼식에는 참석하지만 식사는 하지 않아. 예산 12만원이야."})
    assert result["context"]["attendance_with_meal"] is False



def test_intent_fallback_does_not_replace_answer_generation_model(tmp_path, monkeypatch):
    """Gemini 분류 결과를 생성 모델 우선순위로 넘기지 않는다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    save_workspace("U001", _workspace(100000))

    class ClassificationGateway(FixedGateway):
        def __init__(self):
            super().__init__()
            self.preferred_models = []

        def classify(self, context, people_ids, notice_ids):
            return {"intent": "amount", "person_id": None, "notice_id": None,
                    "event_type": "결혼", "model": "gemini-3.1-flash-lite"}

        def generate(self, context, allowed_ids, preferred_model=None):
            self.preferred_models.append(preferred_model)
            return super().generate(context, allowed_ids, preferred_model)

    gateway = ClassificationGateway()
    service = ChatService(data_for_chat(load_data(), "U001"), gateway)
    result = service.chat_auto({
        "user_id": "U001", "question": "친구A 결혼식에 참석해서 식사해요. 예산은 10만원이에요",
        "context": {"person_id": "p1"},
    })
    assert result["status"] == "answer"
    assert result["classification_model"] == "gemini-3.1-flash-lite"
    assert gateway.preferred_models == [None]

def test_budget_followup_keeps_meal_condition(tmp_path, monkeypatch):
    """예산만 바꾼 후속 질문에서 앞서 말한 식사 불참을 다시 묻지 않는다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    save_workspace("U001", _workspace(100000))
    gateway = FixedGateway()
    monkeypatch.setattr(gateway, "classify", lambda *args: {
        "intent": "amount", "person_id": None, "notice_id": None,
        "event_type": "결혼", "model": "fixed-model"})
    service = ChatService(data_for_chat(load_data(), "U001"), gateway)
    first = service.chat_auto({"user_id": "U001",
        "question": "친구A 결혼식에 참석하지만 식사는 하지 않아. 예산은 12만원이야."})
    assert first["context"]["attendance_with_meal"] is False
    assert first["context"]["event_type"] == "결혼"
    second = service.chat_auto({"user_id": "U001", "context": first["context"],
        "question": "상대와 행사 조건은 그대로야. 이번 예산을 3만원으로 줄일게."})
    assert second["status"] == "answer"
    assert second["context"]["attendance_with_meal"] is False
    assert second["context"]["budget_krw"] == 30000
    assert second["suggested_amount_krw"] <= 30000


def test_history_reply_contains_calculated_stats(tmp_path, monkeypatch):
    """이력 조회도 모델의 문구와 별개로 실제 장부의 평균을 반환한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    save_workspace("U001", _workspace(100000))
    result = ChatService(data_for_chat(load_data(), "U001"), FixedGateway()).chat({
        "user_id": "U001", "mode": "history", "person_id": "p1", "question": "주고받은 평균"})
    assert result["history_stats"]["received"]["average_krw"] == 100000
    assert result["history_stats"]["paid"]["average_krw"] is None


def test_amount_explanation_receives_event_categories_and_attendance(tmp_path, monkeypatch):
    """같은 인물의 결혼·장례 구분과 기록된 참석 여부를 설명 모델에 전달한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    snapshot = _workspace(100000).model_dump(mode="json")
    snapshot["events"] = [{"id": "wedding", "personId": "p1", "title": "친구 결혼",
                           "type": "결혼식", "date": "2025-01-01", "attendance": "attended"}]
    snapshot["records"].append({"id": "r2", "personId": "p1", "eventId": "wedding",
                                "type": "결혼식", "date": "2025-01-01", "direction": "보낸 마음", "amount": 70000})
    save_workspace("U001", WorkspaceInput.model_validate(snapshot))
    gateway = FixedGateway()
    result = ChatService(data_for_chat(load_data(), "U001"), gateway).chat({
        "user_id": "U001", "mode": "amount", "person_id": "p1", "event_type": "장례",
        "question": "장례 예산은 10만원이고 식사는 하지 않아", "budget_krw": 100000})
    context = gateway.contexts[-1]
    events = {e["id"]: e for e in context["history"]["events"]}
    assert {e["category"] for e in events.values()} == {"결혼", "장례"}
    assert events["wedding"]["actual_attendance"] == "attended"
    assert context["attendance_with_meal"] is False
    assert all(t["event_id"] in events for t in context["history"]["transactions"])
    assert {e["id"] for e in context["history"]["events"]} <= set(context["allowed_evidence_ids"])
    assert any(e["id"] == "r2" and "결혼" in e["text"] for e in result["evidence"])


def _workspace(amount):
    """계정 소유 인맥과 실제 거래가 있는 최소 서버 작업 공간이다."""
    return WorkspaceInput.model_validate({
        "revision": 0,
        "people": [
            {"id": "p1", "name": "친구A", "relation": "친구", "group": "대학 동기",
             "closeness_score": 5},
            {"id": "p2", "name": "친구B", "relation": "친구", "group": "동아리"},
        ],
        "events": [],
        "records": [
            {"id": "r1", "personId": "p1", "eventId": "", "type": "장례식",
             "date": "2026-10-01", "direction": "받은 마음", "amount": amount},
        ],
    })


def test_sqlite_workspace_changes_next_consultation(tmp_path, monkeypatch):
    """장부를 수정한 후 같은 질문의 과거 거래 근거가 바뀐다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "data.sqlite3"))
    base = load_data()
    gateway = FixedGateway()
    save_workspace("U001", _workspace(50000))
    first_data = data_for_chat(base, "U001")
    first = ChatService(first_data, gateway).chat({
        "user_id": "U001", "mode": "amount", "question": "장례 예산은 10만원",
        "person_id": "p1", "event_type": "장례", "budget_krw": 100000,
    })
    assert any("50,000원" in item["text"] for item in first["evidence"]
               if item["kind"] == "개인 거래")
    assert gateway.contexts[-1]["history"]["transactions"][0]["amount_krw"] == 50000

    replacement = _workspace(200000).model_dump(mode="json")
    replacement["revision"] = 1
    save_workspace("U001", WorkspaceInput.model_validate(replacement))
    second = ChatService(data_for_chat(base, "U001"), gateway).chat({
        "user_id": "U001", "mode": "amount", "question": "장례 예산은 10만원",
        "person_id": "p1", "event_type": "장례", "budget_krw": 100000,
    })
    assert any("200,000원" in item["text"] for item in second["evidence"]
               if item["kind"] == "개인 거래")
    assert second["suggested_amount_krw"] <= 100000
    assert gateway.contexts[-1]["history"]["transactions"][0]["amount_krw"] == 200000


def test_workspace_isolation_and_missing_account_data(tmp_path, monkeypatch):
    """다른 계정의 신규 거래를 임의 연결하지 않는다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "data.sqlite3"))
    base = load_data()
    save_workspace("U001", _workspace(200000))
    other = data_for_chat(base, "U002")
    assert all(person["id"] != "p1" for person in other.people("U002"))
    mine = data_for_chat(base, "U001")
    assert mine.people("U001")[0]["id"] == "p1"
    assert mine.history("U001", "p1")["received_total_krw"] == 200000
    assert mine.history("U002", "p1") is None


def test_same_engine_with_and_without_person_transactions(tmp_path, monkeypatch):
    """거래가 있든 없든 개인화 결과에 정책 평가가 존재해야 한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "data.sqlite3"))
    save_workspace("U001", _workspace(100000))
    gateway = FixedGateway()
    service = ChatService(data_for_chat(load_data(), "U001"), gateway)
    for person_id in ("p1", "p2"):
        result = service.chat({
            "user_id": "U001", "mode": "amount", "question": "장례 예산 10만원",
            "person_id": person_id, "event_type": "장례", "budget_krw": 100000,
        })
        assert result["status"] == "answer"
        assert result["v4_analysis"]["legal_assessment"]
        assert result["suggested_amount_krw"] <= 100000
        assert result["suggested_amount_krw"] != 200000
        assert result["recommendation_basis"] in {"heuristic", "history", "survey"}


def test_contract_risk_withholds_numeric_suggestion(tmp_path, monkeypatch):
    """계약·심사 단서는 일반 상담에서도 법률 확인 전 추천 금액을 보류한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "data.sqlite3"))
    save_workspace("U001", _workspace(100000))
    gateway = FixedGateway()
    service = ChatService(data_for_chat(load_data(), "U001"), gateway)
    result = service.chat({
        "user_id": "U001", "mode": "amount",
        "question": "공직자 계약 심사 상대에게 장례 예산 10만원",
        "person_id": "p1", "event_type": "장례", "budget_krw": 100000,
    })
    assert result["suggested_amount_krw"] is None
    assert result["v4_analysis"]["status"] != "RECOMMENDED"
    assert "보류" in result["message"]
    assert not gateway.contexts
    assert result["v4_analysis"]["ai_status"] == "not_requested"


def test_unmarked_legal_question_does_not_enter_fictional_scenario():
    """일반 계약 관계 질문을 U001 전용 가상 인물로 전환하지 않는다."""
    from gyeongjosa_ai.v4_chat import try_v4_chat
    assert try_v4_chat("U001", "저는 심사하는 거래처의 부친상에 가고 싶어요.", {}) is None


def test_conversation_api_reads_updated_workspace_each_turn(tmp_path, monkeypatch):
    """실제 대화 API가 합성 원본이 아닌 최신 SQLite 장부를 매 요청 읽는다."""
    from fastapi.testclient import TestClient

    from gyeongjosa_ai.api import app
    from gyeongjosa_ai.dependencies import get_service
    from gyeongjosa_ai import integration_api

    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    monkeypatch.setattr(integration_api, "_DB", tmp_path / "conversations.sqlite3")
    gateway = FixedGateway()
    app.dependency_overrides[get_service] = lambda: ChatService(load_data(), gateway)
    try:
        with TestClient(app) as client:
            save_workspace("U001", _workspace(50000))
            headers = {"X-Demo-User-Id": "U001"}
            cid = client.post("/api/conversations", headers=headers).json()["id"]
            endpoint = f"/api/conversations/{cid}/messages"
            first = client.post(endpoint, headers=headers, json={
                "requestId": "request-turn-one",
                "text": "친구A의 장례식인데 예산은 10만원이에요",
            })
            assert first.status_code == 200, first.text
            assert any("50,000원" in row["text"] for row in first.json()["evidence"]
                       if row["kind"] == "개인 거래")

            amended = _workspace(200000).model_dump(mode="json")
            amended["revision"] = 1
            save_workspace("U001", WorkspaceInput.model_validate(amended))
            second = client.post(endpoint, headers=headers, json={
                "requestId": "request-turn-two", "text": "예산은 10만원으로 추천해줘",
            })
            assert second.status_code == 200, second.text
            assert any("200,000원" in row["text"] for row in second.json()["evidence"]
                       if row["kind"] == "개인 거래")
            assert second.json()["suggested_amount_krw"] <= 100000
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_amount_with_history_displays_generated_ai_explanation(tmp_path, monkeypatch):
    """개인 거래가 있어도 실제 모델이 반환한 해석을 사용자 답변에 포함한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "data.sqlite3"))
    save_workspace("U001", _workspace(50000))
    gateway = FixedGateway()
    result = ChatService(data_for_chat(load_data(), "U001"), gateway).chat({
        "user_id": "U001", "mode": "amount", "question": "장례 예산은 10만원",
        "person_id": "p1", "event_type": "장례", "budget_krw": 100000,
    })
    assert result["v4_analysis"]["ai_status"] == "generated"
    assert result["model"] == "fixed-model"
    assert "AI 해석: 설명만 제공합니다." in result["message"]
    assert result["suggested_amount_krw"] <= 100000
    assert len(gateway.contexts) == 1


def test_unconfigured_amount_keeps_rule_result_without_calling_model(tmp_path, monkeypatch):
    """API 키가 없으면 규칙 결과만 제공하고 호출 실패로 표시하지 않는다."""
    class UnconfiguredGateway(FixedGateway):
        api_key = ""

        def generate(self, *args, **kwargs):
            raise AssertionError("API 키 없이 모델을 호출하면 안 됩니다.")

    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "data.sqlite3"))
    save_workspace("U001", _workspace(50000))
    result = ChatService(data_for_chat(load_data(), "U001"), UnconfiguredGateway()).chat({
        "user_id": "U001", "mode": "amount", "question": "장례 예산은 10만원",
        "person_id": "p1", "event_type": "장례", "budget_krw": 100000,
    })
    assert result["v4_analysis"]["ai_status"] == "not_configured"
    assert result["model"] is None
    assert "AI 해석:" not in result["message"]
    assert result["suggested_amount_krw"] <= 100000


def test_failed_amount_analysis_is_not_reported_as_missing_key(tmp_path, monkeypatch):
    """설정된 모델이 실패해도 참고액은 유지하며 실패 상태를 정확히 반환한다."""
    class FailingGateway(FixedGateway):
        api_key = "test-key"

        def generate(self, *args, **kwargs):
            raise ModelUnavailable("모델 호출 실패")

    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "data.sqlite3"))
    save_workspace("U001", _workspace(50000))
    result = ChatService(data_for_chat(load_data(), "U001"), FailingGateway()).chat({
        "user_id": "U001", "mode": "amount", "question": "장례 예산은 10만원",
        "person_id": "p1", "event_type": "장례", "budget_krw": 100000,
    })
    assert result["v4_analysis"]["ai_status"] == "unavailable"
    assert result["model"] is None
    assert "AI 해석:" not in result["message"]
    assert result["suggested_amount_krw"] <= 100000
