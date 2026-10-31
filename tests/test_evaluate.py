"""실제 모델 평가의 호출 한도 기록을 확인한다."""

import pytest

from gyeongjosa_ai import evaluate
from gyeongjosa_ai.ai import ModelUnavailable


def test_budget_persists_and_never_exceeds_limit(tmp_path, monkeypatch):
    directory = tmp_path / "evaluation"
    monkeypatch.setattr(evaluate, "DIRECTORY", directory)
    monkeypatch.setattr(evaluate, "BUDGET_PATH", directory / "budget.json")
    budget = evaluate.Budget()
    assert budget.data["previous_reserved"] == 5
    budget.data["evaluation_requests"] = evaluate.MAX_TOTAL - budget.data["previous_reserved"] - 1
    budget.save()
    budget.claim()
    assert evaluate.Budget().data["evaluation_requests"] == evaluate.MAX_TOTAL - budget.data["previous_reserved"]
    with pytest.raises(ModelUnavailable):
        budget.claim()


def test_budget_500_preserves_prior_consumption(tmp_path, monkeypatch):
    """기존 62회 평가 기록은 유지하고 새 총 상한만 500회로 계산한다."""
    import json

    directory = tmp_path / "evaluation"
    directory.mkdir()
    budget_path = directory / "budget.json"
    budget_path.write_text(json.dumps({
        "limit": 500, "previous_reserved": 5, "evaluation_requests": 57,
        "additional_approval": {"date": "2026-10-31", "extra_calls": 12},
    }), encoding="utf-8")
    monkeypatch.setattr(evaluate, "DIRECTORY", directory)
    monkeypatch.setattr(evaluate, "BUDGET_PATH", budget_path)
    assert evaluate.MAX_TOTAL == 500
    budget = evaluate.Budget()
    assert budget.data["previous_reserved"] + budget.data["evaluation_requests"] == 62
    assert budget.data["limit"] - 62 == 438
    budget.claim()
    assert evaluate.Budget().data["evaluation_requests"] == 58


def test_evaluation_gateway_accepts_timeout_keyword(tmp_path, monkeypatch):
    """평가용 모델도 제한시간을 전달하되 호출 이전에 예산을 차감한다."""
    import json

    directory = tmp_path / "evaluation"
    monkeypatch.setattr(evaluate, "DIRECTORY", directory)
    monkeypatch.setattr(evaluate, "BUDGET_PATH", directory / "budget.json")
    budget = evaluate.Budget()

    class NoNetworkGateway(evaluate.EvaluationGateway):
        def __init__(self):
            super().__init__("gpt-5.4-mini", budget)
            self.api_key = "fake"

    gateway = NoNetworkGateway()
    def handler(request):
        return __import__("httpx").Response(200, json={"choices": [{"message": {
            "content": json.dumps({"intent": "history", "person_id": None,
                                   "notice_id": None, "event_type": None}),
        }}]})

    import httpx
    gateway.transport = httpx.MockTransport(handler)
    result = gateway.classify_for_model({"question": "거래 이력"}, set(), set(),
                                        "gpt-5.4-mini", timeout=5)
    assert result["intent"] == "history"
    assert budget.data["evaluation_requests"] == 1
