"""사전 등록된 세 가지 가상 상황을 자유 상담에서 v4 엔진으로 연결한다."""
from __future__ import annotations

import re

from app.main import RecommendationRequest, recommendation

SCENARIOS = {
    "general": {
        "name": "직장 동료 결혼식",
        "person_id": "P001",
        "scenario_id": "default",
        "event_type": "결혼",
    },
    "public_exception": {
        "name": "공직자 부조 예외 성립 가정",
        "person_id": "P004",
        "scenario_id": "chat_public_exception",
        "event_type": "장례",
    },
    "procurement": {
        "name": "계약·심사 이해관계 가정",
        "person_id": "P005",
        "scenario_id": "chat_public_procurement",
        "event_type": "장례",
    },
}
DEMO_MARKERS = ("가상", "시나리오", "시연", "데모")
RISK_TERMS = ("계약", "입찰", "심사", "평가", "거래처", "발주", "이해충돌")
PUBLIC_TERMS = ("공직자", "공무원", "부조 예외", "청탁금지법", "직무 관련")
GENERAL_TERMS = ("직장 동료", "직장동료", "동료 결혼", "김도윤")
MONEY = re.compile(r"(\d[\d,]*)\s*(만)?\s*원")
BUDGET = re.compile(r"예산|최대|상한|낼\s*수\s*있는|지출\s*가능|금액\s*수정")
CHANGE = re.compile(r"바꿔|바꿀|수정|줄여|높여|올려|낮춰")


def _detected(text: str) -> str | None:
    """자연어의 시연 상황을 후보로만 분류한다."""
    if any(word in text for word in RISK_TERMS):
        return "procurement"
    if any(word in text for word in PUBLIC_TERMS):
        return "public_exception"
    if any(word in text for word in GENERAL_TERMS) and "결혼" in text:
        return "general"
    if any(word in text for word in DEMO_MARKERS) and ("일반" in text or "결혼" in text):
        return "general"
    return None


def _amount(text: str, *, followup: bool) -> int | None:
    """예산과 법적 가액 기준의 숫자를 혼동하지 않는다."""
    match = MONEY.search(text)
    if not match:
        return None
    if not BUDGET.search(text) and not (
        followup and (CHANGE.search(text) or MONEY.fullmatch(text.strip()))
    ):
        return None
    return int(match.group(1).replace(",", "")) * (10000 if match.group(2) else 1)


def _question(message: str, state: dict, field: str, options: list | None = None) -> dict:
    """추가 확인이 필요한 경우 채팅 상태를 보존한다."""
    state["pending_field"] = field
    return {
        "status": "need_more_info", "message": message, "pending_field": field,
        "options": options or [], "context": state, "intent": "amount",
    }


def try_v4_chat(user_id: str, text: str, old_context: dict) -> dict | None:
    """선택 또는 명시적으로 확인된 가상 시나리오만 v4로 보낸다."""
    current = old_context.get("v4_scenario")
    if current not in SCENARIOS:
        current = None
    marker = any(word in text for word in DEMO_MARKERS)
    candidate = _detected(text)
    if current and candidate and candidate != current:
        if not marker:
            return _question(
                "다른 가상 인물의 상황으로 전환할까요? 이전 예산과 직무 조건은 이어받지 않습니다.",
                {}, "v4_scenario",
                [{"id": candidate, "label": f"가상 {SCENARIOS[candidate]['name']} 전환"}],
            )
        current = None
        old_context = {}
    if current and candidate is None and not re.search(
        r"예산|원|참석|식사|부의|조의|결혼|장례|다시|근거|얼마|추천|상대|법적", text
    ):
        return None
    if not current and not candidate:
        return None
    if user_id != "U001":
        return {
            "status": "need_more_info",
            "message": "세 가지 v4 합성 시연은 가상 계정 U001에서 사용할 수 있습니다. 다른 계정의 인물은 임의로 연결하지 않습니다.",
            "context": {}, "options": [],
        }
    state = {
        key: value for key, value in old_context.items()
        if key in {"v4_scenario", "budget_krw", "v4_attendance", "event_type", "pending_field"}
    }
    if current is None:
        if not marker and state.get("v4_scenario") not in SCENARIOS:
            return _question(
                "등록된 가상 인물을 사용하는 시연으로 진행할까요? 일반 상담의 실제 사실로 간주하지 않습니다.",
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

    if current == "general":
        if old_context.get("v4_attendance") in ("yes", "no"):
            state["v4_attendance"] = old_context["v4_attendance"]
        if any(term in text for term in ("식사하지", "식사 안", "불참", "못 가", "참석 안")):
            state["v4_attendance"] = "no"
        elif any(term in text for term in ("식사해", "식사하", "밥도 먹", "밥 먹", "식사 예정")):
            state["v4_attendance"] = "yes"
        if state.get("v4_attendance") not in ("yes", "no"):
            return _question(
                "이 가상 결혼식에 참석해 식사하나요?",
                state, "v4_attendance",
                [{"id": "yes", "label": "참석하여 식사"}, {"id": "no", "label": "식사하지 않음"}],
            )
    if current != "procurement" and state.get("budget_krw") is None:
        return _question("이번 경조사에 사용할 최대 예산을 알려 주세요.", state, "budget_krw")

    scenario = SCENARIOS[current]
    event_type = state.get("event_type") or scenario["event_type"]
    attendance = (state.get("v4_attendance") == "yes") if current == "general" else None
    if event_type == "결혼" and attendance is None:
        return _question(
            "결혼식에서 식사할 예정인지 알려 주세요.",
            state, "v4_attendance",
            [{"id": "yes", "label": "식사함"}, {"id": "no", "label": "식사하지 않음"}],
        )
    if current != "general" and old_context.get("v4_attendance") in ("yes", "no"):
        attendance = old_context["v4_attendance"] == "yes"

    request = RecommendationRequest(
        demo_user_id=user_id, person_id=scenario["person_id"],
        identity_confirmed=True, event_type=event_type,
        attendance_with_meal=attendance, budget_krw=state.get("budget_krw"),
        scenario_id=scenario["scenario_id"], explanation_mode="offline",
        allow_llm_analysis=False,
    )
    report = recommendation(request)
    result = report["result"]
    status = result["status"]
    amount = result.get("amount_krw") if status == "RECOMMENDED" else None
    if amount is not None and (state.get("budget_krw") is not None and amount > state["budget_krw"]):
        raise ValueError("추천액이 사용자 예산을 초과했습니다.")
    if amount is not None:
        message = f"[가상 시연: {scenario['name']}] 참고 추천액은 {amount:,}원입니다. {report['explanation']}"
    else:
        message = f"[가상 시연: {scenario['name']}] 금액 추천을 보류합니다. {report['explanation']}"
    sources = [{
        "id": entry["id"], "kind": entry.get("publisher", "공개 근거"),
        "text": entry.get("title", ""), "url": entry.get("url"),
        "decision_role": entry.get("decision_role"),
    } for entry in report["evidence"]]
    return {
        "status": "answer", "intent": "amount", "message": message,
        "suggested_amount_krw": amount, "evidence": sources,
        "context": state, "model": None,
        "v4_analysis": {
            "scenario": current, "person_id": scenario["person_id"],
            "status": status, "amount_krw": amount,
            "legal_assessment": result.get("legal_assessment"),
            "missing_questions": result.get("missing_questions", []),
            "evidence_trace": result.get("evidence_trace"),
            "demo_only": True,
        },
    }
