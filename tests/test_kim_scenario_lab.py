"""김시나리오 합성 장부와 일반 자유 상담 API 재사용 회귀 테스트."""

from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.dependencies import get_service
from gyeongjosa_ai.scenario_lab import (
    USER_ID, cases, catalog, ensure_scenario_workspace, scenario_workspace, with_scenario_user,
)
from gyeongjosa_ai.service import ChatService
from gyeongjosa_ai.workspace_adapter import data_for_chat
from gyeongjosa_ai.workspace_store import WorkspaceInput, load_workspace, save_workspace
from gyeongjosa_ai import integration_api


class Gateway:
    """추가 모델 비용 없이 실제 금액 엔진까지 API 경로를 검사한다."""

    def classify(self, context, people_ids, notice_ids):
        question = context["question"]
        return {
            "intent": "amount", "person_id": None, "notice_id": None,
            "event_type": "결혼" if "결혼" in question else "장례",
            "model": "test-model",
        }

    def generate(self, context, allowed_ids, preferred_model=None):
        return {
            "answer": "확인된 관계 이력과 예산을 참고한 AI 설명입니다.",
            "model": "test-model", "evidence_ids": sorted(allowed_ids),
            "suggested_amount_krw": 999999,
        }


def test_persona_workspace_has_twenty_people_and_distinct_transactions(tmp_path, monkeypatch):
    """20명 서로 다른 ID와 금액·참석 맥락을 SQLite에 저장한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    original = scenario_workspace()
    assert len(original.people) == len(cases()) == 20
    assert len({person.id for person in original.people}) == 20
    assert len(original.records) == sum(len(item["paid"]) + len(item["received"]) for item in cases())
    assert original.records and all(record.eventId for record in original.records)

    initial = ensure_scenario_workspace()
    assert initial["initialized"] and initial["revision"] == 1
    assert len(initial["people"]) == 20
    assert ensure_scenario_workspace()["revision"] == 1

    revised = {**initial, "people": [*initial["people"]]}
    revised["people"][0] = {**revised["people"][0], "memo": "사용자가 변경한 메모"}
    save_workspace(USER_ID, WorkspaceInput.model_validate(revised))
    assert ensure_scenario_workspace()["people"][0]["memo"] == "사용자가 변경한 메모"
    assert load_workspace("U001")["initialized"] is False


def test_persona_records_are_used_by_normal_recommendation_engine(tmp_path, monkeypatch):
    """별도 시나리오 분기 없이 동일 추천 엔진의 근거와 예산을 검사한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    ensure_scenario_workspace()
    data = data_for_chat(with_scenario_user(load_data()), USER_ID)
    gateway = Gateway()
    service = ChatService(data, gateway)
    first = cases()[0]
    history = data.history(USER_ID, first["person_id"])
    assert len(history["transactions"]) == 6
    assert history["received_total_krw"] == 300000
    assert history["paid_total_krw"] == 150000

    result = service.chat({
        "user_id": USER_ID, "mode": "amount", "question": first["question"],
        "person_id": first["person_id"], "event_type": "결혼",
        "attendance_with_meal": False, "budget_krw": first["budget_krw"],
    })
    assert result["status"] == "answer"
    assert result["suggested_amount_krw"] is not None
    assert result["suggested_amount_krw"] <= first["budget_krw"]
    assert result["suggested_amount_krw"] == result["v4_analysis"]["amount_krw"]
    assert result["suggested_amount_krw"] != 999999
    assert result["recommendation_basis"] in {"history", "survey", "heuristic"}
    assert "기록상 받은 금액" in result["message"]
    assert sum(item["kind"] == "개인 거래" for item in result["evidence"]) == 6


def test_persona_api_and_20_real_dialogues(tmp_path, monkeypatch):
    """20건을 대화 저장·분류·추천에 통과시키고 보류/실패도 감춘 채 성공으로 취급하지 않는다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    monkeypatch.setattr(integration_api, "_DB", tmp_path / "conversations.sqlite3")
    ensure_scenario_workspace()
    service = ChatService(with_scenario_user(load_data()), Gateway())
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            headers = {"X-Demo-User-Id": USER_ID}
            assert client.get("/api/demo/kim-scenarios", headers={"X-Demo-User-Id": "U001"}).status_code == 403
            items = client.get("/api/demo/kim-scenarios", headers=headers).json()["items"]
            assert len(items) == 20
            assert len({item["person_id"] for item in items}) == 20
            assert any(user["id"] == USER_ID for user in client.get("/api/demo/users").json()["items"])
            assert len(client.get("/api/workspace/personal", headers=headers).json()["people"]) == 20

            for number, item in enumerate(items):
                conversation = client.post("/api/conversations", headers=headers)
                assert conversation.status_code == 201
                cid = conversation.json()["id"]
                reply = client.post(f"/api/conversations/{cid}/messages", headers=headers, json={
                    "requestId": f"kim-test-{number:02d}",
                    "text": item["question"],
                })
                assert reply.status_code == 200, (item["id"], reply.text)
                result = reply.json()
                assert result["status"] in {"answer", "need_more_info"}
                if result["status"] == "answer":
                    assert result["context"]["person_id"] == item["person_id"], item["id"]
                expected_signals = {
                    "reciprocity_up": "reciprocity",
                    "recent_large": "recent_large_gift",
                    "relationship_drift": "relationship_drift",
                    "closeness_rise": "closeness",
                }
                if item["focus"] in expected_signals and result["status"] == "answer":
                    signals = {row["signal"] for row in result["v4_analysis"]["relationship_adjustments"]}
                    assert expected_signals[item["focus"]] in signals, item["id"]
                if item["focus"] in {"legal_recipient", "legal_sender"} and result["status"] == "answer":
                    assert result.get("suggested_amount_krw") is None, item["id"]
                if item["focus"] not in {"legal_recipient", "legal_sender"}:
                    assert result["status"] == "answer", item["id"]
                    assert result.get("suggested_amount_krw") is not None, item["id"]
                    assert result.get("evidence"), item["id"]
                if result.get("suggested_amount_krw") is not None:
                    assert 0 < result["suggested_amount_krw"] <= item["budget_krw"]
                    assert result["suggested_amount_krw"] == result["v4_analysis"]["amount_krw"]
                assert len(client.get(f"/api/conversations/{cid}", headers=headers).json()["messages"]) == 2

            unknown = client.get("/api/workspace/personal", headers={"X-Demo-User-Id": "U001"}).json()
            assert not any(item["id"].startswith("KIMP") for item in unknown["people"])
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_duplicate_names_require_identification(tmp_path, monkeypatch):
    """동명이인 단독 이름은 특정 인물에게 임의 연결하지 않는다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    ensure_scenario_workspace()
    service = ChatService(data_for_chat(with_scenario_user(load_data()), USER_ID), Gateway())
    result = service.chat_auto({
        "user_id": USER_ID, "question": "문지훈 결혼식인데 예산 10만원이야",
        "context": {},
    })
    assert result["status"] == "need_more_info"
    assert result["pending_field"] == "person_id"
    assert len(result["options"]) == 2
