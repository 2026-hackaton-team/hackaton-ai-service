"""사전 등록된 스무 가지 가상 상황을 자유 상담에서 분석한다."""
from __future__ import annotations

from app.knowledge import KB
from app.main import RecommendationRequest, recommendation
from app.special_cases import assess_special
from . import seed_db
from .ai import ModelUnavailable
from .relationship_insights import analyze_relationship_case

SCENARIOS = {
    row["id"]: row for row in
    seed_db.load("v4_chat_scenarios")["scenarios"]
}
DEMO_MARKERS = ("가상", "시나리오", "시연", "데모")
RISK_TERMS = ("계약", "입찰", "심사", "평가", "거래처", "발주", "이해충돌")
PUBLIC_TERMS = ("공직자", "공무원", "부조 예외", "청탁금지법", "직무 관련")
GENERAL_TERMS = ("직장 동료", "직장동료", "동료 결혼", "김도윤")
BUDGET_TERMS = ("예산", "최대", "상한", "낼 수 있는", "지출 가능", "금액 수정")
CHANGE_TERMS = ("바꿔", "바꿀", "수정", "줄여", "높여", "올려", "낮춰")
TOPIC_TERMS = ("예산", "원", "참석", "식사", "부의", "조의", "조화", "화환", "결혼",
               "장례", "다시", "근거", "얼마", "추천", "상대", "법적", "부친상",
               "돌잔치", "계약", "관계", "서운", "받", "내", "도움", "친밀",
               "친구", "감사", "보답", "의미", "부담", "걱정", "왜")


def _money_spans(text: str) -> list[tuple[int, int, int]]:
    """정규식 없이 원·만원 표현의 위치와 정수 금액을 추출한다."""
    spans = []
    index = 0
    while index < len(text):
        if not text[index].isdigit():
            index += 1
            continue
        start = index
        while index < len(text) and (text[index].isdigit() or
                                     text[index] == "," and index + 1 < len(text) and text[index + 1].isdigit()):
            index += 1
        number = int(text[start:index].replace(",", ""))
        end = index
        while end < len(text) and text[end].isspace():
            end += 1
        if end < len(text) and text[end] == "만":
            end += 1
            while end < len(text) and text[end].isspace():
                end += 1
            if end < len(text) and text[end] == "원":
                end += 1
            spans.append((start, end, number * 10000))
        elif end < len(text) and text[end] == "원":
            spans.append((start, end + 1, number))
    return spans


def _budget_reply(text: str) -> bool:
    """후속 답변의 숫자·단위·종결 어미만 허용한다."""
    value = text.strip().rstrip(".!?").strip()
    for suffix in ("이에요", "입니다", "이요", "정도"):
        if value.endswith(suffix):
            value = value[:-len(suffix)].strip()
            break
    for unit in ("만원", "만 원", "만", "원"):
        if value.endswith(unit):
            value = value[:-len(unit)].strip()
            break
    return bool(value) and value.replace(",", "").isdigit()


def _closeness(text: str) -> int | None:
    """명시적인 친밀도 점수만 가상 시연 조건으로 사용한다."""
    compact = "".join(text.split())
    marker = compact.find("친밀도")
    if marker < 0:
        return None
    tail = compact[marker + len("친밀도"):]
    if tail[:1] in ("는", "가", "를"):
        tail = tail[1:]
    if tail[:1] in ("1", "2", "3", "4", "5") and tail[1:].startswith(("점", "/5")):
        return int(tail[0])
    return None


def _recent_received(text: str) -> int | None:
    """최근에 받았다고 명시한 금액만 시연용 변경 값으로 취급한다."""
    for start, end, value in _money_spans(text):
        previous = text[max(0, start - 40):start]
        following = text[end:end + 8]
        if any(term in previous for term in ("최근", "지난번")) and "받" in following and value <= 10000000:
            return value
    return None

def _detected(text: str) -> str | None:
    """관계 사례와 특수 법적 사례의 고유 표현을 우선 분류한다."""
    from app.recommender import owned_person
    for identifier, scenario in SCENARIOS.items():
        if identifier.startswith("relation_"):
            person = owned_person("U001", scenario["person_id"])
            if person and person["name"] in text:
                return identifier
    for identifier in SCENARIOS:
        if identifier.startswith("relation_") and any(
            word in text for word in SCENARIOS[identifier]["keywords"]
        ):
            return identifier
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
    """예산 표시가 있는 금액이나 명시적인 후속 예산만 채택한다."""
    amounts = _money_spans(text)
    markers = [(at, at + len(term)) for term in BUDGET_TERMS
               for at in range(len(text)) if text.startswith(term, at)]
    if markers:
        forward = [(start - end, value)
                   for _, end in markers for start, _, value in amounts
                   if 0 <= start - end <= 35]
        if forward:
            return min(forward, key=lambda item: item[0])[1]
        before = [(start - end, value)
                  for start, _ in markers for _, end, value in amounts
                  if 0 <= start - end <= 12]
        return min(before, key=lambda item: item[0])[1] if before else None
    if followup and _budget_reply(text):
        if amounts:
            return amounts[-1][2]
        return int(text.strip().rstrip(".!?").strip().replace(",", ""))
    if followup and any(term in text for term in CHANGE_TERMS) and amounts:
        return amounts[-1][2]
    return None


def _gift_amount(text: str, kinds: tuple[str, ...]) -> int | None:
    """현금·조화 명칭 바로 뒤에 적힌 금액만 분리한다."""
    for start, _, value in _money_spans(text):
        if any(text[max(0, start - len(kind) - 2):start].strip().endswith(kind) for kind in kinds):
            return value
    return None


def _question(message: str, state: dict, field: str, options: list | None = None) -> dict:
    """답변을 보류하고 확인할 필드를 현재 대화에 보존한다."""
    state["pending_field"] = field
    return {
        "status": "need_more_info", "message": message, "pending_field": field,
        "options": options or [], "context": state, "intent": "amount",
    }


def _with_llm_analysis(response: dict, gateway, question: str, scenario: dict,
                       *, facts: dict, known_amounts: list) -> dict:
    """서버 판정값은 유지하고 실제 모델의 사례별 해석만 덧붙인다."""
    details = response["v4_analysis"]
    details["ai_status"] = "not_configured"
    if gateway is None or not getattr(gateway, "api_key", None):
        return response
    payload = {
        "question": question,
        "scenario": scenario["name"],
        "category": scenario.get("category"),
        "facts": facts,
        "decision": {
            "status": details["status"],
            "suggested_amount_krw": response["suggested_amount_krw"],
            "legal_assessment": details.get("legal_assessment"),
        },
        "evidence": response["evidence"],
        "known_amounts_krw": sorted({item for item in known_amounts if type(item) is int}),
    }
    try:
        generated = gateway.explain_scenario(payload)
    except ModelUnavailable:
        details["ai_status"] = "unavailable"
        return response
    details["ai_status"] = "generated"
    response["model"] = generated["model"]
    response["message"] += "\n\nAI 해석: " + generated["analysis"]
    return response


def try_v4_chat(user_id: str, text: str, old_context: dict, gateway=None) -> dict | None:
    """가상 시연임이 명확한 경우에만 등록된 인물과 v4 정책을 사용한다."""
    current = old_context.get("v4_scenario")
    if current not in SCENARIOS:
        current = None
    marker = any(word in text for word in DEMO_MARKERS)
    # 자연어 직무·계약 질문을 가상 고정 시나리오로 강제로 전환하지 않는다.
    if current is None and not marker:
        return None
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
    if (current and candidate is None and not any(term in text for term in TOPIC_TERMS)
            and not _budget_reply(text)
            and old_context.get("pending_field") not in ("v4_person", "v4_scenario")):
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
                   "pending_field", "cash_krw", "wreath_krw", "v4_person",
                   "relationship_closeness", "relationship_special_care",
                   "recent_received_override"}
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

    if current.startswith("relation_"):
        # 현재 대화의 직접 입력은 가상 기록과 구분해 임시 개인화 조건으로 사용한다.
        closeness = _closeness(text)
        if closeness is not None:
            state["relationship_closeness"] = closeness
        if any(term in "".join(text.split()) for term in ("특별히챙기", "더챙기", "특별하게보답")):
            state["relationship_special_care"] = True
        recent = _recent_received(text)
        if recent is not None:
            state["recent_received_override"] = recent
        scenario = SCENARIOS[current]
        person_id = scenario["person_id"]
        insights = analyze_relationship_case(
            user_id=user_id, person_id=person_id, scenario_id=current
        )
        money = state.get("budget_krw")
        amount = None
        legal = None
        if money is not None:
            request = RecommendationRequest(
                demo_user_id=user_id, person_id=person_id,
                identity_confirmed=True, event_type=scenario["event_type"],
                budget_krw=money, scenario_id="default", explanation_mode="offline",
                allow_llm_analysis=False,
                closeness_override=state.get("relationship_closeness"),
                special_care=bool(state.get("relationship_special_care")),
                recent_received_override=state.get("recent_received_override"),
            )
            report = recommendation(request)
            result = report["result"]
            status = result["status"]
            legal = result.get("legal_assessment")
            amount = result.get("amount_krw") if status == "RECOMMENDED" else None
            if amount is not None and amount > money:
                raise ValueError("추천액이 사용자 예산을 초과했습니다.")
        else:
            status = "RELATIONSHIP_INSIGHT"
        if money is None:
            conclusion = "예산을 알려 주시면 기존 추천 엔진으로 상한을 지키는 참고 금액을 계산할 수 있습니다."
        elif amount is not None:
            baseline = result.get("baseline_amount_krw")
            difference = f" (과거 이력 기준 {baseline:,}원에서 개인화 조정)" if baseline is not None and baseline != amount else ""
            conclusion = f"이번 예산 {money:,}원 안의 참고액은 {amount:,}원{difference}입니다. 과거 거래액과 같게 돌려줄 의무는 없습니다."
        else:
            conclusion = f"이번 예산 {money:,}원과 확인 가능한 근거에서는 행동 금액 추천을 보류합니다."
        message = f"[가상 관계 시연: {scenario['name']}] " + " ".join(insights["messages"]) + " " + conclusion
        evidence = [
            {"id": row["id"], "kind": "사용자 소유 가상 거래",
             "text": f"{row['date']} · {'낸 금액' if row['direction']=='paid' else '받은 금액'} {row['amount_krw']:,}원",
             "decision_role": "personal_history"}
            for row in insights["history"]
        ]
        if state.get("recent_received_override") is not None:
            evidence.append({"id": "claim:" + person_id, "kind": "사용자 자기신고 수령액",
                             "text": f"직접 말한 최근 수령액 {state['recent_received_override']:,}원(기록 미확인)",
                             "decision_role": "user_reported"})
        if insights["relationship_note"]:
            evidence.append({
                "id": "note:" + person_id, "kind": "사용자 입력 관계 메모",
                "text": insights["relationship_note"], "decision_role": "user_recorded",
            })
        # 연구 자료는 관계 설명에만 사용하고 금액 가중치로 전환하지 않는다.
        guidance = [doc for doc in KB.retrieve(
            f"{scenario['name']} {text} 친구 호혜성 선물 감사",
            event_type=scenario["event_type"], top_k=10
        ) if doc["source_type"] == "relationship_guidance"][:3]
        for doc in guidance:
            evidence.append({"id": doc["id"], "kind": "인간관계 연구",
                             "text": doc["excerpt"], "url": doc["url"],
                             "decision_role": "relationship_guidance"})
        if money is not None:
            for adjustment in result.get("relationship_adjustments", []):
                evidence.append({"id": "adjustment:" + adjustment["signal"],
                                 "kind": "개인화 추천 규칙", "text": adjustment["reason"],
                                 "decision_role": "personalization"})
        summary = {key: value for key, value in insights.items() if key != "history"}
        response = {
            "status": "answer", "intent": "amount", "message": message,
            "suggested_amount_krw": amount, "evidence": evidence,
            "context": state, "model": None,
            "v4_analysis": {
                "scenario": current, "person_id": person_id, "status": status,
                "amount_krw": amount, "legal_assessment": legal,
                "baseline_amount_krw": result.get("baseline_amount_krw") if money is not None else None,
                "relationship_adjustments": result.get("relationship_adjustments", []) if money is not None else [],
                "relationship_insights": summary, "demo_only": True,
            },
        }
        return _with_llm_analysis(
            response, gateway, text, scenario, facts=insights,
            known_amounts=(
                [row["amount_krw"] for row in insights["history"]] +
                [insights["paid_average_krw"], insights["received_average_krw"],
                 insights["comparison_reference_krw"], state.get("budget_krw"),
                 state.get("recent_received_override"), amount,
                 result.get("baseline_amount_krw") if money is not None else None]
            ),
        )

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
    response = {
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

    return _with_llm_analysis(
        response, gateway, text, scenario,
        facts={"explanation": explanation, "event_type": event_type, "status": status},
        known_amounts=[state.get("budget_krw"), state.get("cash_krw"),
                       state.get("wreath_krw"), amount],
    )
