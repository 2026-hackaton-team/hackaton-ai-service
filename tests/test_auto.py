"""기능 선택 없이 질문하고 문맥에 따라 추가 정보를 받는 흐름을 확인한다."""

import pytest

from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService


class AutoGateway:
    """의도 분류와 답변을 별도로 확인하는 대역이다."""

    def __init__(self, intent="history", person_id="P001", notice_id=None):
        self.intent = intent
        self.person_id = person_id
        self.notice_id = notice_id
        self.classifications = []
        self.answers = []

    def classify(self, context, people_ids, notice_ids):
        self.classifications.append(context)
        return {"intent": self.intent, "person_id": self.person_id, "notice_id": self.notice_id, "event_type": None, "model": "claude-opus-4-8"}

    def generate(self, context, allowed_ids, preferred_model=None):
        self.answers.append((context, allowed_ids))
        return {"answer": "확인된 기록을 참고해 주세요.", "evidence_ids": sorted(allowed_ids), "suggested_amount_krw": 50000 if context["mode"] == "amount" else None, "model": "claude-opus-4-8"}


def test_natural_question_is_classified_without_mode():
    gateway = AutoGateway()
    service = ChatService(load_data(), gateway)
    result = service.chat_auto({"user_id": "U001", "question": "해든기획팀 김도윤과 주고받은 기록을 알려줘"})
    assert result["status"] == "answer"
    assert result["intent"] == "history"
    assert result["classification_model"] == "claude-opus-4-8"
    assert {item["id"] for item in result["evidence"] if item["id"].startswith("T")} == {"T001", "T002"}
    assert gateway.classifications and gateway.answers


def test_classifier_cannot_silently_pick_same_name_person():
    gateway = AutoGateway(person_id="P001")
    result = ChatService(load_data(), gateway).chat_auto({"user_id": "U001", "question": "김도윤 이력을 알려줘"})
    assert result["status"] == "need_more_info" and result["pending_field"] == "person_id"
    assert {option["id"] for option in result["options"]} == {"P001", "P002"}
    assert gateway.answers == []


def test_budget_followup_preserves_intent_and_selected_person():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service = ChatService(load_data(), gateway)
    initial = service.chat_auto({"user_id": "U001", "question": "동료 부고에 얼마가 좋을까?", "context": {"person_id": "P001", "notice_id": "N001", "person_confirmed": True}})
    assert initial["status"] == "need_more_info" and initial["pending_field"] == "budget_krw"
    reply = service.chat_auto({"user_id": "U001", "question": "최대 8만 원이야", "context": initial["context"]})
    assert reply["status"] == "answer"
    assert gateway.answers[-1][0]["budget_krw"] == 80000
    assert reply["context"]["person_id"] == "P001"


def test_unavailable_notice_is_rejected_before_classification():
    gateway = AutoGateway(intent="notice", notice_id="N003")
    result = ChatService(load_data(), gateway).chat_auto({"user_id": "U001", "question": "부고 알려줘", "context": {"notice_id": "N003"}})
    assert result["status"] == "error"
    assert "가상 상주" not in str(result)
    assert gateway.classifications == []


def test_notice_question_requires_selection_from_visible_candidates():
    gateway = AutoGateway(intent="notice", person_id=None)
    result = ChatService(load_data(), gateway).chat_auto({"user_id": "U001", "question": "추천된 부고가 왜 관련 있나요?"})
    assert result["status"] == "need_more_info" and result["pending_field"] == "notice_id"
    assert {item["id"] for item in result["options"]} == {"N001", "N002"}
    assert gateway.answers == []


def test_out_of_scope_question_does_not_generate_an_answer():
    gateway = AutoGateway(intent="out_of_scope", person_id=None)
    result = ChatService(load_data(), gateway).chat_auto({"user_id": "U001", "question": "오늘 주식 가격은?"})
    assert result["status"] == "out_of_scope"
    assert gateway.answers == []


def test_attendance_followup_uses_user_supplied_availability():
    gateway = AutoGateway(intent="attendance", person_id=None, notice_id="N001")
    service = ChatService(load_data(), gateway)
    first = service.chat_auto({"user_id": "U001", "question": "선택한 부고에 조문하러 갈까?", "context": {"notice_id": "N001"}})
    assert first["status"] == "need_more_info" and first["pending_field"] == "availability"
    answer = service.chat_auto({"user_id": "U001", "question": "10월 31일 오전은 시간이 돼요", "context": first["context"]})
    assert answer["status"] == "answer"
    assert gateway.answers[-1][0]["availability"] == "10월 31일 오전은 시간이 돼요"


def test_user_explicitly_confirms_identity_before_history_is_used():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service = ChatService(load_data(), gateway)
    first = service.chat_auto({"user_id": "U001", "question": "부고에 얼마를 내면 될까? 예산은 8만 원이야", "context": {"notice_id": "N001", "person_id": "P001"}})
    assert first["status"] == "need_more_info" and first["pending_field"] == "person_confirmed"
    assert gateway.answers == []
    answer = service.chat_auto({"user_id": "U001", "question": "네, 맞아요", "context": first["context"]})
    assert answer["status"] == "answer"
    assert gateway.answers[-1][0]["person_confirmed"] is True


def test_explicit_budget_followup_keeps_prior_intent_even_if_classifier_is_uncertain():
    gateway = AutoGateway(intent="out_of_scope", person_id=None)
    service = ChatService(load_data(), gateway)
    context = {"intent": "amount", "person_id": "P001", "event_type": "결혼", "pending_field": "budget_krw"}
    result = service.chat_auto({"user_id": "U001", "question": "최대 8만 원이요", "context": context})
    assert result["status"] == "answer" and result["intent"] == "amount"
    assert gateway.answers[-1][0]["budget_krw"] == 80000


def test_selected_notice_amount_question_shows_details_and_relevant_candidates():
    gateway = AutoGateway(intent="amount", person_id=None, notice_id="N001")
    service = ChatService(load_data(), gateway)
    result = service.chat_auto({
        "user_id": "U001",
        "question": "동료 가족의 부고 N001은 누구인지 모르겠는데 가면 얼마를 내야 하나요?",
        "context": {"notice_id": "N001"},
    })
    assert result["pending_field"] == "person_id"
    assert {item["id"]: item["affiliation_match"] for item in result["options"]} == {"P001": True, "P002": False}
    assert "김도윤" in result["message"] and "해든기획팀" in result["message"]
    assert "부친" in result["message"] and "가상" in result["message"]
    assert result["allow_unknown"] is True
    assert gateway.answers == []


def test_unknown_mourner_returns_partial_information_without_using_personal_history():
    gateway = AutoGateway(intent="amount", person_id=None, notice_id="N001")
    service = ChatService(load_data(), gateway)
    first = service.chat_auto({"user_id": "U001", "question": "선택한 부고에 얼마를 내야 하나요?", "context": {"notice_id": "N001"}})
    result = service.chat_auto({"user_id": "U001", "question": "모르겠어요", "context": first["context"]})
    assert result["status"] == "answer"
    assert "보류" in result["message"] and "김도윤" in result["message"]
    assert result["context"].get("notice_id") == "N001" and not result["context"].get("person_id")
    assert all(not item["id"].startswith("T") for item in result.get("evidence", []))
    assert len(gateway.classifications) == 1 and gateway.answers == []


def test_no_matching_contact_can_be_skipped_without_selecting_an_unrelated_person():
    data = load_data()
    notice = data.notice_for_user("U001", "N001")["notice"]
    notice["mourner"]["name"] = "가상미확인상주"
    gateway = AutoGateway(intent="amount", person_id=None, notice_id="N001")
    service = ChatService(data, gateway)
    first = service.chat_auto({"user_id": "U001", "question": "이 부고에 얼마를 내나요?", "context": {"notice_id": "N001"}})
    assert first["pending_field"] == "person_id" and first["options"] == [] and first["allow_unknown"] is True
    result = service.chat_auto({"user_id": "U001", "question": "해당 지인이 없어요", "context": first["context"]})
    assert result["status"] == "answer" and "보류" in result["message"]
    assert gateway.answers == []


def test_changing_contact_does_not_reuse_previous_identity_confirmation():
    gateway = AutoGateway(intent="history", person_id="P002", notice_id="N001")
    service = ChatService(load_data(), gateway)
    result = service.chat_auto({
        "user_id": "U001", "question": "솔빛독서모임 김도윤의 이력은?",
        "context": {"notice_id": "N001", "person_id": "P001", "person_confirmed": True},
    })
    assert result["pending_field"] == "person_confirmed"
    assert result["context"]["person_id"] == "P002" and not result["context"].get("person_confirmed")
    assert gateway.answers == []


def test_unknown_identity_at_confirmation_does_not_reuse_selected_contact():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service = ChatService(load_data(), gateway)
    first = service.chat_auto({"user_id": "U001", "question": "이 부고에 얼마를 내나요?", "context": {"notice_id": "N001", "person_id": "P001"}})
    assert first["pending_field"] == "person_confirmed" and first["allow_unknown"] is True
    result = service.chat_auto({"user_id": "U001", "question": "잘 모르겠어요", "context": first["context"]})
    assert result["status"] == "answer" and not result["context"].get("person_id")
    assert gateway.answers == []


def test_selected_notice_does_not_accept_model_choice_between_same_name_people():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service = ChatService(load_data(), gateway)
    result = service.chat_auto({"user_id": "U001", "question": "김도윤 부고에 얼마를 낼까요?", "context": {"notice_id": "N001"}})
    assert result["pending_field"] == "person_id"
    assert {item["id"] for item in result["options"]} == {"P001", "P002"}
    assert not result["context"].get("person_id") and gateway.answers == []


def test_combined_notice_and_explicit_amount_question_survives_notice_classification():
    gateway = AutoGateway(intent="notice", person_id=None, notice_id="N001")
    service = ChatService(load_data(), gateway)
    result = service.chat_auto({
        "user_id": "U001", "question": "이 부고는 누구인지 모르겠는데 가면 얼마내야하지?",
        "context": {"notice_id": "N001"},
    })
    assert result["intent"] == "amount" and result["pending_field"] == "person_id"
    assert "김도윤" in result["message"] and gateway.answers == []


def test_how_close_question_is_not_treated_as_money():
    gateway = AutoGateway(intent="notice", person_id=None, notice_id="N001")
    service = ChatService(load_data(), gateway)
    result = service.chat_auto({"user_id": "U001", "question": "이 부고는 저와 얼마나 가까운 관련이 있나요?", "context": {"notice_id": "N001"}})
    assert result["intent"] == "notice" and result["status"] == "answer"


def start_amount_question(gateway, user_id="U001", person_id="P001", notice_id="N001"):
    """지인 확인이 끝난 뒤 최대 예산을 묻는 상태를 만든다."""
    service = ChatService(load_data(), gateway)
    context = {"person_id": person_id, "event_type": "장례"}
    if notice_id:
        context.update({"notice_id": notice_id, "person_confirmed": True})
    first = service.chat_auto({"user_id": user_id, "question": "이번에 얼마를 내면 좋을까요?", "context": context})
    assert first["pending_field"] == "budget_krw"
    return service, first


@pytest.mark.parametrize("reply", ["없어", "없어요", "없는데요", "예산 없어", "아니요", "8만 원은 없어"])
def test_ambiguous_budget_reply_asks_for_meaning_without_repeating_question(reply):
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    result = service.chat_auto({"user_id": "U001", "question": reply, "context": first["context"]})
    assert result["pending_field"] == "budget_clarification"
    assert "정하지" in result["message"] and "어려" in result["message"]
    assert result["message"] != first["message"] and not result["context"].get("budget_krw")
    assert len(result["options"]) == 2 and len(gateway.classifications) == 1 and gateway.answers == []


def test_undecided_budget_shows_transaction_evidence_without_inventing_a_limit():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    clarify = service.chat_auto({"user_id": "U001", "question": "없어", "context": first["context"]})
    result = service.chat_auto({"user_id": "U001", "question": "예산을 아직 정하지 않았어요", "context": clarify["context"]})
    assert result["status"] == "answer" and "아직 정하지" in result["message"]
    assert "100,000원" in result["message"] and "50,000원" in result["message"]
    assert {item["id"] for item in result["evidence"]} == {"T001", "T002"}
    assert result.get("suggested_amount_krw") is None and result["context"].get("budget_krw") is None
    assert len(gateway.classifications) == 1 and gateway.answers == []
    later = service.chat_auto({"user_id": "U001", "question": "예산 8만원으로 추천해줘", "context": result["context"]})
    assert later["status"] == "answer" and gateway.answers[-1][0]["budget_krw"] == 80000


def test_spending_difficulty_is_acknowledged_without_a_model_amount():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    clarify = service.chat_auto({"user_id": "U001", "question": "없어", "context": first["context"]})
    result = service.chat_auto({"user_id": "U001", "question": "지금은 지출이 어려워요", "context": clarify["context"]})
    assert result["status"] == "answer" and "무리" in result["message"]
    assert result.get("suggested_amount_krw") is None and gateway.answers == []
    assert len(gateway.classifications) == 1


def test_zero_budget_is_not_sent_to_model_as_a_payment_recommendation():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    result = service.chat_auto({"user_id": "U001", "question": "0원", "context": first["context"]})
    assert result["status"] == "answer" and "0원" in result["message"]
    assert result.get("suggested_amount_krw") is None and gateway.answers == []


def test_explicit_undecided_budget_with_no_history_does_not_invent_records():
    gateway = AutoGateway(intent="amount", person_id="P019", notice_id=None)
    service, first = start_amount_question(gateway, user_id="U004", person_id="P019", notice_id=None)
    result = service.chat_auto({"user_id": "U004", "question": "예산을 아직 정하지 않았어요", "context": first["context"]})
    assert result["status"] == "answer" and "기록" in result["message"]
    assert result.get("suggested_amount_krw") is None and result.get("evidence") == []
    assert gateway.answers == []


def test_user_can_change_subject_while_a_budget_answer_is_pending():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    gateway.intent = "out_of_scope"
    result = service.chat_auto({"user_id": "U001", "question": "오늘 주식 가격은?", "context": first["context"]})
    assert result["status"] == "out_of_scope" and gateway.answers == []


@pytest.mark.parametrize("reply", ["예산 아직 안 정했어", "아직 정해진 게 없어", "상한은 없어요"])
def test_explicitly_unset_budget_does_not_repeat_the_question(reply):
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    result = service.chat_auto({"user_id": "U001", "question": reply, "context": first["context"]})
    assert result["status"] == "answer" and "아직 정하지" in result["message"]
    assert result.get("suggested_amount_krw") is None and gateway.answers == []


def test_numeric_budget_is_accepted_after_clarification_even_if_classifier_is_uncertain():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    clarify = service.chat_auto({"user_id": "U001", "question": "없어", "context": first["context"]})
    gateway.intent = "out_of_scope"
    result = service.chat_auto({"user_id": "U001", "question": "8만원", "context": clarify["context"]})
    assert result["status"] == "answer" and gateway.answers[-1][0]["budget_krw"] == 80000


def test_numeric_budget_is_accepted_after_undecided_answer_even_if_classifier_is_uncertain():
    gateway = AutoGateway(intent="amount", person_id="P001", notice_id="N001")
    service, first = start_amount_question(gateway)
    undecided = service.chat_auto({"user_id": "U001", "question": "예산을 아직 정하지 않았어요", "context": first["context"]})
    gateway.intent = "out_of_scope"
    result = service.chat_auto({"user_id": "U001", "question": "8만원이요", "context": undecided["context"]})
    assert result["status"] == "answer" and gateway.answers[-1][0]["budget_krw"] == 80000
