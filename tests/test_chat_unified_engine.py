"""자유 상담의 단일 검토 엔진·SQLite 반영·법률·예산 회귀 검사."""
from copy import deepcopy

import pytest

from gyeongjosa_ai.ai import ModelUnavailable
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService, parse_budget
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
