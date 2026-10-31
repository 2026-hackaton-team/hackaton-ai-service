"""친밀도·최근 수령 변화·예산·법률 제한의 회귀 검증."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app.knowledge import KB
from app.main import app as policy_app
from app import recommender
from gyeongjosa_ai.api import app as chat_app
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService


class OfflineGateway:
    """고정 시연이 외부 모델을 호출하지 않는지 검사한다."""

    def classify(self, *_args, **_kwargs):
        raise AssertionError("고정 시연은 모델 분류를 호출하지 않습니다.")

    def generate(self, *_args, **_kwargs):
        raise AssertionError("고정 시연은 모델 금액을 사용하지 않습니다.")


def recommend(person_id, **kwargs):
    """동일 조건에서 개인화 신호만 비교한다."""
    return recommender.recommend(
        user_id="U001", person_id=person_id, identity_confirmed=True,
        event_type="장례", attendance_with_meal=None,
        budget_krw=100000, **kwargs,
    )


def ask(question, context=None):
    """자유 상담의 오프라인 시나리오를 실행한다."""
    return ChatService(load_data(), OfflineGateway()).chat_auto({
        "user_id": "U001", "question": question, "context": context or {},
    })


def test_closeness_changes_the_recommendation():
    """과거 거래를 고정한 채 친밀도만 변경하면 금액이 올라간다."""
    lower = recommend("V4P013", closeness_override=2)
    higher = recommend("V4P013", closeness_override=5)
    assert lower["status"] == higher["status"] == "RECOMMENDED"
    assert higher["amount_krw"] > lower["amount_krw"]
    assert any(row["signal"] == "closeness" for row in higher["relationship_adjustments"])


def test_recent_large_receipt_changes_recommendation(monkeypatch):
    """가장 최근 받은 금액의 변화가 이력 중앙값과 별도로 작동한다."""
    actual = recommend("V4P014")
    data = deepcopy(recommender.DEMO)
    events = {e["id"]: e for e in data["private_events"]}
    received = sorted(
        (t for t in data["transactions"]
         if t["owner_user_id"] == "U001" and t["contact_person_id"] == "V4P014"
         and t["direction"] == "received"),
        key=lambda t: (events[t["private_event_id"]]["start_date"], t["id"]),
    )
    assert len(received) >= 3
    received[-1]["amount_krw"] = 50000
    monkeypatch.setattr(recommender, "DEMO", data)
    ordinary = recommend("V4P014")
    assert actual["amount_krw"] > ordinary["amount_krw"]
    assert any(row["signal"] == "recent_large_gift" for row in actual["relationship_adjustments"])


def test_budget_is_never_exceeded():
    """상승 신호가 있더라도 예산 상한을 넘기지 않는다."""
    high = recommender.recommend(
        user_id="U001", person_id="V4P013", identity_confirmed=True,
        event_type="장례", attendance_with_meal=None, budget_krw=30000,
        closeness_override=5, special_care=True,
    )
    assert high["status"] == "RECOMMENDED"
    assert 0 < high["amount_krw"] <= 30000


def test_free_chat_uses_personalized_engine_and_evidence():
    """자유 상담에서 관계 보정과 연구 출처가 함께 전달된다."""
    result = ask("가상 시나리오: 금액보다 소중한 친구야. 친밀도를 5점으로 등록했어. 예산은 10만원이고 특별히 챙기고 싶어")
    assert result["status"] == "answer"
    assert result["model"] is None
    details = result["v4_analysis"]
    assert details["amount_krw"] <= 100000
    assert any(row["signal"] == "closeness" for row in details["relationship_adjustments"])
    assert any(row["kind"] == "인간관계 연구" and row.get("url") for row in result["evidence"])


def test_user_closeness_input_overrides_scenario_default():
    """친밀도 직접 입력을 시나리오 고정값보다 우선 적용한다."""
    q = "가상 시나리오: 금액보다 소중한 친구야. 예산은 10만원이고 친밀도는 {}점"
    low = ask(q.format(2))
    high = ask(q.format(5))
    assert high["suggested_amount_krw"] > low["suggested_amount_krw"]


def test_relationship_rag_never_claims_a_numeric_rule():
    """심리 연구는 금액 통계로 채택하지 않는다."""
    results = KB.retrieve("호혜성 선물 감사 친밀도", event_type="장례", top_k=20)
    guidance = [row for row in results if row["source_type"] == "relationship_guidance"]
    assert guidance
    for row in guidance:
        assert KB.by_id[row["id"]]["can_anchor_amount"] is False
    assert KB.eligible_amount_source(
        event_type="장례", relationship="가까운 친구", attendance_with_meal=None
    ) is None


def test_legal_risk_still_blocks_transfer():
    """개인화 추천을 구현한 뒤에도 계약 심사 위험은 송금액을 보류한다."""
    result = ask("가상 시나리오: 계약 심사 거래처 부친상, 예산은 10만원")
    assert result["v4_analysis"]["status"] == "POTENTIALLY_PROHIBITED"
    assert result["suggested_amount_krw"] is None


def test_invalid_closeness_is_rejected():
    """친밀도 범위 밖 입력은 정책 API에서 거부한다."""
    payload = {
        "demo_user_id": "U001", "person_id": "V4P013",
        "identity_confirmed": True, "event_type": "장례",
        "budget_krw": 100000, "closeness_override": 6,
    }
    response = TestClient(policy_app).post("/api/recommend", json=payload)
    assert response.status_code == 422


def test_only_free_chat_frontend_is_exposed():
    """독립 v4 경로를 제거하되 내부 정책 API 테스트는 유지한다."""
    assert TestClient(chat_app).get("/v4/").status_code == 404
    source = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "IntegratedAIPage.jsx").read_text(encoding="utf-8")
    assert "iframe" not in source
    assert "v4 직무·법적 위험 분석</button>" not in source
