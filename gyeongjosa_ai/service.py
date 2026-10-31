"""계정별 근거, 추가 질문과 모델 응답을 조합하는 대화 서비스."""

import re
from statistics import median

from .ai import ModelUnavailable


MODES = {"history", "amount", "attendance", "message", "notice"}
CATEGORIES = ("결혼", "장례", "부고", "백일", "돌", "생일", "환갑", "칠순", "팔순")


def parse_budget(text):
    """예산 표현을 우선 인식하고 과거 수령·지급액을 예산으로 오인하지 않는다."""
    money = list(re.finditer(r"(?<!\d)(\d[\d,]*)\s*(만\s*원?|원)", text))
    if not money:
        return None

    def amount(match):
        return int(match.group(1).replace(",", "")) * (10000 if match.group(2).startswith("만") else 1)

    markers = list(re.finditer(r"예산|최대|상한|지출\s*가능|낼\s*수\s*있는", text))
    for marker in markers:
        following = [match for match in money if 0 <= match.start() - marker.end() <= 30]
        if following:
            return amount(min(following, key=lambda match: match.start() - marker.end()))
        preceding = [match for match in money if 0 <= marker.start() - match.end() <= 12]
        if preceding:
            return amount(min(preceding, key=lambda match: marker.start() - match.end()))

    if len(money) != 1 or re.search(r"받|줬|주었|보냈|냈|이전|과거|지난|저번", text):
        return None
    return amount(money[0])


def interpret_budget_reply(text):
    """예산 답변에서 미정, 지출 곤란과 모호한 부정을 구분한다."""
    compact = re.sub(r"[\s.,!?~]+", "", text)
    if re.search(r"\d[\d,]*(?:만)?(?:원)?(?:은|는|도)?없", compact):
        return "ambiguous"
    if parse_budget(text) is not None:
        return None
    if re.search(r"(?:지출|돈|여유|쓸수|쓸돈|내기).{0,10}(?:어려|어렵|없|부족|못)", compact):
        return "difficult"
    if re.search(r"정하지않|정해두지않|정해지지않|안정했|못정했|정해둔.{0,10}없|정해진.{0,10}없|아직미정|예산미정|상한.{0,5}없", compact):
        return "undecided"
    if re.fullmatch(r"(?:(?:예산|상한)(?:은|이|도|을|는)?)?(?:없어|없어요|없는데|없는데요|없습니다|없음|없다|아니|아니요|아뇨)", compact):
        return "ambiguous"
    return None


def question_result(message, field, options=None):
    """사용자가 추가 정보를 제공할 수 있는 응답을 만든다."""
    return {"status": "need_more_info", "message": message, "pending_field": field, "options": options or []}


def error_result(message):
    """기록을 임의로 만들어 내지 않는 오류 응답을 만든다."""
    return {"status": "error", "message": message, "model": None, "evidence": []}


def person_option(person):
    """동명이인을 구분하는 선택지의 최소 정보를 만든다."""
    return {
        "id": person["id"],
        "name": person["name"],
        "relationship": person["relationship"],
        "affiliation": person["fictional_affiliation"],
        "label": f"{person['name']} · {person['fictional_affiliation'] or '소속 미기록'} · {person['relationship']}",
    }


def notice_summary(candidate):
    """공유가 허용된 부고에서 확인된 내용과 미기록 항목을 설명한다."""
    notice = candidate["notice"]
    mourner = notice.get("mourner") or {}
    relation = "직접 친구" if candidate["relation_type"] == "direct_friend" else "친구의 친구"
    publisher = candidate.get("publisher_name") or "이름 공개 미확인"
    return (
        f"선택한 부고 {notice['id']}: 상주 {mourner.get('name') or '미기록'} · "
        f"소속 {mourner.get('affiliation') or '미기록'} · 고인과의 관계 {mourner.get('deceased_relation') or '미기록'}.\n"
        f"공유자 {publisher} · 공유자와의 관계 {relation} · 공통 친구 {candidate['mutual_count']}명.\n"
        f"기간 {notice['start_date']}~{notice['end_date']} · 지역 {notice.get('region') or '미기록'}.\n"
        f"장소 {notice.get('venue') or '미기록'} · 주소 {notice.get('address') or '미기록'} · "
        f"빈소 {notice.get('room') or '미기록'} · 조문 시간 {notice.get('visiting_hours') or '미기록'}."
    )


def summarize_transactions(history):
    """선택한 지인의 실거래 금액을 양방향으로 요약하고 최근 급증 신호를 계산한다."""
    event_dates = {event["id"]: event["start_date"] for event in history["events"]}
    summary = {}
    for direction in ("paid", "received"):
        records = sorted(
            (transaction for transaction in history["transactions"]
             if transaction["direction"] == direction and transaction["amount_krw"] > 0),
            key=lambda transaction: (
                event_dates.get(transaction["private_event_id"], ""), transaction["id"]
            ),
        )
        amounts = [record["amount_krw"] for record in records]
        earlier = amounts[:-1]
        earlier_median = median(earlier) if len(earlier) >= 2 else None
        latest = amounts[-1] if amounts else None
        increase_ratio = round(latest / earlier_median, 2) if earlier_median else None
        summary[direction] = {
            "count": len(amounts),
            "total_krw": sum(amounts),
            "average_krw": round(sum(amounts) / len(amounts)) if amounts else None,
            "median_krw": median(amounts) if amounts else None,
            "latest_krw": latest,
            "previous_median_krw": earlier_median,
            "recent_spike": bool(earlier_median and latest >= 2 * earlier_median),
            "recent_ratio": increase_ratio,
        }
    return summary


def find_person(data, user_id, question, person_id, candidate=None):
    """사용자가 지정하거나 질문에서 식별한 개인 지인을 찾는다."""
    people = data.people(user_id)
    if person_id:
        return next((person for person in people if person["id"] == person_id), None), None
    matches = [person for person in people if person["name"] in question]
    if not matches:
        matches = [person for person in people if person["fictional_affiliation"] and person["fictional_affiliation"] in question]
    if len(matches) > 1:
        narrowed = [person for person in matches if person["fictional_affiliation"] in question or person["relationship"] in question]
        if narrowed:
            matches = narrowed
    if len(matches) == 1:
        return matches[0], None
    if candidate:
        matching = data.matching_people(user_id, candidate["notice"])
        options = [{**person_option(item["person"]), "affiliation_match": item["affiliation_match"]} for item in matching]
        detail = "상주와 같은 이름의 지인 후보가 없습니다." if not options else "상주와 같은 이름의 지인 후보입니다."
        result = question_result(
            f"{notice_summary(candidate)}\n{detail} 같은 사람인지 확인해 주세요. 모르면 선택하지 않아도 됩니다.",
            "person_id", options,
        )
        result["allow_unknown"] = True
        return None, result
    options = matches if matches else people
    return None, question_result("어떤 지인인지 이름과 소속을 확인해 주세요.", "person_id", [person_option(p) for p in options])


class ChatService:
    """가상 계정 범위에서 모델에 필요한 자료만 준비한다."""

    def __init__(self, data, gateway):
        self.data = data
        self.gateway = gateway

    def _recommend_amount(self, request, person, history, event_type, budget):
        """일반 금액 상담은 거래 유무와 관계없이 동일한 법률·RAG·추천 엔진으로 계산한다."""
        from app.main import STORE
        from app.profile_store import profile_for_recipient
        from app.relationship_analysis import analyze
        from app.orchestrator import run

        question = request["question"]
        user_id = request["user_id"]
        attendance = request.get("attendance_with_meal")
        if attendance is None and re.search(r"식사|뷔페|밥", question):
            attendance = not bool(re.search(r"식사\s*(?:안|하지)|안\s*(?:먹|할)", question))
        risk = bool(re.search(r"공무원|공직|직무|계약|입찰|심사|평가|청탁금지|담임|교사|인허가", question))
        access = profile_for_recipient(
            store=STORE, data=self.data.dataset, viewer_id=user_id, person_id=person["id"]
        )
        profile = dict(access["policy"] or {
            "covered": "unknown", "duty_related": "unknown",
            "exception_confirmed": "unknown", "conflict": "unknown",
            "provenance": "unavailable_profile",
            "description": "상대의 직업·직무 관련성 정보가 확인되지 않았습니다.",
        })
        relation = analyze(
            sender=STORE.get(user_id), recipient=profile,
            relationship_text=question[:400], allow_llm_analysis=False,
        )
        profile["sender_ethics_risk"] = relation["sender_ethics_risk"]
        # 일반 자유서술의 의심 단서는 허용 사실로 사용하지 않고 보류 근거로 사용한다.
        profile["unconfirmed_high_risk"] = bool(risk or relation["high_risk_hint"])
        close = re.search(r"친밀도(?:는|가|를)?\s*([1-5])\s*(?:점|/5)", question)
        recent = re.search(r"(?:최근|지난번)[^\n]{0,35}?(\d[\d,]*)\s*(만\s*원?|원)(?:을|이나)?\s*받", question)
        received = None
        if recent:
            received = int(recent.group(1).replace(",", "")) * (
                10000 if recent.group(2).startswith("만") else 1
            )
            if received > 10000000:
                received = None

        report = run(
            user_id=user_id, person_id=person["id"], identity_confirmed=True,
            event_type=event_type, attendance_with_meal=attendance, budget_krw=budget,
            profile_override=profile, profile_access=access["access"],
            relation_assessment=relation, dataset=self.data.dataset,
            closeness_override=int(close.group(1)) if close else request.get("relationship_closeness"),
            special_care=bool(request.get("relationship_special_care") or re.search(r"특별히\s*챙기|더\s*챙기|특별하게\s*보답", question)),
            recent_received_override=received if received is not None else request.get("recent_received_override"),
        )
        result = report["result"]
        status = result["status"]
        if status == "NEEDS_ATTENDANCE_CONTEXT":
            return question_result(
                "결혼식에 참석해 식사할 예정인가요?", "attendance_with_meal",
                [{"label": "식사할 예정", "reply": "식사할 예정이에요"},
                 {"label": "식사하지 않음", "reply": "식사하지 않을 예정이에요"}],
            )
        legal = result.get("legal_assessment") or {}
        evidence = [{"id": person["id"], "kind": "지인",
                     "text": f"{person['name']} · {person['relationship']}"}]
        for transaction in history["transactions"]:
            direction = "받음" if transaction["direction"] == "received" else "냄"
            evidence.append({
                "id": transaction["id"], "kind": "개인 거래",
                "text": f"{direction} · {transaction['amount_krw']:,}원 · 행사 {transaction['private_event_id']}",
                "decision_role": "personal_history",
            })
        for source in report["evidence"]:
            evidence.append({
                "id": source["id"], "kind": "공개 근거", "text": source["excerpt"],
                "url": source["url"], "decision_role": source["decision_role"],
            })
        if received is not None:
            evidence.append({"id": "claim:recent_received", "kind": "사용자 자기신고 수령액",
                             "text": f"직접 말한 최근 수령액 {received:,}원(기록 미확인)",
                             "decision_role": "user_reported"})
        for adjustment in result.get("relationship_adjustments", []):
            evidence.append({
                "id": "adjustment:" + adjustment["signal"], "kind": "개인화 추천 규칙",
                "text": adjustment["reason"], "decision_role": "personalization",
            })

        # 위법 위험이 있거나 법률 확인이 필요한 상황의 참고액은 행동 금액과 구분한다.
        normal = status == "RECOMMENDED"
        reference = result.get("reference_only_amount_krw")
        provisional = not risk and status == "NEEDS_FACTS" and reference is not None
        amount = result["amount_krw"] if normal else reference if provisional else None
        if amount is not None and amount > budget:
            raise ValueError("추천 후보가 예산을 초과했습니다.")
        why = " ".join(result.get("reasons", []))
        if risk or status in {"NEEDS_EXPERT_REVIEW", "POTENTIALLY_PROHIBITED"}:
            message = "법률·직무 위험이 확인되기 전에는 행동 금액 제안을 보류합니다. " + (
                legal.get("reason") or result.get("message", "")
            )
        elif amount is not None:
            label = "법률 확인 전 일반 비교 참고액" if provisional else "추천 참고액"
            message = f"{label}은 {amount:,}원입니다. "
            if not history["transactions"]:
                message = "선택한 지인과의 금전 이력은 0건입니다. " + message
            message += why
            if history["transactions"]:
                message += (f" 기록상 받은 금액 {history['received_total_krw']:,}원, "
                            f"낸 금액 {history['paid_total_krw']:,}원, 예산 {budget:,}원을 확인했습니다.")
            if provisional:
                message += " 법적 송금 가능 여부는 별도로 확인해야 합니다."
        else:
            message = result.get("message", "확인 가능한 근거와 조건에서 금액 제안을 보류합니다.")
        if amount is None and history["transactions"]:
            message += (f" 개인 기록상 받은 금액 {history['received_total_krw']:,}원, "
                        f"낸 금액 {history['paid_total_krw']:,}원, 예산 {budget:,}원을 확인했습니다.")
        model = None
        cited_ids = []
        if amount is not None:
            compact_history = {
                "person_id": person["id"], "events": [],
                "transactions": [{
                    "id": row["id"], "event_id": row["private_event_id"],
                    "direction": row["direction"], "amount_krw": row["amount_krw"],
                    "contact_person_id": row["contact_person_id"],
                } for row in history["transactions"]],
            }
            context = {
                "mode": "amount", "question": question, "person": person_option(person),
                "history": compact_history, "event_type": event_type, "budget_krw": budget,
                "recommendation": {
                    "amount_krw": amount, "reference_only": provisional,
                    "recommendation_basis": result.get("recommendation_basis"),
                    "reasons": result.get("reasons", []),
                    "evidence_level": result.get("evidence_level"),
                    "matched_source_id": result.get("matched_source_id"),
                },
                "public_sources": [
                    {"id": item["id"], "text": item["text"],
                     "decision_role": item.get("decision_role")}
                    for item in evidence if item["kind"] == "공개 근거"
                ],
                "allowed_evidence_ids": [item["id"] for item in evidence],
            }
            try:
                preferred = request.get("_preferred_model")
                if preferred:
                    answer = self.gateway.generate(context, set(context["allowed_evidence_ids"]),
                                                   preferred_model=preferred)
                else:
                    answer = self.gateway.generate(context, set(context["allowed_evidence_ids"]))
                model = answer.get("model")
                cited_ids = answer.get("evidence_ids", [])
                # 모델이 출력한 금액은 서버 확정값을 덮어쓸 수 없다.
                if not history["transactions"]:
                    message += " " + answer["answer"]
            except ModelUnavailable:
                message += " 추가 AI 설명 없이 검증된 계산 결과만 표시합니다."

        return {
            "status": "answer", "message": message.strip(), "model": model,
            "evidence": evidence, "cited_ids": cited_ids,
            "history_stats": summarize_transactions(history),
            "suggested_amount_krw": amount,
            "recommendation_basis": result.get("recommendation_basis"),
            "evidence_level": result.get("evidence_level"),
            "v4_analysis": {
                "status": status, "legal_assessment": legal,
                "amount_krw": amount, "baseline_amount_krw": result.get("baseline_amount_krw"),
                "relationship_adjustments": result.get("relationship_adjustments", []),
                "reference_only": provisional,
            },
        }

    def chat_auto(self, request):
        """자연어 의도를 분류하고 계정별 대화 맥락을 이어 간다."""
        user_id = request.get("user_id", "")
        question = str(request.get("question") or "").strip()
        if user_id not in self.data.users:
            return error_result("알 수 없는 가상 계정입니다.")
        if not question or len(question) > 2000:
            return error_result("질문은 1자 이상 2,000자 이하로 입력해 주세요.")
        raw_context = request.get("context") or {}
        if not isinstance(raw_context, dict):
            return error_result("대화 맥락 형식을 확인해 주세요.")
        from .v4_chat import try_v4_chat
        v4_result = try_v4_chat(user_id, question, raw_context, gateway=self.gateway)
        if v4_result is not None:
            return v4_result
        keys = {"intent", "person_id", "notice_id", "person_confirmed", "budget_krw", "budget_state", "availability", "event_type", "attendance_with_meal", "pending_field", "relationship_closeness", "relationship_special_care", "recent_received_override"}
        context = {key: value for key, value in raw_context.items() if key in keys}
        people = self.data.people(user_id)
        people_ids = {person["id"] for person in people}
        notices = self.data.recommendations(user_id)
        notice_ids = {item["notice"]["id"] for item in notices}
        if context.get("person_id") and context["person_id"] not in people_ids:
            return error_result("선택한 지인을 이 계정에서 조회할 수 없습니다.")
        if context.get("notice_id") and context["notice_id"] not in notice_ids:
            return error_result("선택한 부고를 이 계정에서 조회할 수 없습니다.")

        if context.get("intent") == "amount" and context.get("pending_field") in {"budget_krw", "budget_clarification"}:
            budget_reply = interpret_budget_reply(question)
            if budget_reply == "ambiguous":
                context.pop("budget_krw", None)
                context.pop("budget_state", None)
                context["pending_field"] = "budget_clarification"
                result = question_result(
                    "예산을 아직 정하지 않은 건가요, 아니면 지금 지출이 어려운 상황인가요?",
                    "budget_clarification",
                    [{"label": "아직 정하지 않았어요", "reply": "예산을 아직 정하지 않았어요"},
                     {"label": "지출이 어려워요", "reply": "지금은 지출이 어려워요"}],
                )
                return {**result, "intent": "amount", "model": None, "context": context}
            if budget_reply in {"undecided", "difficult"}:
                context.pop("budget_krw", None)
                context.pop("pending_field", None)
                context["budget_state"] = budget_reply
                result = self.chat({**context, "user_id": user_id, "question": question, "mode": "amount"})
                if result.get("pending_field"):
                    context["pending_field"] = result["pending_field"]
                return {**result, "intent": "amount", "context": context}

        if context.get("pending_field") in {"person_id", "person_confirmed"} and context.get("notice_id") and re.search(
            r"모르겠|잘 모르|해당.*없|아는.*없|확인.*(?:어렵|불가|못)", question
        ):
            candidate = self.data.notice_for_user(user_id, context["notice_id"])
            context.pop("person_id", None)
            context.pop("person_confirmed", None)
            context.pop("pending_field", None)
            return {
                "status": "answer",
                "message": f"{notice_summary(candidate)}\n상주와 지인의 관계를 확인하지 못해 개인 이력 연결과 금액 제안을 보류합니다. 다른 질문은 계속할 수 있습니다.",
                "intent": context.get("intent"), "model": None,
                "evidence": [{"id": candidate["notice"]["id"], "kind": "공유 부고", "text": notice_summary(candidate)}],
                "context": context,
            }

        recent = request.get("history") or []
        if not isinstance(recent, list):
            return error_result("대화 이력 형식을 확인해 주세요.")
        recent = [
            {"role": item.get("role"), "content": str(item.get("content", ""))[:500]}
            for item in recent[-4:] if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
        ]
        classification_context = {
            "question": question,
            "previous_context": context,
            "recent_messages": recent,
            "people": [person_option(person) for person in people],
            "notices": [
                {"id": item["notice"]["id"], "title": item["notice"]["title"],
                 "mourner": item["notice"].get("mourner"), "region": item["notice"]["region"]}
                for item in notices
            ],
        }
        try:
            classified = self.gateway.classify(classification_context, people_ids, notice_ids)
        except ModelUnavailable as exc:
            return error_result(str(exc))

        intent = classified["intent"]
        pending = context.get("pending_field")
        if pending == "attendance_with_meal":
            if re.search(r"식사\s*(?:안|하지)|안\s*(?:먹|할)|불참", question):
                context["attendance_with_meal"] = False
            elif re.search(r"식사|먹|참석|네|예", question):
                context["attendance_with_meal"] = True
        previous_intent = context.get("intent")
        explicit_followup = (
            pending in {"budget_krw", "budget_clarification"} and parse_budget(question) is not None
            or pending == "person_confirmed" and bool(re.search(r"네|예|맞아|맞아요|맞습니다|아니|틀려|다른 사람", question))
            or pending == "person_id" and bool(context.get("person_id"))
            or pending == "notice_id" and bool(context.get("notice_id"))
            or pending == "event_type" and any(category in question for category in CATEGORIES)
            or pending == "attendance_with_meal" and context.get("attendance_with_meal") is not None
        )
        if pending and previous_intent in MODES and (intent == previous_intent or explicit_followup):
            intent = previous_intent
        elif pending and previous_intent in MODES and intent != previous_intent:
            context.pop("pending_field", None)
            pending = None
        if not pending and previous_intent == "amount" and context.get("budget_state") in {"undecided", "difficult"} and re.fullmatch(
            r"\s*(?:(?:최대|예산(?:은|이|을|으로)?)\s*)?\d[\d,]*(?:\s*만\s*원?|\s*원)(?:\s*(?:이요|이야|이에요|입니다|정도|으로|까지만))?\s*[.!?]*\s*",
            question,
        ):
            intent = "amount"
        if intent == "out_of_scope":
            return {"status": "out_of_scope", "message": "경조사 기록과 부고, 금액·참석·인사말에 대해 질문해 주세요.", "classification_model": classified["model"], "model": None, "evidence": [], "context": {}}

        if pending == "person_confirmed":
            if re.search(r"(^|\s)(네|예|맞아요|맞습니다|맞아|맞습니다|네,|예,)", question):
                context["person_confirmed"] = True
            elif re.search(r"아니|틀려|다른 사람", question):
                context.pop("person_id", None)
                context["person_confirmed"] = False
                candidate = self.data.notice_for_user(user_id, context["notice_id"]) if context.get("notice_id") else None
                if candidate:
                    _, result = find_person(self.data, user_id, "", None, candidate)
                else:
                    result = question_result("상주와 연결할 지인을 다시 선택해 주세요.", "person_id", [person_option(person) for person in people])
                context.update({"intent": intent, "pending_field": "person_id"})
                return {**result, "intent": intent, "classification_model": classified["model"], "context": context}
            else:
                result = question_result("선택한 지인이 상주와 같은 사람인지 '네' 또는 '아니요'로 확인해 주세요.", "person_confirmed")
                return {**result, "intent": intent, "classification_model": classified["model"], "context": context}
        if pending == "availability":
            context["availability"] = question
        budget = parse_budget(question)
        if budget is not None:
            context.pop("budget_state", None)
            context["budget_krw"] = budget

        if not context.get("notice_id"):
            selected_id = classified.get("notice_id")
            if selected_id in notice_ids and (selected_id.casefold() in question.casefold() or len(notices) == 1):
                context["notice_id"] = selected_id
        if pending == "notice_id" and classified.get("notice_id") in notice_ids:
            context["notice_id"] = classified["notice_id"]
        if intent == "notice" and context.get("notice_id") and re.search(
            r"얼마\s*(?:를|씩)?\s*(?:내|낼|드리|드릴|보내|보낼)|(?:부의금|조의금|부조금)\s*(?:을|은|이|는)?\s*(?:얼마|금액)",
            question,
        ):
            intent = "amount"

        direct_closeness = re.search(r"친밀도(?:는|가|를)?\s*([1-5])\s*(?:점|/5)", question)
        if direct_closeness:
            context["relationship_closeness"] = int(direct_closeness.group(1))
        if re.search(r"특별히\s*챙기|더\s*챙기|특별하게\s*보답", question):
            context["relationship_special_care"] = True
        direct_received = re.search(r"(?:최근|지난번)[^\n]{0,35}?(\d[\d,]*)\s*(만\s*원?|원)(?:을|이나)?\s*받", question)
        if direct_received:
            claimed = int(direct_received.group(1).replace(",", "")) * (
                10000 if direct_received.group(2).startswith("만") else 1
            )
            if claimed <= 10000000:
                context["recent_received_override"] = claimed
        previous_person_id = context.get("person_id")
        mentioned = [person for person in people if person["name"] in question]
        narrowed = [person for person in mentioned if person["fictional_affiliation"] and person["fictional_affiliation"] in question or person["relationship"] in question]
        if len(narrowed) == 1:
            context["person_id"] = narrowed[0]["id"]
        elif len(mentioned) == 1:
            context["person_id"] = mentioned[0]["id"]
        elif len(mentioned) > 1 and not context.get("person_id") and not context.get("notice_id"):
            result = question_result("같은 이름의 지인이 있습니다. 소속과 관계를 확인해 주세요.", "person_id", [person_option(person) for person in mentioned])
            context.update({"intent": intent, "pending_field": "person_id"})
            return {**result, "intent": intent, "classification_model": classified["model"], "context": context}
        elif pending == "person_id" and classified.get("person_id") in people_ids:
            context["person_id"] = classified["person_id"]
        elif not context.get("person_id") and classified.get("person_id") in people_ids:
            chosen = self.data.people_by_id[classified["person_id"]]
            matched = [person for person in people if person["name"] in question
                       or person["fictional_affiliation"] and person["fictional_affiliation"] in question
                       or person["relationship"] in question]
            if len(matched) == 1 and matched[0]["id"] == chosen["id"]:
                context["person_id"] = chosen["id"]
        if context.get("person_id") != previous_person_id:
            context.pop("person_confirmed", None)
            for key in ("relationship_closeness", "relationship_special_care", "recent_received_override"):
                if key not in {"relationship_closeness" if direct_closeness else "",
                               "relationship_special_care" if re.search(r"특별히|더\s*챙기", question) else "",
                               "recent_received_override" if direct_received else ""}:
                    context.pop(key, None)

        if intent == "notice" and not context.get("notice_id"):
            if not notices:
                return {"status": "answer", "message": "현재 이 계정에서 추천할 수 있는 부고가 없습니다.", "intent": intent, "classification_model": classified["model"], "model": None, "evidence": [], "context": {"intent": intent}}
            options = [{"id": item["notice"]["id"], "title": item["notice"]["title"], "region": item["notice"]["region"]} for item in notices]
            result = question_result("어떤 부고를 확인할지 선택해 주세요.", "notice_id", options)
            context.update({"intent": intent, "pending_field": "notice_id"})
            return {**result, "intent": intent, "classification_model": classified["model"], "context": context}
        event_type = classified.get("event_type")
        if event_type and (event_type in question or event_type == "장례" and any(word in question for word in ("부고", "조문", "상주"))):
            context["event_type"] = event_type

        context["intent"] = intent
        context.pop("pending_field", None)
        request_for_chat = {**context, "user_id": user_id, "question": question, "mode": intent, "_preferred_model": classified["model"]}
        result = self.chat(request_for_chat)
        if result.get("pending_field"):
            context["pending_field"] = result["pending_field"]
        return {**result, "intent": intent, "classification_model": classified["model"], "context": context}

    def chat(self, request):
        """대화 입력을 확인하고 추가 질문 또는 근거 기반 답변을 반환한다."""
        user_id = request.get("user_id", "")
        mode = request.get("mode", "")
        question = str(request.get("question") or "").strip()
        if user_id not in self.data.users:
            return error_result("알 수 없는 가상 계정입니다.")
        if mode not in MODES or not question:
            return error_result("기능과 질문을 확인해 주세요.")

        candidate = None
        notice_id = request.get("notice_id")
        if notice_id:
            candidate = self.data.notice_for_user(user_id, notice_id)
            if candidate is None:
                return error_result("선택한 부고를 이 계정에서 조회할 수 없습니다.")
        if mode == "notice" and candidate is None:
            return question_result("먼저 확인할 부고를 선택해 주세요.", "notice_id")

        person = None
        if mode in {"history", "amount", "message"} or request.get("person_id"):
            person, pending = find_person(self.data, user_id, question, request.get("person_id"), candidate)
            if request.get("person_id") and person is None:
                return error_result("선택한 지인을 이 계정에서 조회할 수 없습니다.")
            if pending:
                return pending

        if candidate and person and mode in {"history", "amount", "attendance", "message"} and not request.get("person_confirmed", False):
            mourner = candidate["notice"].get("mourner") or {}
            same_name = person["name"] == mourner.get("name")
            affiliation = mourner.get("affiliation")
            same_affiliation = person["fictional_affiliation"] == affiliation if affiliation else None
            relation_text = "이름이 일치합니다." if same_name else "이름이 다릅니다."
            if same_affiliation is False:
                relation_text += " 소속도 다릅니다."
            elif same_affiliation is None:
                relation_text += " 상주의 소속은 미기록입니다."
            else:
                relation_text += " 소속이 일치합니다."
            result = question_result(f"{notice_summary(candidate)}\n{relation_text} 선택한 지인이 상주와 같은 사람인지 직접 확인해 주세요.", "person_confirmed")
            result["allow_unknown"] = True
            return result

        history = self.data.history(user_id, person["id"]) if person else None
        budget = request.get("budget_krw")
        if budget is None:
            budget = parse_budget(question)
        if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int) or budget < 0):
            return error_result("예산은 0 이상의 정수 금액으로 입력해 주세요.")

        if mode == "history" and history and not history["events"]:
            return {"status": "answer", "message": "선택한 지인과의 경조사 이력이 기록되어 있지 않습니다.", "model": None, "evidence": []}
        if mode == "amount" and (request.get("budget_state") == "difficult" or budget == 0):
            prefix = "입력하신 최대 예산은 0원입니다." if budget == 0 else "지금은 지출이 어려운 상황이군요."
            return {"status": "answer", "message": prefix + " 무리해서 금액을 정할 필요는 없습니다. 원하시면 위로 문구를 함께 생각해 볼게요.", "model": None, "evidence": [], "suggested_amount_krw": None}
        if mode == "amount" and budget is None and request.get("budget_state") == "undecided":
            evidence = []
            if history and history["transactions"]:
                for transaction in history["transactions"]:
                    direction = "받음" if transaction["direction"] == "received" else "냄"
                    evidence.append({"id": transaction["id"], "kind": "개인 거래", "text": f"{direction} · {transaction['amount_krw']:,}원 · 행사 {transaction['private_event_id']}"})
                detail = f"확인된 기록은 받은 금액 {history['received_total_krw']:,}원, 낸 금액 {history['paid_total_krw']:,}원입니다."
            else:
                detail = "선택한 지인의 주고받은 금액 기록이 없습니다."
            return {"status": "answer", "message": f"예산을 아직 정하지 않았군요. {detail} 구체적인 금액 제안은 보류하며, 예산을 정하면 알려 주세요.", "model": None, "evidence": evidence, "suggested_amount_krw": None}
        if mode == "amount" and budget is None:
            prefix = "선택한 지인의 경조사 이력이 없습니다. " if history and not history["events"] else ""
            return question_result(prefix + "이번에 생각하시는 최대 예산이 있나요?", "budget_krw")
        if mode == "attendance" and not request.get("availability"):
            return question_result("행사 기간에 시간을 낼 수 있는지 알려 주시겠어요?", "availability")

        event_type = (request.get("event_type")
                      or (candidate["notice"]["category"] if candidate else None)
                      or next((category for category in CATEGORIES if category in question), None))
        if event_type == "부고":
            event_type = "장례"
        if mode in {"amount", "message"} and not candidate and not event_type:
            prefix = "선택한 지인의 경조사 이력이 없습니다. " if history and not history["events"] else ""
            return question_result(prefix + "어떤 종류의 경조사인지 알려 주세요.", "event_type")
        if mode == "amount" and history is not None:
            return self._recommend_amount(request, person, history, event_type, budget)

        evidence = []
        person_data = None
        if person:
            person_data = person_option(person)
            evidence.append({"id": person["id"], "kind": "지인", "text": f"{person['name']} · {person['relationship']} · {person['fictional_affiliation']}"})
        notice_data = None
        if candidate:
            notice = candidate["notice"]
            mourner = notice.get("mourner") or {}
            notice_data = {
                "id": notice["id"], "category": notice["category"], "start_date": notice["start_date"],
                "end_date": notice["end_date"], "region": notice["region"], "mourner": mourner,
                "venue": notice.get("venue"), "address": notice.get("address"), "room": notice.get("room"),
                "visiting_hours": notice.get("visiting_hours"), "publisher_name": candidate.get("publisher_name"),
            }
            if mode == "notice":
                notice_data.update({"mutual_count": candidate["mutual_count"], "score": candidate["score"], "relation_type": candidate["relation_type"]})
            evidence.append({"id": notice["id"], "kind": "공유 부고", "text": notice_summary(candidate)})

        matching_people = []
        if candidate and mode == "notice":
            matching_people = self.data.matching_people(user_id, candidate["notice"])
            for match in matching_people:
                item = match["person"]
                match_text = "소속 일치" if match["affiliation_match"] is True else "소속 다름" if match["affiliation_match"] is False else "상주 소속 미기록"
                evidence.append({"id": item["id"], "kind": "확인할 지인 후보", "text": f"{item['name']} · {item['relationship']} · {item['fictional_affiliation']} · {match_text}"})

        compact_history = None
        if history and mode in {"history", "amount", "attendance"}:
            compact_history = {"person_id": person["id"], "events": [], "transactions": []}
            for event in history["events"]:
                compact_history["events"].append({"id": event["id"], "contact_person_id": event["contact_person_id"], "title": event["title"], "subject_relation": event["subject_relation"], "category": event["category"], "start_date": event["start_date"], "actual_attendance": event["actual_attendance"]})
                evidence.append({"id": event["id"], "kind": "개인 행사", "text": f"{event['start_date']} · {event['title']}"})
            for transaction in history["transactions"]:
                compact_history["transactions"].append({"id": transaction["id"], "event_id": transaction["private_event_id"], "contact_person_id": transaction["contact_person_id"], "direction": transaction["direction"], "amount_krw": transaction["amount_krw"]})
                direction = "받음" if transaction["direction"] == "received" else "냄"
                evidence.append({"id": transaction["id"], "kind": "개인 거래", "text": f"{direction} · {transaction['amount_krw']:,}원 · 행사 {transaction['private_event_id']}"})

        context = {
            "mode": mode, "question": question, "person": person_data, "notice": notice_data,
            "person_confirmed": bool(request.get("person_confirmed")), "history": compact_history,
            "budget_krw": budget if mode == "amount" else None,
            "availability": request.get("availability") if mode == "attendance" else None, "event_type": event_type,
            "matching_people": [{**person_option(match["person"]), "affiliation_match": match["affiliation_match"]} for match in matching_people],
            "allowed_evidence_ids": [item["id"] for item in evidence],
        }
        try:
            preferred = request.get("_preferred_model")
            if preferred:
                answer = self.gateway.generate(context, {item["id"] for item in evidence}, preferred_model=preferred)
            else:
                answer = self.gateway.generate(context, {item["id"] for item in evidence})
        except ModelUnavailable as exc:
            return error_result(str(exc))

        message = answer["answer"]
        if mode == "amount" and history and history["transactions"]:
            message = f"선택한 지인과의 확인된 기록은 받은 금액 {history['received_total_krw']:,}원, 낸 금액 {history['paid_total_krw']:,}원입니다. 입력한 최대 예산 {budget:,}원과 함께 살펴보세요."
        if mode == "history" and history["transactions"]:
            message = f"기록 합계: 받은 금액 {history['received_total_krw']:,}원, 낸 금액 {history['paid_total_krw']:,}원.\n" + message
        if mode == "amount" and answer.get("suggested_amount_krw") is not None:
            message += f"\n검토할 선택지: {answer['suggested_amount_krw']:,}원. 최종 결정은 사용자가 합니다."
        if mode == "notice":
            message = f"{notice_summary(candidate)}\n{message}\n상주와 지인이 같은 사람인지는 사용자가 직접 확인해야 합니다."
        return {
            "status": "answer", "message": message, "model": answer["model"],
            "evidence": evidence, "cited_ids": answer["evidence_ids"],
            "suggested_amount_krw": answer.get("suggested_amount_krw"),
            "requires_identity_confirmation": bool(candidate and mode == "notice"),
            "identity_candidates": [{**person_option(match["person"]), "affiliation_match": match["affiliation_match"]} for match in matching_people],
        }
