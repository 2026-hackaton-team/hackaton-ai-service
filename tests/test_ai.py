"""모델 교체와 응답 검증이 외부 호출 없이 작동하는지 확인한다."""

import json

import httpx
import pytest

from gyeongjosa_ai.ai import ModelGateway, ModelUnavailable, parse_response


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
    assert result["model"] == "gpt-5.4"
    assert [item["model"] for item in requests] == ["claude-opus-4-8", "gpt-5.4"]
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
        person_id = "P999" if payload["model"] == "claude-opus-4-8" else "P001"
        content = json.dumps({"intent": "history", "person_id": person_id, "notice_id": None, "event_type": None})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    result = gateway.classify({"question": "가상 지인의 이력"}, {"P001"}, set())
    assert result["person_id"] == "P001" and result["model"] == "gpt-5.4"
    assert requests == ["claude-opus-4-8", "gpt-5.4"]


def test_fallback_classification_keeps_fallback_for_answer():
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload["model"])
        return httpx.Response(200, json=response(ids=["T001"]))

    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(handler))
    result = gateway.generate({"mode": "history"}, {"T001"}, preferred_model="gpt-5.4")
    assert result["model"] == "gpt-5.4"
    assert requests == ["gpt-5.4"]


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
    assert result["model"] == "gpt-5.4"
    assert set(result["evidence_ids"]) == {"T001", "T002"}
    assert requests == ["claude-opus-4-8", "gpt-5.4"]


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
    assert result["model"] == "gpt-5.4"
    assert "여러 사정" in result["analysis"]
    assert models == ["claude-opus-4-8", "gpt-5.4"]


def test_scenario_explanation_rejects_invalid_model_output():
    """두 모델 모두 근거 없는 금액을 제안하면 성공으로 표시하지 않는다."""
    gateway = ModelGateway(api_key="test", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {
            "content": '{"analysis":"7만 원을 내세요."}',
        }}]})
    ))
    with pytest.raises(ModelUnavailable):
        gateway.explain_scenario({"question": "어떤 의미일까요?", "known_amounts_krw": [50000]})
