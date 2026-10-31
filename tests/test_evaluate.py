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
