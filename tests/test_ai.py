"""모델 교체와 응답 검증이 외부 호출 없이 작동하는지 확인한다."""

import json

import httpx
import pytest

from gyeongjosa_ai.ai import (
    FALLBACK_MODEL, INTENT_FALLBACK_MODEL, INTENT_PRIMARY_MODEL,
    PRIMARY_MODEL, ModelGateway, ModelUnavailable,
    model_request_budget, parse_intent, parse_response,
)


def response(answer="기록을 참고해 직접 결정해 주세요.", ids=None, suggested=None):
    return {"choices": [{"message": {"content": json.dumps({"answer": answer, "evidence_ids": ids or [], "suggested_amount_krw": suggested}, ensure_ascii=False)}}]}


def test_primary_falls_back_and_identifies_actual_model():
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["model"] == "claude-opus-4-8":
            return httpx.Response(503)
        return httpx.Response(200, json=response(ids=["T001"]))

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    result = gateway.generate({"mode": "history"}, {"T001"})
    assert result["model"] == "gpt-5.4-mini"
    assert [item["model"] for item in requests] == ["claude-opus-4-8", "gpt-5.4-mini"]
    assert all("temperature" not in item and "top_p" not in item for item in requests)


def test_invented_evidence_and_excess_budget_are_rejected():
    def handler(request):
        payload = json.loads(request.content)
        if payload["model"] == "claude-opus-4-8":
            return httpx.Response(200, json=response(ids=["T999"], suggested=50000))
        return httpx.Response(200, json=response(ids=["T001"], suggested=90000))

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    with pytest.raises(ModelUnavailable):
        gateway.generate({"mode": "amount", "budget_krw": 80000}, {"T001"})


def test_both_models_failing_reports_failure():
    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(ModelUnavailable):
        gateway.generate({"mode": "history"}, {"T001"})


def test_classifier_falls_back_when_primary_returns_unowned_person():
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload["model"])
        person_id = "P999" if payload["model"] == INTENT_PRIMARY_MODEL else "P001"
        content = json.dumps({"intent": "history", "person_id": person_id, "notice_id": None, "event_type": None})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    result = gateway.classify({"question": "가상 지인의 이력"}, {"P001"}, set())
    assert result["person_id"] == "P001" and result["model"] == INTENT_FALLBACK_MODEL
    assert requests == [INTENT_PRIMARY_MODEL, INTENT_FALLBACK_MODEL]


def test_fallback_classification_keeps_fallback_for_answer():
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload["model"])
        return httpx.Response(200, json=response(ids=["T001"]))

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    result = gateway.generate({"mode": "history"}, {"T001"}, preferred_model="gpt-5.4-mini")
    assert result["model"] == "gpt-5.4-mini"
    assert requests == ["gpt-5.4-mini"]


def test_amount_response_must_cite_each_transaction():
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload["model"])
        ids = ["P001"] if payload["model"] == "claude-opus-4-8" else ["T001", "T002"]
        return httpx.Response(200, json=response(ids=ids, suggested=50000))

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    context = {"mode": "amount", "budget_krw": 80000, "history": {"transactions": [{"id": "T001"}, {"id": "T002"}]}}
    result = gateway.generate(context, {"P001", "T001", "T002"})
    assert result["model"] == "gpt-5.4-mini"
    assert set(result["evidence_ids"]) == {"T001", "T002"}
    assert requests == ["claude-opus-4-8", "gpt-5.4-mini"]


def test_known_amounts_in_model_prose_are_redacted_and_unrecorded_amounts_rejected():
    context = {"mode": "amount", "budget_krw": 80000, "history": {"transactions": [{"id": "T001", "amount_krw": 100000}, {"id": "T002", "amount_krw": 50000}]}}
    content = json.dumps({"answer": "이전에 10만 원을 받았고 5만 원을 냈으니 5만 원을 검토하세요.", "evidence_ids": ["T001", "T002"], "suggested_amount_krw": 50000}, ensure_ascii=False)
    parsed = parse_response(content, context, {"T001", "T002"})
    assert "10만 원" not in parsed["answer"] and "5만 원" not in parsed["answer"]
    assert parsed["suggested_amount_krw"] == 50000
    invalid = json.dumps({"answer": "7만 원을 내셨습니다.", "evidence_ids": ["T001", "T002"], "suggested_amount_krw": 50000}, ensure_ascii=False)
    with pytest.raises(ValueError):
        parse_response(invalid, context, {"T001", "T002"})


def test_scenario_explanation_uses_real_gateway_and_validates_fallback():
    """출처 없는 금액이 나오면 다른 모델을 호출하고 실제 사용 모델을 기록한다."""
    models = []

    def handler(request):
        payload = json.loads(request.content)
        models.append(payload["model"])
        analysis = ("새로운 9만 원을 추천합니다." if payload["model"] == "claude-opus-4-8"
                    else "평소보다 큰 금액에는 여러 사정이 있을 수 있어요. 감사만 전하고 이유는 단정하지 마세요.")
        return httpx.Response(200, json={"choices": [{"message": {
            "content": json.dumps({"analysis": analysis}, ensure_ascii=False),
        }}]})

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    result = gateway.explain_scenario({
        "question": "이번에는 왜 더 줬을까요?",
        "known_amounts_krw": [50000, 200000],
    })
    assert result["model"] == "gpt-5.4-mini"
    assert "여러 사정" in result["analysis"]
    assert models == ["claude-opus-4-8", "gpt-5.4-mini"]


def test_scenario_explanation_rejects_invalid_model_output():
    """두 모델 모두 근거 없는 금액을 제안하면 성공으로 표시하지 않는다."""
    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {
            "content": '{"analysis":"7만 원을 내세요."}',
        }}]})
    ))
    with pytest.raises(ModelUnavailable):
        gateway.explain_scenario({"question": "어떤 의미일까요?", "known_amounts_krw": [50000]})


@pytest.mark.parametrize(("meal", "expected"), [(False, False), (True, True), (None, None)])
def test_meal_intent_accepts_optional_structured_answer(meal, expected):
    """모델의 명시적인 식사 판단만 허용하고 누락된 구형 응답은 유지한다."""
    payload = json.dumps({"intent": "amount", "person_id": None, "notice_id": None,
                          "event_type": "결혼", "attendance_with_meal": meal})
    assert parse_intent(payload, set(), set())["attendance_with_meal"] is expected
    old = '{"intent":"amount","person_id":null,"notice_id":null,"event_type":"결혼"}'
    assert parse_intent(old, set(), set())["attendance_with_meal"] is None


@pytest.mark.parametrize("meal", ["아니요", 0, 1, [], {}])
def test_meal_intent_rejects_invalid_type(meal):
    """의미 판단값이 불명확하면 잘못된 형식을 조용히 적용하지 않는다."""
    payload = json.dumps({"intent": "amount", "person_id": None, "notice_id": None,
                          "event_type": "결혼", "attendance_with_meal": meal}, ensure_ascii=False)
    with pytest.raises(ValueError, match="식사 여부"):
        parse_intent(payload, set(), set())


def test_model_request_timeout_for_demo():
    """모델당 과도한 재시도 대신 기존 기본 제한시간을 공유하며 설정을 유지한다."""
    assert ModelGateway(api_key="test").timeout == 30
    assert ModelGateway(api_key="test", timeout=15).timeout == 15


def test_internal_field_names_never_pass_response_validation():
    """생성형 답변에 내부 자료 필드가 나오면 외부 노출 전에 차단한다."""
    context = {"mode": "history", "history": {"transactions": []}}
    for key in ("subject_relation", "suggested_amount_krw", "person_id"):
        payload = json.dumps({"answer": f"내부 정보 {key}를 확인하세요.",
                              "evidence_ids": [], "suggested_amount_krw": None},
                             ensure_ascii=False)
        with pytest.raises(ValueError, match="내부 필드"):
            parse_response(payload, context, set())


def test_model_fallback_shares_one_timeout_budget():
    """두 모델 재시도가 각각 제한시간 전체를 새로 받지 않는다."""
    import time

    calls = []

    class DelayedGateway(ModelGateway):
        def generate_for_model(self, context, allowed_ids, model, timeout=None):
            calls.append((model, timeout))
            if model == "claude-opus-4-8":
                time.sleep(0.02)
                raise ModelUnavailable("첫 모델 오류")
            return {"answer": "확인했습니다.", "evidence_ids": [], "model": model}

    gateway = DelayedGateway(api_key="test", timeout=1)
    assert gateway.generate({}, set())["model"] == "gpt-5.4-mini"
    assert len(calls) == 2
    assert 0 < calls[1][1] < calls[0][1] <= 1


def test_primary_and_fallback_have_separate_limits():
    """주 모델은 20초, 보조 모델은 10초까지만 요청한다."""
    calls = []

    class RecordingGateway(ModelGateway):
        def generate_for_model(self, context, allowed_ids, model, timeout=None):
            calls.append((model, timeout))
            if model == PRIMARY_MODEL:
                raise ModelUnavailable("주 모델 실패")
            return {"model": model, "answer": "확인", "evidence_ids": []}

    result = RecordingGateway(api_key="test").generate({}, set())
    assert result["model"] == FALLBACK_MODEL
    assert [model for model, _ in calls] == [PRIMARY_MODEL, FALLBACK_MODEL]
    assert 0 < calls[0][1] <= 20
    assert 0 < calls[1][1] <= 10
    assert sum(timeout for _, timeout in calls) <= 30


def test_classification_and_generation_share_total_budget(monkeypatch):
    """의도 분류와 답변 생성은 모델 구성이 달라도 30초 예산을 공유한다."""
    from gyeongjosa_ai import ai

    clock = [0.0]
    monkeypatch.setattr(ai.time, "monotonic", lambda: clock[0])
    calls = []

    class ClockedGateway(ModelGateway):
        def classify_for_model(self, context, people_ids, notice_ids, model, timeout=None):
            calls.append(("classify", model, timeout))
            clock[0] += 12
            return {"intent": "amount", "person_id": None, "notice_id": None,
                    "event_type": "결혼", "model": model}

        def generate_for_model(self, context, allowed_ids, model, timeout=None):
            calls.append(("generate", model, timeout))
            if model == PRIMARY_MODEL:
                clock[0] += 10
                raise ModelUnavailable("답변 주 모델 실패")
            clock[0] += 7
            return {"model": model, "answer": "확인", "evidence_ids": []}

    class Conversation:
        gateway = ClockedGateway(api_key="test")

        @model_request_budget
        def run(self):
            self.gateway.classify({}, set(), set())
            return self.gateway.generate({}, set())

    assert Conversation().run()["model"] == FALLBACK_MODEL
    assert calls == [
        ("classify", INTENT_PRIMARY_MODEL, 20),
        ("generate", PRIMARY_MODEL, 18),
        ("generate", FALLBACK_MODEL, 8),
    ]
    assert clock[0] == 29


def test_intent_primary_is_mini_and_fallback_is_gemini():
    """의도 분류만 두 경량 모델을 사용하고 최종 답변 순서는 유지한다."""
    assert INTENT_PRIMARY_MODEL == "gpt-5.4-mini"
    assert INTENT_FALLBACK_MODEL == "gemini-3.1-flash-lite"
    assert PRIMARY_MODEL == "claude-opus-4-8"
    assert FALLBACK_MODEL == "gpt-5.4-mini"


def test_intent_models_use_20_and_10_second_limits():
    """분류 모델 순서와 시간 한도가 맞고 두 모델 실패는 오류가 된다."""
    calls = []

    class RecordingGateway(ModelGateway):
        def classify_for_model(self, context, people_ids, notice_ids, model, timeout=None):
            calls.append((model, timeout))
            if model == INTENT_PRIMARY_MODEL:
                raise ModelUnavailable("첫 분류 실패")
            return {"intent": "amount", "person_id": None, "notice_id": None,
                    "event_type": "결혼", "model": model}

    result = RecordingGateway(api_key="test").classify({}, set(), set())
    assert result["model"] == INTENT_FALLBACK_MODEL
    assert [model for model, _ in calls] == [INTENT_PRIMARY_MODEL, INTENT_FALLBACK_MODEL]
    assert 0 < calls[0][1] <= 20
    assert 0 < calls[1][1] <= 10


def test_intent_failure_keeps_generation_routing_unchanged():
    """분류용 Gemini는 응답 생성 후보가 아니다."""
    requested = []

    def handler(request):
        payload = json.loads(request.content)
        requested.append(payload["model"])
        return httpx.Response(200, json=response())

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    generated = gateway.generate({"mode": "history"}, set())
    assert generated["model"] == PRIMARY_MODEL
    assert requested == [PRIMARY_MODEL]


def test_fallback_alone_still_uses_ten_seconds():
    """분류 단계에서 보조 모델을 선택하면 생성도 보조 모델을 유지한다."""
    calls = []

    class RecordingGateway(ModelGateway):
        def generate_for_model(self, context, allowed_ids, model, timeout=None):
            calls.append((model, timeout))
            return {"model": model, "answer": "확인", "evidence_ids": []}

    result = RecordingGateway(api_key="test").generate({}, set(), preferred_model=FALLBACK_MODEL)
    assert result["model"] == FALLBACK_MODEL
    assert len(calls) == 1 and calls[0][0] == FALLBACK_MODEL
    assert 0 < calls[0][1] <= 10
