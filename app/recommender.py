"""결정적 금액 추천: 공개 통계와 가상 개인 거래를 구분하여 계산한다.

이 가중치는 학습되지 않은 임의의 실험값이다. 금액의 '정답'이 아니라
해당 조건에서 고를 수 있는 후보 순위만 제공한다.
"""
from __future__ import annotations
import json
from pathlib import Path
from statistics import median
from .knowledge import KB, KnowledgeBase

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "original_demo.json"
from gyeongjosa_ai.special_fixtures import merge_special_fixtures

DEMO = merge_special_fixtures(json.loads(DATA_FILE.read_text(encoding="utf-8")))
AMOUNTS = (30000, 50000, 70000, 100000, 150000, 200000)
RAW_WEIGHTS = {"matched_survey": 0.55, "same_type_paid": 0.20, "paid_to_person": 0.15, "received_from_person": 0.10}


def owned_person(user_id: str, person_id: str):
    return next((p for p in DEMO["people"] if p["id"] == person_id and p["owner_user_id"] == user_id), None)


def _positive_median(records):
    amounts = [t["amount_krw"] for t in records if t["amount_krw"] > 0]
    return median(amounts) if amounts else None


def _closeness(amount, anchor):
    return max(0.0, 1.0 - abs(amount - anchor) / max(50000, anchor))


def recommend(*, user_id: str, person_id: str, identity_confirmed: bool, event_type: str,
              attendance_with_meal: bool | None, budget_krw: int | None, legal_risk: bool = False,
              kb: KnowledgeBase = KB, closeness_override: int | None = None,
              special_care: bool = False):
    if not identity_confirmed:
        return {"status": "NEEDS_IDENTITY_CONFIRMATION", "message": "동명이인일 수 있습니다. 추천 대상자를 확인해 주세요."}
    person = owned_person(user_id, person_id)
    if person is None:
        return {"status": "FORBIDDEN_OR_NOT_FOUND", "message": "접근 가능한 해당 인물 기록이 없습니다."}
    if event_type not in DEMO["event_categories"]:
        return {"status": "INVALID_EVENT_TYPE", "message": "지원하지 않는 행사입니다."}
    if legal_risk:
        return {"status": "LEGAL_REVIEW_REQUIRED", "message": "직무 관련 청탁금지법 적용 여부를 먼저 검토해야 합니다."}
    if event_type == "결혼" and attendance_with_meal is None:
        return {"status": "NEEDS_ATTENDANCE_CONTEXT", "message": "결혼식 참석·식사 여부를 선택해 주세요."}
    if budget_krw is not None and budget_krw < 0:
        return {"status": "INVALID_BUDGET", "message": "예산은 음수가 될 수 없습니다."}
    own_events = {e["id"]: e for e in DEMO["private_events"] if e["owner_user_id"] == user_id}
    transactions = [t for t in DEMO["transactions"] if t["owner_user_id"] == user_id and t["private_event_id"] in own_events]
    same_person = [t for t in transactions if t["contact_person_id"] == person_id]
    paid = [t for t in same_person if t["direction"] == "paid"]
    received = [t for t in same_person if t["direction"] == "received"]
    # 관계 시연 거래는 해당 인물의 이력에만 반영해 기존 추천의 기준값을 보존한다.
    is_relationship_demo = "relationship_context" in person
    same_type = [t for t in transactions if t["direction"] == "paid"
                 and own_events[t["private_event_id"]]["category"] == event_type
                 and (t["contact_person_id"] == person_id if is_relationship_demo
                      else not t["id"].startswith("V4T"))]
    per_type_med = _positive_median(same_type)
    paid_med = _positive_median(paid)
    received_med = _positive_median(received)

    survey = kb.eligible_amount_source(event_type=event_type, relationship=person["relationship"], attendance_with_meal=attendance_with_meal)
    survey_shares = ({f["amount_krw"]: f["pct"] / 100 for f in survey["facts"] if f["metric"] == "perceived_amount_share"} if survey else {})
    if not survey_shares and paid_med is None and received_med is None:
        return {"status": "INSUFFICIENT_EVIDENCE", "message": "일치하는 설문이나 해당 인물의 과거 금전 이력이 없어 금액 추천을 보류합니다."}
    weights = {k: v for k, v in RAW_WEIGHTS.items() if
               (k == "matched_survey" and bool(survey_shares)) or
               (k == "same_type_paid" and per_type_med is not None) or
               (k == "paid_to_person" and paid_med is not None) or
               (k == "received_from_person" and received_med is not None)}
    denom = sum(weights.values())
    weights = {k: v / denom for k, v in weights.items()}
    affordable = [a for a in AMOUNTS if budget_krw is None or a <= budget_krw]
    if not affordable:
        return {"status": "NO_AFFORDABLE_CANDIDATE", "message": "설정한 예산 내 기본 후보가 없습니다. 축하·위로 메시지 등 비금전적 대안도 고려해 주세요."}

    def calc(amount):
        signals = {}
        if "matched_survey" in weights:
            signals["matched_survey"] = survey_shares.get(amount, 0.0) / max(survey_shares.values())
        if "same_type_paid" in weights:
            signals["same_type_paid"] = _closeness(amount, per_type_med)
        if "paid_to_person" in weights:
            signals["paid_to_person"] = _closeness(amount, paid_med)
        if "received_from_person" in weights:
            signals["received_from_person"] = _closeness(amount, received_med)
        return round(sum(weights[k] * signals[k] for k in weights), 6)

    baseline_ranked = sorted(affordable, key=lambda a: (-calc(a), a))
    baseline_amount = baseline_ranked[0]
    context = person.get("relationship_context") or {}
    closeness = closeness_override if closeness_override is not None else context.get("closeness_score")
    adjustments = []
    upward = 0
    downward = 0
    if isinstance(closeness, int) and not isinstance(closeness, bool) and closeness == 5:
        upward += 1
        adjustments.append({"signal": "closeness", "direction": "up", "reason": "현재 친밀도 5/5를 고려했습니다."})
    if paid_med and received_med and len(received) >= 2 and received_med >= paid_med * 1.5:
        upward += 1
        adjustments.append({"signal": "reciprocity", "direction": "up", "reason": "상대에게 받은 금액의 중앙값이 내가 낸 금액보다 높습니다."})
    dated_received = sorted(received, key=lambda t: (own_events[t["private_event_id"]]["start_date"], t["id"]))
    if len(dated_received) >= 3:
        from statistics import median as _median
        preceding = _median(t["amount_krw"] for t in dated_received[:-1] if t["amount_krw"] > 0)
        latest = dated_received[-1]["amount_krw"]
        if preceding and latest >= preceding * 2:
            upward += 2 if latest >= preceding * 3 else 1
            adjustments.append({"signal": "recent_large_gift", "direction": "up",
                                "reason": "최근 받은 금액이 이전 수령 중앙값의 2배 이상입니다."})
    closeness_history = context.get("closeness_history") or []
    if (isinstance(closeness, int) and closeness <= 2 and len(closeness_history) >= 2
            and closeness_history[0].get("score", 0) > closeness):
        downward += 1
        adjustments.append({"signal": "relationship_drift", "direction": "down",
                            "reason": "사용자가 기록한 현재 친밀도가 과거보다 낮습니다."})
    if special_care and (context.get("non_monetary_support") or (isinstance(closeness, int) and closeness >= 4)):
        upward += 1
        adjustments.append({"signal": "special_care", "direction": "up",
                            "reason": "사용자가 특별히 챙기겠다는 의향을 밝혔습니다."})
    steps = max(-2, min(2, upward - downward))
    target = AMOUNTS[max(0, min(len(AMOUNTS) - 1, AMOUNTS.index(baseline_amount) + steps))]
    eligible_target = min((a for a in affordable if a >= target), default=affordable[-1])
    if target > affordable[-1]:
        eligible_target = affordable[-1]
    if not adjustments:
        ranked = baseline_ranked
    else:
        ranked = sorted(affordable, key=lambda a: (abs(AMOUNTS.index(a) - AMOUNTS.index(eligible_target)), -calc(a), a))
    tx_ids = list(dict.fromkeys(t["id"] for t in (same_person + same_type)))
    reasons = []
    if survey:
        reasons.append("직장 동료의 결혼식에 참석해 식사하는 조건에 맞는 설문을 참고했습니다.")
    if paid:
        reasons.append(f"해당 인물에게 보낸 거래가 {len(paid)}건 있고 총 {sum(t['amount_krw'] for t in paid):,}원입니다.")
    if received:
        reasons.append(f"해당 인물에게 받은 거래가 {len(received)}건 있고 총 {sum(t['amount_krw'] for t in received):,}원입니다.")
    if same_type:
        reasons.append(f"같은 행사 종류의 과거 지급 기록 {len(same_type)}건을 참고했습니다.")
    if budget_krw is not None:
        reasons.append(f"예산 {budget_krw:,}원을 초과하는 후보는 제외했습니다.")
    if not survey:
        reasons.append("해당 상황에 직접 일치하는 공개 금액 설문이 없어 개인 이력 중심으로 계산했습니다.")
    if adjustments:
        reasons.extend(item["reason"] for item in adjustments)
    level = "moderate" if survey else "low"
    return {"status": "RECOMMENDED", "amount_krw": ranked[0], "alternatives_krw": ranked[1:3],
            "baseline_amount_krw": baseline_amount, "personalized_amount_krw": ranked[0],
            "relationship_adjustments": adjustments,
            "scores": [{"amount_krw": a, "score": (
                round(1 - abs(AMOUNTS.index(a) - AMOUNTS.index(eligible_target)) / len(AMOUNTS) + calc(a) / 100, 6)
                if adjustments else calc(a))} for a in ranked],
            "evidence_level": level, "weights_used": {k: round(v, 4) for k, v in weights.items()},
            "matched_source_id": survey["id"] if survey else None,
            "matched_transaction_ids": tx_ids,
            "personal_history": {"paid_count": len(paid), "paid_total_krw": sum(t["amount_krw"] for t in paid),
                                "received_count": len(received), "received_total_krw": sum(t["amount_krw"] for t in received),
                                "explicit_zero_paid_count": sum(t["amount_krw"] == 0 for t in paid)},
            "reasons": reasons,
            "disclaimer": "검증된 예측 모델이 아닌 규칙 기반 추천 시연입니다. 적정 금액이나 법적 적합성을 보장하지 않습니다."}
