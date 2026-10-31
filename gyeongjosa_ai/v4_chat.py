"""사전 등록된 열 가지 가상 상황을 자유 상담에서 v4 엔진으로 연결한다."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.knowledge import KB
from app.main import RecommendationRequest, recommendation
from app.special_cases import assess_special

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    row["id"]: row for row in
    json.loads((ROOT / "data" / "v4_chat_scenarios.json").read_text(encoding="utf-8"))["scenarios"]
}
DEMO_MARKERS = ("가상", "시나리오", "시연", "데모")
RISK_TERMS = ("계약", "입찰", "심사", "평가", "거래처", "발주", "이해충돌")
PUBLIC_TERMS = ("공직자", "공무원", "부조 예외", "청탁금지법", "직무 관련")
GENERAL_TERMS = ("직장 동료", "직장동료", "동료 결혼", "김도윤")
MONEY = re.compile(r"(\d[\d,]*)\s*(만)?\s*원")
BUDGET = re.compile(r"예산|최대|상한|낼\s*수\s*있는|지출\s*가능|금액\s*수정")
CHANGE = re.compile(r"바꿔|바꿀|수정|줄여|높여|올려|낮춰")
TOPIC = re.compile(r"예산|원|참석|식사|부의|조의|조화|화환|결혼|장례|다시|근거|얼마|추천|상대|법적|부친상|돌잔치|계약")


def _detected(text: str) -> str | None:
    """특별 사례의 고유 단서를 기존 일반 키워드보다 먼저 적용한다."""
    for identifier in (
        "teacher_parent", "sender_public", "private_occupation", "cash_and_wreath",
        "public_dol", "duplicate_mourner", "ended_contract",
    ):
        if any(word in text for word in SCENARIOS[identifier]["keywords"]):
            return identifier
    if "돌잔치" in text and any(w in text for w in ("공직자", "공무원", "직무 관련")):
        return "public_dol"
    if "조화" in text and any(w in text for w in ("조의금", "현금", "축의금")):
        return "cash_and_wreath"
    if "담임" in text and "축의금" in text:
        return "teacher_parent"
    if any(word in text for word in SCENARIOS["public_exception"]["keywords"]):
        return "public_exception"
    if any(word in text for word in SCENARIOS["procurement"]["keywords"]) or (
        any(word in text for word in RISK_TERMS)
    ):
        return "procurement"
    if any(word in text for word in PUBLIC_TERMS):
        return "public_exception"
    if (any(word in text for word in GENERAL_TERMS) and "결혼" in text) or (
        any(word in text for word in DEMO_MARKERS) and ("일반" in text or "결혼" in text)
    ):
        return "general"
    return None


def _amount(text: str, *, followup: bool) -> int | None:
    """단순 법적 기준 숫자가 예산으로 오인되지 않도록 한다."""
    match = MONEY.search(text)
    if not match:
        return None
    if not BUDGET.search(text) and not (
        followup and (CHANGE.search(text) or MONEY.fullmatch(text.strip()))
    ):
        return None
    return int(match.group(1).replace(",", "")) * (10000 if match.group(2) else 1)


def _gift_amount(text: str, kinds: tuple[str, ...]) -> int | None:
    """현금과 조화 금액을 각각 추출한다."""
    pattern = r"(?:" + "|".join(kinds) + r")\s*(\d[\d,]*)\s*(만)?\s*원"
    match = re.search(pattern, text)
    if not match:
        return None
    return int(match.group(1).replace(",", "")) * (10000 if match.group(2) else 1)


def _question(message: str, state: dict, field: str, options: list | None = None) -> dict:
    """답변을 보류하고 확인할 필드를 현재 대화에 보존한다."""
    state["pending_field"] = field
    return {
        "status": "need_more_info", "message": message, "pending_field": field,
        "options": options or [], "context": state, "intent": "amount",
    }


def try_v4_chat(user_id: str, text: str, old_context: dict) -> dict | None:
    """가상 시연임이 명확한 경우에만 등록된 인물과 v4 정책을 사용한다."""
    current = old_context.get("v4_scenario")
    if current not in SCENARIOS:
        current = None
    marker = any(word in text for word in DEMO_MARKERS)
    candidate = _detected(text)
    if current and candidate and candidate != current:
        if not marker:
            return _question(
                "다른 가상 인물로 전환할까요? 이전 예산·직무 조건은 이어받지 않습니다.",
                {}, "v4_scenario",
                [{"id": candidate, "label": f"가상 {SCENARIOS[candidate]['name']} 전환"}],
            )
        current = None
        old_context = {}
    if current and candidate is None and not TOPIC.search(text) and old_context.get("pending_field") != "v4_person":
        return None
    if not current and not candidate:
        return None
    if user_id != "U001":
        return {
            "status": "need_more_info",
            "message": "가상 v4 시연은 U001 계정에서만 실행됩니다. 다른 계정의 인물을 연결하지 않습니다.",
            "context": {}, "options": [],
        }

    state = {
        key: value for key, value in old_context.items()
        if key in {"v4_scenario", "budget_krw", "v4_attendance", "event_type",
                   "pending_field", "cash_krw", "wreath_krw", "v4_person"}
    }
    if current is None:
        if not marker and state.get("v4_scenario") not in SCENARIOS:
            return _question(
                "기존 가상 인물의 시연 상황으로 진행할까요? 실제 사실로 확정하지 않습니다.",
                {}, "v4_scenario",
                [{"id": candidate, "label": f"가상 {SCENARIOS[candidate]['name']} 시연"}],
            )
        current = candidate or state.get("v4_scenario")
        if current not in SCENARIOS:
            return None
        state = {"v4_scenario": current}
    state["v4_scenario"] = current
    state.pop("pending_field", None)

    budget = _amount(text, followup=bool(old_context.get("v4_scenario")))
    if budget is not None:
        if budget > 10000000:
            return _question("예산은 1,000만 원 이하로 입력해 주세요.", state, "budget_krw")
        state["budget_krw"] = budget
    if any(term in text for term in ("장례", "부친상", "모친상", "부의", "조의", "조문")):
        state["event_type"] = "장례"
    elif "결혼" in text:
        state["event_type"] = "결혼"

    if current == "duplicate_mourner" and state.get("v4_person") not in {"P001", "P002"}:
        return _question(
            "동명이인 김도윤 두 명 중 부고의 상주가 누구인지 확인해 주세요.",
            state, "v4_person",
            [{"id": "P001", "label": "직장 동료 김도윤 (해든기획팀)"},
             {"id": "P002", "label": "독서모임 김도윤 (솔빛독서모임)"}],
        )
    if current == "general":
        if old_context.get("v4_attendance") in ("yes", "no"):
            state["v4_attendance"] = old_context["v4_attendance"]
        if any(term in text for term in ("식사하지", "식사 안", "불참", "못 가", "참석 안")):
            state["v4_attendance"] = "no"
        elif any(term in text for term in ("식사해", "식사하", "밥도 먹", "밥 먹", "식사 예정")):
            state["v4_attendance"] = "yes"
        if state.get("v4_attendance") not in ("yes", "no"):
            return _question(
                "이 가상 결혼식에 참석해 식사하나요?", state, "v4_attendance",
                [{"id": "yes", "label": "참석하여 식사"}, {"id": "no", "label": "식사하지 않음"}],
            )
    if current == "cash_and_wreath":
        cash = _gift_amount(text, ("조의금", "축의금", "현금"))
        wreath = _gift_amount(text, ("조화", "화환"))
        if cash is not None:
            state["cash_krw"] = cash
        if wreath is not None:
            state["wreath_krw"] = wreath
        if state.get("cash_krw") is None or state.get("wreath_krw") is None:
            return _question("조의금과 조화 금액을 각각 알려 주세요. 예: 조의금 5만원, 조화 5만원", state, "v4_gifts")
        if max(state["cash_krw"], state["wreath_krw"]) > 10000000:
            return _question("개별 금액은 1,000만 원 이하로 입력해 주세요.", state, "v4_gifts")
    if current in ("general", "public_exception") and state.get("budget_krw") is None:
        return _question("이번 경조사에 사용할 최대 예산을 알려 주세요.", state, "budget_krw")

    scenario = SCENARIOS[current]
    person_id = state.get("v4_person") if current == "duplicate_mourner" else scenario["person_id"]
    event_type = state.get("event_type") or scenario["event_type"]
    attendance = state.get("v4_attendance") == "yes" if current == "general" else None
    if event_type == "결혼" and attendance is None and current in ("general", "public_exception"):
        return _question(
            "결혼식에서 식사할 예정인지 알려 주세요.", state, "v4_attendance",
            [{"id": "yes", "label": "식사함"}, {"id": "no", "label": "식사하지 않음"}],
        )
    if current != "general" and old_context.get("v4_attendance") in ("yes", "no"):
        attendance = old_context["v4_attendance"] == "yes"

    request = RecommendationRequest(
        demo_user_id=user_id, person_id=person_id, identity_confirmed=True,
        event_type=event_type, attendance_with_meal=attendance,
        budget_krw=state.get("budget_krw"),
        scenario_id=scenario["scenario_id"], explanation_mode="offline",
        duty_context="contract_active" if current == "sender_public" else "unknown",
        relationship_text="가상 과거 계약 종료, 현재 후속 업무 관계 미확인" if current == "ended_contract" else "",
        allow_llm_analysis=False,
    )
    report = recommendation(request)
    result = report["result"]
    legal = dict(result.get("legal_assessment") or {})
    status = result["status"]
    amount = result.get("amount_krw") if status == "RECOMMENDED" else None

    special = assess_special(current, cash_krw=state.get("cash_krw"),
                             wreath_krw=state.get("wreath_krw"))
    if special:
        legal.update(special)
        legal["is_hypothetical"] = True
        status = special["status"]
        amount = None
    elif status != "RECOMMENDED" and legal.get("status") in (
        "NEEDS_FACTS", "NEEDS_EXPERT_REVIEW", "POTENTIALLY_PROHIBITED",
    ):
        status = legal["status"]
    if amount is not None and state.get("budget_krw") is not None and amount > state["budget_krw"]:
        raise ValueError("추천액이 사용자 예산을 초과했습니다.")

    evidence = [{
        "id": entry["id"], "kind": entry.get("publisher", "공개 근거"),
        "text": entry.get("title", ""), "url": entry.get("url"),
        "decision_role": entry.get("decision_role"),
    } for entry in report["evidence"]]
    if special:
        for source_id in special["source_ids"]:
            doc = KB.by_id[source_id]
            if not any(row["id"] == source_id for row in evidence):
                evidence.append({"id": source_id, "kind": doc["publisher"],
                                 "text": doc["title"], "url": doc["url"],
                                 "decision_role": "applied_legal"})
    if special:
        explanation = special["reason"]
    else:
        explanation = report["explanation"]
    if amount is not None:
        message = f"[가상 시연: {scenario['name']}] 참고 추천액은 {amount:,}원입니다. {explanation}"
    elif status == "CONDITIONALLY_ALLOWED":
        message = f"[가상 시연: {scenario['name']}] 금액 조건만 검토했습니다. {explanation}"
    else:
        message = f"[가상 시연: {scenario['name']}] 행동 금액 추천을 보류합니다. {explanation}"
    return {
        "status": "answer", "intent": "amount", "message": message,
        "suggested_amount_krw": amount, "evidence": evidence,
        "context": state, "model": None,
        "v4_analysis": {
            "scenario": current, "person_id": person_id, "status": status,
            "amount_krw": amount, "legal_assessment": legal,
            "missing_questions": legal.get("missing_questions", []),
            "evidence_trace": result.get("evidence_trace"), "demo_only": True,
        },
    }
