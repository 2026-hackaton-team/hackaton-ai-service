"""개인 이력과 적용 가능한 공개 근거로 연속형 금액을 계산한다.

가중치와 관계 조정률은 학습되지 않은 실험값이며 적정 금액을 보증하지 않는다.
"""
from __future__ import annotations
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median
from .knowledge import KB, KnowledgeBase
from .inflation import DATA as CPI_DATA, adjust_amount

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "original_demo.json"
from gyeongjosa_ai.special_fixtures import merge_special_fixtures

DEMO = merge_special_fixtures(json.loads(DATA_FILE.read_text(encoding="utf-8")))
AMOUNT_UNIT = 10000
RAW_WEIGHTS = {"matched_survey": 0.55, "same_type_paid": 0.20, "paid_to_person": 0.15, "received_from_person": 0.10}


def owned_person(user_id: str, person_id: str):
    return next((p for p in DEMO["people"] if p["id"] == person_id and p["owner_user_id"] == user_id), None)


def _positive_median(records, events=None):
    amounts = []
    for transaction in records:
        amount = transaction["amount_krw"]
        if amount > 0:
            if events is not None:
                event_date = events[transaction["private_event_id"]]["start_date"]
                amount = adjust_amount(amount, event_date)["adjusted_amount_krw"]
            amounts.append(amount)
    return median(amounts) if amounts else None


def _closeness(amount, anchor):
    return max(0.0, 1.0 - abs(amount - anchor) / max(50000, anchor))


def recommend(*, user_id: str, person_id: str, identity_confirmed: bool, event_type: str,
              attendance_with_meal: bool | None, budget_krw: int | None, legal_risk: bool = False,
              kb: KnowledgeBase = KB, closeness_override: int | None = None,
              special_care: bool = False, recent_received_override: int | None = None,
              dataset: dict | None = None):
    if not identity_confirmed:
        return {"status": "NEEDS_IDENTITY_CONFIRMATION", "message": "동명이인일 수 있습니다. 추천 대상자를 확인해 주세요."}
    source = dataset if dataset is not None else DEMO
    person = next((p for p in source['people'] if p['id'] == person_id and p['owner_user_id'] == user_id), None)
    if person is None:
        return {"status": "FORBIDDEN_OR_NOT_FOUND", "message": "접근 가능한 해당 인물 기록이 없습니다."}
    if event_type not in source["event_categories"]:
        return {"status": "INVALID_EVENT_TYPE", "message": "지원하지 않는 행사입니다."}
    if legal_risk:
        return {"status": "LEGAL_REVIEW_REQUIRED", "message": "직무 관련 청탁금지법 적용 여부를 먼저 검토해야 합니다."}
    if event_type == "결혼" and attendance_with_meal is None:
        return {"status": "NEEDS_ATTENDANCE_CONTEXT", "message": "결혼식 참석·식사 여부를 선택해 주세요."}
    if budget_krw is not None and budget_krw < 0:
        return {"status": "INVALID_BUDGET", "message": "예산은 음수가 될 수 없습니다."}
    own_events = {e["id"]: e for e in source["private_events"] if e["owner_user_id"] == user_id}
    transactions = [t for t in source["transactions"] if t["owner_user_id"] == user_id and t["private_event_id"] in own_events]
    same_person = [t for t in transactions if t["contact_person_id"] == person_id]
    paid = [t for t in same_person if t["direction"] == "paid"]
    received = [t for t in same_person if t["direction"] == "received"]
    # 관계 시연 거래는 해당 인물의 이력에만 반영해 기존 추천의 기준값을 보존한다.
    is_relationship_demo = "relationship_context" in person
    same_type = [t for t in transactions if t["direction"] == "paid"
                 and own_events[t["private_event_id"]]["category"] == event_type
                 and (t["contact_person_id"] == person_id if is_relationship_demo
                      else not t["id"].startswith("V4T"))]
    per_type_med = _positive_median(same_type, own_events)
    paid_med = _positive_median(paid, own_events)
    received_med = _positive_median(received, own_events)

    survey = kb.eligible_amount_source(event_type=event_type, relationship=person["relationship"], attendance_with_meal=attendance_with_meal)
    survey_shares = ({f["amount_krw"]: f["pct"] / 100 for f in survey["facts"] if f["metric"] == "perceived_amount_share"} if survey else {})
    cold_start = not survey_shares and paid_med is None and received_med is None and per_type_med is None
    weights = {k: v for k, v in RAW_WEIGHTS.items() if
               (k == "matched_survey" and bool(survey_shares)) or
               (k == "same_type_paid" and per_type_med is not None) or
               (k == "paid_to_person" and paid_med is not None) or
               (k == "received_from_person" and received_med is not None)}
    denom = sum(weights.values())
    weights = {k: v / denom for k, v in weights.items()} if denom else {}
    # 조건이 맞는 설문은 전체 분포의 평균을 꾸며내지 않고 최빈 응답액만 사용한다.
    anchors = {}
    if survey_shares:
        anchors["matched_survey"] = min(survey_shares, key=lambda amount: (-survey_shares[amount], amount))
    if per_type_med is not None:
        anchors["same_type_paid"] = per_type_med
    if paid_med is not None:
        anchors["paid_to_person"] = paid_med
    if received_med is not None:
        anchors["received_from_person"] = received_med
    base_amount = (
        sum(Decimal(str(anchors[key])) * Decimal(str(weight)) for key, weight in weights.items())
        if anchors else Decimal(50000)
    )

    def round_amount(amount):
        """연속 계산 결과를 한국 경조사 시연의 1만원 단위로 반올림한다."""
        return int((amount / AMOUNT_UNIT).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * AMOUNT_UNIT)

    baseline_amount = round_amount(base_amount)
    if budget_krw is not None and budget_krw < AMOUNT_UNIT:
        return {"status": "NO_AFFORDABLE_CANDIDATE",
                "message": "예산이 1만원 미만이므로 정해진 추천 단위 안의 현금 후보가 없습니다. 비금전적 대안을 고려해 주세요."}
    context = person.get("relationship_context") or {}
    closeness = closeness_override if closeness_override is not None else context.get("closeness_score")
    adjustments = []
    change = Decimal("0")

    def apply(signal, delta, reason):
        """검증된 개인화 신호의 영향과 설명을 함께 기록한다."""
        nonlocal_change[0] += Decimal(str(delta))
        adjustments.append({"signal": signal, "direction": "up" if delta > 0 else "down",
                            "percentage_points": int(Decimal(str(delta)) * 100), "reason": reason})

    nonlocal_change = [change]
    if type(closeness) is int and 1 <= closeness <= 5 and closeness != 3:
        delta = Decimal(closeness - 3) * Decimal("0.05")
        apply("closeness", delta, f"현재 친밀도 {closeness}/5를 기준 수준 3/5와 비교해 반영했습니다.")
    if paid_med and received_med and len(received) >= 2 and received_med >= paid_med * 1.5:
        apply("reciprocity", Decimal("0.05"), "상대에게 받은 금액의 중앙값이 내가 낸 금액보다 높습니다.")
    dated_received = sorted(received, key=lambda t: (own_events[t["private_event_id"]]["start_date"], t["id"]))
    if len(dated_received) >= (2 if recent_received_override is not None else 3):
        from statistics import median as _median
        # 사용자 자기신고 최신 수령액은 저장된 거래를 변경하지 않고 임시 신호로 처리한다.
        preceding_records = dated_received if recent_received_override is not None else dated_received[:-1]
        earlier_amounts = [adjust_amount(t["amount_krw"], own_events[t["private_event_id"]]["start_date"])["adjusted_amount_krw"]
                           for t in preceding_records if t["amount_krw"] > 0]
        preceding = _median(earlier_amounts) if earlier_amounts else None
        latest = (recent_received_override if recent_received_override is not None
                  else adjust_amount(dated_received[-1]["amount_krw"],
                                     own_events[dated_received[-1]["private_event_id"]]["start_date"])["adjusted_amount_krw"])
        if preceding and latest >= preceding * 2:
            apply("recent_large_gift", Decimal("0.15") if latest >= preceding * 3 else Decimal("0.10"),
                  "최근 받은 금액이 이전 수령 중앙값의 2배 이상입니다.")
    closeness_history = context.get("closeness_history") or []
    if (isinstance(closeness, int) and closeness <= 2 and len(closeness_history) >= 2
            and closeness_history[0].get("score", 0) > closeness):
        apply("relationship_drift", Decimal("-0.10"),
              "사용자가 기록한 현재 친밀도가 과거보다 낮습니다.")
    if special_care and (context.get("non_monetary_support") or (isinstance(closeness, int) and closeness >= 4)):
        apply("special_care", Decimal("0.05"),
              "사용자가 특별히 챙기겠다는 의향을 밝혔습니다.")
    # 과도한 가산·감산을 방지하며, 반올림 이전 금액으로 예산 제한의 영향을 판단한다.
    change = max(Decimal("-0.20"), min(Decimal("0.20"), nonlocal_change[0]))
    raw_personalized = base_amount * (Decimal("1") + change)
    unrestricted_amount = max(AMOUNT_UNIT, round_amount(raw_personalized))
    budget_limited = budget_krw is not None and unrestricted_amount > budget_krw
    budget_floor = (budget_krw // AMOUNT_UNIT) * AMOUNT_UNIT if budget_krw is not None else None
    chosen = min(unrestricted_amount, budget_floor) if budget_floor is not None else unrestricted_amount

    # 법률 한도가 별도 적용되므로 낮은 후보도 포함한다. 고정 6단계는 사용하지 않는다.
    candidates = set(range(AMOUNT_UNIT, 50001, AMOUNT_UNIT))
    for center in (chosen, unrestricted_amount, baseline_amount):
        candidates.update(center + offset * AMOUNT_UNIT for offset in range(-3, 4))
    if budget_floor is not None:
        candidates.update(budget_floor + offset * AMOUNT_UNIT for offset in range(-3, 4))
    affordable = sorted(a for a in candidates
                        if a >= AMOUNT_UNIT and (budget_floor is None or a <= budget_floor))
    ranked = sorted(affordable, key=lambda a: (abs(a - raw_personalized), a))
    tx_ids = list(dict.fromkeys(t["id"] for t in (same_person + same_type)))
    cpi_coverage = {"monthly": 0, "annual": 0, "unavailable": 0, "after_reference": 0}
    for transaction in same_person:
        if transaction["amount_krw"] > 0:
            adjustment = adjust_amount(
                transaction["amount_krw"], own_events[transaction["private_event_id"]]["start_date"])
            cpi_coverage[adjustment["status"]] += 1
    reasons = []
    if survey:
        reasons.append("직장 동료의 결혼식에 참석해 식사하는 조건에 맞는 설문을 참고했습니다.")
    if paid:
        reasons.append(f"해당 인물에게 보낸 거래가 {len(paid)}건 있고 총 {sum(t['amount_krw'] for t in paid):,}원입니다.")
    if received:
        reasons.append(f"해당 인물에게 받은 거래가 {len(received)}건 있고 총 {sum(t['amount_krw'] for t in received):,}원입니다.")
    if same_type:
        reasons.append(f"같은 행사 종류의 과거 지급 기록 {len(same_type)}건을 참고했습니다.")
    if paid or received or same_type:
        reasons.append(
            f"과거 지급·수령 비교 기준을 {CPI_DATA['reference_month']}의 소비자물가지수로 환산했습니다."
            " 월별 지수가 없는 과거 기록은 연평균으로 근사하고, 확인 불가 기록은 원금을 사용합니다.")
    if budget_krw is not None:
        reasons.append(f"예산 {budget_krw:,}원을 초과하는 후보는 제외했습니다.")
    if cold_start:
        reasons.append("해당 지인의 금전 이력과 직접 일치하는 공개 금액 설문이 없어 50,000원을 시연용 비교 기준으로 사용했습니다. 통계적 적정액은 아닙니다.")
    elif not survey:
        reasons.append("해당 상황에 직접 일치하는 공개 금액 설문이 없어 개인 이력 중심으로 계산했습니다.")
    if adjustments:
        reasons.extend(item["reason"] for item in adjustments)
    level = "moderate" if survey else "low"
    return {"status": "RECOMMENDED", "amount_krw": ranked[0], "alternatives_krw": ranked[1:3],
            "baseline_amount_krw": baseline_amount, "personalized_amount_krw": ranked[0],
            "unrestricted_amount_krw": unrestricted_amount, "budget_limited": budget_limited,
            "raw_base_amount_krw": int(base_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            "raw_personalized_amount_krw": int(raw_personalized.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            "amount_unit_krw": AMOUNT_UNIT, "relationship_adjustment_pct": float(change * 100),
            "recommendation_basis": "heuristic" if cold_start else "survey" if survey else "history",
            "relationship_adjustments": adjustments,
            "scores": [{"amount_krw": a,
                        "score": round(1 / (1 + float(abs(Decimal(a) - raw_personalized) /
                                                    max(base_amount, Decimal(50000)))), 6)}
                       for a in ranked],
            "evidence_level": level, "weights_used": {k: round(v, 4) for k, v in weights.items()},
            "matched_source_id": survey["id"] if survey else None,
            "matched_transaction_ids": tx_ids,
            "personal_history": {"paid_count": len(paid), "paid_total_krw": sum(t["amount_krw"] for t in paid),
                                "received_count": len(received), "received_total_krw": sum(t["amount_krw"] for t in received),
                                "explicit_zero_paid_count": sum(t["amount_krw"] == 0 for t in paid),
                                "paid_median_current_krw": paid_med,
                                "received_median_current_krw": received_med,
                                "same_type_paid_median_current_krw": per_type_med,
                                "cpi_reference_month": CPI_DATA["reference_month"],
                                "cpi_coverage": cpi_coverage},
            "reasons": reasons,
            "disclaimer": "검증된 예측 모델이 아닌 규칙 기반 추천 시연입니다. 적정 금액이나 법적 적합성을 보장하지 않습니다."}
