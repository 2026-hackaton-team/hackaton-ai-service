"""연속형 1만원 단위 추천의 예산·개인화·근거 경계 테스트."""

from copy import deepcopy

from app.knowledge import KB
from app.recommender import DEMO, recommend
from app.orchestrator import run


def result(budget, **kwargs):
    """개인화 관계 시연의 동일 조건에서 예산만 교체한다."""
    return recommend(
        user_id="U001", person_id="V4P013", identity_confirmed=True,
        event_type="장례", attendance_with_meal=None, budget_krw=budget,
        **kwargs,
    )


def test_budget_below_previous_minimum_has_ten_thousand_candidates():
    """기존 3만원 최소 후보 때문에 1~2만원 예산을 거절하지 않는다."""
    for budget in (10000, 20000, 27000):
        answer = result(budget)
        assert answer["status"] == "RECOMMENDED"
        assert answer["amount_krw"] <= budget
        assert answer["amount_krw"] % 10000 == 0
        assert answer["amount_unit_krw"] == 10000
    for budget in (0, 5000, 9999):
        assert result(budget)["status"] == "NO_AFFORDABLE_CANDIDATE"


def test_rounding_and_budget_limit_preserve_continuous_internal_amount():
    """1만원 단위 상한 적용 전후의 금액을 구분하고 정수 금액을 반환한다."""
    baseline = result(None, closeness_override=5, special_care=True)
    assert baseline["status"] == "RECOMMENDED"
    assert baseline["amount_krw"] % 10000 == 0
    assert baseline["raw_base_amount_krw"] > 0
    assert baseline["raw_personalized_amount_krw"] >= baseline["raw_base_amount_krw"]
    assert baseline["unrestricted_amount_krw"] == baseline["amount_krw"]
    assert baseline["budget_limited"] is False

    for budget in (30000, 85000, 95000, 125000):
        answer = result(budget, closeness_override=5, special_care=True)
        assert answer["status"] == "RECOMMENDED"
        assert answer["amount_krw"] <= budget
        assert answer["amount_krw"] % 10000 == 0
        assert answer["unrestricted_amount_krw"] == baseline["amount_krw"]
        assert answer["budget_limited"] is (baseline["amount_krw"] > budget)


def test_closeness_affects_continuous_amount_without_candidate_steps():
    """친밀도에 따라 내부 목표액이 연속적으로 바뀌고 조정 근거를 남긴다."""
    low = result(None, closeness_override=1)
    mid = result(None, closeness_override=3)
    high = result(None, closeness_override=5)
    assert low["raw_personalized_amount_krw"] < mid["raw_personalized_amount_krw"]
    assert mid["raw_personalized_amount_krw"] < high["raw_personalized_amount_krw"]
    assert low["amount_krw"] <= mid["amount_krw"] <= high["amount_krw"]
    assert all(x["amount_krw"] % 10000 == 0 for x in (low, mid, high))
    assert any(row["signal"] == "closeness" for row in high["relationship_adjustments"])


def test_personal_history_uses_cpi_adjusted_anchors_and_no_unsupported_survey():
    """물가 보정된 기록과 설문 적용 조건을 보존한다."""
    response = result(None)
    assert response["personal_history"]["cpi_reference_month"]
    assert response["personal_history"]["cpi_coverage"]
    assert response["matched_source_id"] is None
    assert "SKK-FUNERAL-2024" in KB.by_id
    assert KB.by_id["SKK-FUNERAL-2024"]["can_anchor_amount"] is False


def test_legal_conditional_cash_limit_keeps_ten_thousand_units():
    """공직자 조건부 예외가 확인될 때 5만원 한도가 우선한다."""
    answer = run(
        user_id="U001", person_id="V4P013", identity_confirmed=True,
        event_type="장례", attendance_with_meal=None, budget_krw=150000,
        profile_override={
            "covered": "yes", "duty_related": "yes",
            "exception_confirmed": "yes", "conflict": "none",
            "provenance": "self_reported_context",
        },
        closeness_override=5, special_care=True,
    )["result"]
    assert answer["status"] == "RECOMMENDED"
    assert answer["amount_krw"] <= 50000
    assert answer["amount_krw"] % 10000 == 0


def test_public_survey_is_only_used_when_relevant():
    """직장 동료·결혼·식사 조건에서만 공개 설문을 직접 적용한다."""
    data = deepcopy(DEMO)
    person = next(row for row in data["people"] if row["id"] == "V4P013")
    person["relationship"] = "직장 동료"
    response = recommend(
        user_id="U001", person_id="V4P013", identity_confirmed=True,
        event_type="결혼", attendance_with_meal=True, budget_krw=200000,
        dataset=data,
    )
    assert response["status"] == "RECOMMENDED"
    assert response["matched_source_id"] == "INC-2025-05"
    assert response["amount_krw"] % 10000 == 0
