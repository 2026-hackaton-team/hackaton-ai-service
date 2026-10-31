"""시연 대화의 소유권, 추가 질문, 근거와 실패 처리를 확인한다."""

import pytest

from gyeongjosa_ai.ai import ModelUnavailable
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService


class FakeGateway:
    """외부 호출 없이 전달된 근거와 응답을 확인한다."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def generate(self, context, allowed_ids):
        self.calls.append((context, allowed_ids))
        if self.fail:
            raise ModelUnavailable("모델 요청에 실패했습니다.")
        return {
            "answer": "확인된 기록을 참고해 직접 결정해 주세요.",
            "evidence_ids": sorted(allowed_ids),
            "suggested_amount_krw": 50000 if context["mode"] == "amount" else None,
            "model": "test-model",
        }


@pytest.fixture
def service():
    return ChatService(load_data(), FakeGateway())


def test_same_name_requires_user_selection_before_model_call(service):
    result = service.chat({"user_id": "U001", "mode": "history", "question": "김도윤 이력을 알려줘"})
    assert result["status"] == "need_more_info"
    assert result["pending_field"] == "person_id"
    assert {option["id"] for option in result["options"]} == {"P001", "P002"}
    assert service.gateway.calls == []


def test_history_uses_only_owned_records(service):
    result = service.chat({"user_id": "U001", "mode": "history", "question": "해든기획팀 김도윤 이력", "person_id": "P001"})
    assert result["status"] == "answer"
    assert {item["id"] for item in result["evidence"] if item["id"].startswith("T")} == {"T001", "T002"}
    assert "100,000원" in result["message"] and "50,000원" in result["message"]
    sent_history = service.gateway.calls[-1][0]["history"]
    assert sent_history["person_id"] == "P001"
    assert all(item["contact_person_id"] == "P001" for item in sent_history["transactions"])
    assert next(item for item in sent_history["events"] if item["id"] == "E001")["subject_relation"] == "본인"
    assert service.chat({"user_id": "U004", "mode": "history", "question": "이력", "person_id": "P001"})["status"] == "error"


def test_amount_requires_budget_and_respects_context(service):
    base = {"user_id": "U001", "mode": "amount", "question": "얼마가 좋을까?", "person_id": "P001", "notice_id": "N001", "person_confirmed": True}
    missing = service.chat(base)
    assert missing["status"] == "need_more_info" and missing["pending_field"] == "budget_krw"
    result = service.chat({**base, "question": "최대 8만 원이야"})
    assert result["status"] == "answer"
    assert result["suggested_amount_krw"] == 50000
    context, _ = service.gateway.calls[-1]
    assert context["budget_krw"] == 80000
    assert [(t["direction"], t["amount_krw"]) for t in context["history"]["transactions"]] == [("received", 100000), ("paid", 50000)]


def test_empty_history_and_missing_availability_are_questions(service):
    empty = service.chat({"user_id": "U004", "mode": "amount", "question": "얼마 내면 될까?", "person_id": "P019"})
    assert empty["status"] == "need_more_info"
    assert "이력" in empty["message"]
    attendance = service.chat({"user_id": "U001", "mode": "attendance", "question": "조문하러 갈까?", "notice_id": "N001"})
    assert attendance["status"] == "need_more_info" and attendance["pending_field"] == "availability"
    no_history = service.chat({"user_id": "U004", "mode": "amount", "question": "장례 예산 8만 원", "person_id": "P019", "event_type": "장례"})
    assert no_history["status"] == "answer" and "이력이 없습니다" in no_history["message"]
    assert no_history["model"] is None and no_history.get("suggested_amount_krw") is None


def test_notice_and_identity_are_never_assumed(service):
    forbidden = service.chat({"user_id": "U001", "mode": "notice", "question": "알려줘", "notice_id": "N003"})
    assert forbidden["status"] == "error"
    assert "가상 상주" not in str(forbidden)
    unconfirmed = service.chat({"user_id": "U001", "mode": "amount", "question": "8만원을 생각 중", "person_id": "P001", "notice_id": "N001"})
    assert unconfirmed["status"] == "need_more_info" and unconfirmed["pending_field"] == "person_confirmed"
    explained = service.chat({"user_id": "U001", "mode": "notice", "question": "왜 관련 있나요?", "notice_id": "N001"})
    assert explained["status"] == "answer"
    assert explained["requires_identity_confirmation"] is True
    matches = {item["id"]: item["affiliation_match"] for item in explained["identity_candidates"]}
    assert matches == {"P001": True, "P002": False}
    assert "해든기획팀" in next(item["text"] for item in explained["evidence"] if item["id"] == "N001")


def test_model_failure_is_visible_without_losing_data():
    data = load_data()
    service = ChatService(data, FakeGateway(fail=True))
    result = service.chat({"user_id": "U001", "mode": "history", "question": "이력", "person_id": "P001"})
    assert result["status"] == "error"
    assert data.recommendations("U001")
    assert data.dashboard("U001")["paid_total_krw"] == 420000


def test_attendance_prompt_does_not_mistake_mutual_friends_for_history(service):
    result = service.chat({"user_id": "U001", "mode": "attendance", "question": "조문하러 가도 될까요?", "notice_id": "N001", "availability": "10월 31일 오전 가능"})
    assert result["status"] == "answer"
    sent_context = service.gateway.calls[-1][0]
    assert sent_context["history"] is None
    assert "mutual_count" not in sent_context["notice"]
    assert "score" not in sent_context["notice"]


def test_amount_summary_uses_verified_facts_even_if_model_prose_is_wrong():
    class WrongDescriptionGateway(FakeGateway):
        def generate(self, context, allowed_ids):
            return {"answer": "김도윤 본인의 결혼식에서 받은 기록입니다.", "evidence_ids": sorted(allowed_ids), "suggested_amount_krw": 50000, "model": "test-model"}

    service = ChatService(load_data(), WrongDescriptionGateway())
    result = service.chat({"user_id": "U001", "mode": "amount", "question": "8만 원 이내로 얼마가 좋을까?", "person_id": "P001", "notice_id": "N001", "person_confirmed": True})
    assert result["status"] == "answer"
    assert "김도윤 본인의 결혼식" not in result["message"]
    assert "받은 금액 100,000원" in result["message"]
    assert "낸 금액 50,000원" in result["message"]
    assert "예산 80,000원" in result["message"]


def test_history_associated_with_notice_requires_identity_confirmation(service):
    result = service.chat({"user_id": "U001", "mode": "history", "question": "이 부고와 관련된 이력", "person_id": "P001", "notice_id": "N001"})
    assert result["pending_field"] == "person_confirmed"
    assert service.gateway.calls == []


def test_notice_location_and_time_are_passed_to_the_model(service):
    result = service.chat({"user_id": "U001", "mode": "notice", "question": "부고를 알려줘", "notice_id": "N001"})
    assert result["status"] == "answer"
    sent = service.gateway.calls[-1][0]["notice"]
    assert sent["venue"] and sent["address"] and sent["room"] and sent["visiting_hours"]
    assert "가상" in sent["address"]
    assert sent["publisher_name"] == "이수빈"


def test_missing_notice_details_and_unshared_publisher_are_not_guessed(service):
    result = service.chat({"user_id": "U001", "mode": "notice", "question": "부고를 알려줘", "notice_id": "N002"})
    assert result["status"] == "answer" and "장소 미기록" in result["message"]
    sent = service.gateway.calls[-1][0]["notice"]
    assert sent["venue"] is None and sent["address"] is None and sent["visiting_hours"] is None
    assert sent["publisher_name"] is None and "이수빈" not in result["message"]
