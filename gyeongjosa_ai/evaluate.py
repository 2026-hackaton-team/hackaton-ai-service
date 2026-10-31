"""허용된 호출 한도 안에서 두 실제 모델의 가상 사례를 비교한다."""

import argparse
import json
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .ai import FALLBACK_MODEL, PRIMARY_MODEL, ModelGateway, ModelUnavailable
from .data import load_data
from .service import ChatService


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "evaluation"
BUDGET_PATH = DIRECTORY / "budget.json"
MAX_TOTAL = 62
PREVIOUS_RESERVED = 5


class Budget:
    """이전 연결 시도와 평가 요청을 합쳐 상한을 관리한다."""

    def __init__(self):
        DIRECTORY.mkdir(exist_ok=True)
        if BUDGET_PATH.exists():
            self.data = json.loads(BUDGET_PATH.read_text(encoding="utf-8"))
        else:
            self.data = {"limit": MAX_TOTAL, "previous_reserved": PREVIOUS_RESERVED, "evaluation_requests": 0}
            self.save()
        if self.data.get("limit") != MAX_TOTAL or self.data.get("previous_reserved", 0) < PREVIOUS_RESERVED:
            raise ValueError("호출 예산 기록을 확인해 주세요.")

    def save(self):
        """요청 전에 현재 사용량을 저장한다."""
        temporary = BUDGET_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(BUDGET_PATH)

    def claim(self):
        """한도를 넘지 않을 때만 다음 외부 요청을 예약한다."""
        used = self.data["previous_reserved"] + self.data["evaluation_requests"]
        if used >= self.data["limit"]:
            raise ModelUnavailable("실제 API 검증 호출 한도에 도달했습니다.")
        self.data["evaluation_requests"] += 1
        self.save()


class EvaluationGateway(ModelGateway):
    """자동 대체를 끄고 지정한 모델만 호출한다."""

    def __init__(self, model, budget):
        super().__init__()
        self.model = model
        self.budget = budget
        self.last_error = None

    def _request(self, context, system_prompt, model):
        if not self.api_key:
            raise ModelUnavailable("코디세이 API 키가 설정되지 않았습니다.")
        self.budget.claim()
        return super()._request(context, system_prompt, model)

    def classify(self, context, people_ids, notice_ids):
        try:
            return self.classify_for_model(context, people_ids, notice_ids, self.model)
        except ModelUnavailable as exc:
            self.last_error = str(exc.__cause__) if isinstance(exc.__cause__, ValueError) else type(exc.__cause__).__name__
            raise

    def generate(self, context, allowed_ids, preferred_model=None):
        try:
            return self.generate_for_model(context, allowed_ids, self.model)
        except ModelUnavailable as exc:
            self.last_error = str(exc.__cause__) if isinstance(exc.__cause__, ValueError) else type(exc.__cause__).__name__
            raise


def cases():
    """동일한 두 모델 비교에 사용할 가상 사례를 준비한다."""
    selected = {"person_id": "P001", "notice_id": "N001", "person_confirmed": True}
    return [
        {"id": "history", "input": {"user_id": "U001", "question": "해든기획팀 김도윤과 주고받은 기록을 알려줘"}, "intent": "history", "status": "answer"},
        {"id": "amount", "input": {"user_id": "U001", "question": "동료 부고에 얼마를 내면 좋을까? 예산은 최대 8만 원이야", "context": selected}, "intent": "amount", "status": "answer"},
        {"id": "attendance", "input": {"user_id": "U001", "question": "선택한 부고에 조문하러 갈까? 10월 31일 오전은 가능해", "context": {"notice_id": "N001", "availability": "10월 31일 오전은 가능"}}, "intent": "attendance", "status": "answer"},
        {"id": "message", "input": {"user_id": "U001", "question": "동료에게 전할 위로 인사말을 써줘", "context": selected}, "intent": "message", "status": "answer"},
        {"id": "notice", "input": {"user_id": "U001", "question": "선택한 부고가 왜 나와 관련 있나요?", "context": {"notice_id": "N001"}}, "intent": "notice", "status": "answer"},
        {"id": "same_name", "input": {"user_id": "U001", "question": "김도윤과 주고받은 이력을 알려줘"}, "intent": "history", "status": "need_more_info", "pending": "person_id"},
        {"id": "missing_budget", "input": {"user_id": "U004", "question": "솔빛독서모임 김도윤의 장례에 얼마를 내면 좋을까?", "context": {"person_id": "P019", "event_type": "장례"}}, "intent": "amount", "status": "need_more_info", "pending": "budget_krw", "followup": "최대 8만 원이야"},
        {"id": "missing_availability", "input": {"user_id": "U001", "question": "공유된 부고에 조문하러 가는 게 좋을까?", "context": {"notice_id": "N001"}}, "intent": "attendance", "status": "need_more_info", "pending": "availability", "followup": "10월 31일 오전은 시간이 돼요"},
    ]


def check(case, result):
    """기계적으로 확인할 수 있는 상태와 근거를 판정한다."""
    issues = []
    if result.get("status") != case["status"]:
        issues.append("응답 상태 불일치")
    if result.get("intent") != case["intent"]:
        issues.append("질문 의도 불일치")
    if case.get("pending") and result.get("pending_field") != case["pending"]:
        issues.append("추가 질문 항목 불일치")
    evidence_ids = {item["id"] for item in result.get("evidence", [])}
    cited_ids = set(result.get("cited_ids", []))
    if case["id"] == "history" and result.get("status") == "answer" and not {"T001", "T002"}.issubset(evidence_ids):
        issues.append("이력 근거 누락")
    if case["id"] == "history" and result.get("status") == "answer" and not {"T001", "T002"}.issubset(cited_ids):
        issues.append("이력 거래 인용 누락")
    if case["id"] == "amount" and result.get("status") == "answer":
        if not {"T001", "T002", "N001"}.issubset(evidence_ids):
            issues.append("금액 또는 부고 근거 누락")
        if not {"T001", "T002"}.issubset(cited_ids):
            issues.append("금액 거래 인용 누락")
        amount = result.get("suggested_amount_krw")
        if amount is None or not 0 <= amount <= 80000:
            issues.append("예산 안의 금액 선택지 없음")
    if case["id"] == "notice" and result.get("status") == "answer" and not result.get("requires_identity_confirmation"):
        issues.append("동일인 확인 안내 누락")
    if case["id"] == "same_name" and result.get("status") == "need_more_info":
        if {item["id"] for item in result.get("options", [])} != {"P001", "P002"}:
            issues.append("동명이인 선택지 불일치")
    return issues


def save_results(report, result_path):
    """실제 호출 도중 중단돼도 지금까지의 결과를 보관한다."""
    temporary = result_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(result_path)


def main():
    """두 모델에 같은 사례를 실행하고 결과와 호출 수를 기록한다."""
    parser = argparse.ArgumentParser(description="가상 사례로 두 모델의 응답을 검증합니다.")
    parser.add_argument("--recheck", action="store_true", help="보완한 이력·금액·참석 사례만 다시 확인합니다.")
    args = parser.parse_args()
    budget = Budget()
    if budget.data["previous_reserved"] + budget.data["evaluation_requests"] >= budget.data["limit"]:
        print("실제 API 검증 호출 한도에 도달했습니다. 더 이상 요청하지 않습니다.")
        return 1
    data = load_data()
    first_request_count = budget.data["evaluation_requests"]
    result_path = DIRECTORY / f"results_{datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d_%H%M%S_%f')}.json"
    report = {
        "started_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "notice": "모든 입력은 가상 데이터이며 일부 표현의 의미 정확성은 별도 검토가 필요하다.",
        "run_kind": "보완 후 재검증" if args.recheck else "전체 비교",
        "models": [PRIMARY_MODEL, FALLBACK_MODEL],
        "cases": [],
    }
    for model in report["models"]:
        gateway = EvaluationGateway(model, budget)
        service = ChatService(data, gateway)
        selected_cases = cases()
        if args.recheck:
            names = {"history", "amount", "attendance"}
            selected_cases = [case for case in selected_cases if case["id"] in names]
        for case in selected_cases:
            gateway.last_error = None
            before = budget.data["evaluation_requests"]
            started = time.perf_counter()
            result = service.chat_auto(case["input"])
            elapsed = round(time.perf_counter() - started, 3)
            issues = check(case, result)
            record = {
                "model": model, "case": case["id"], "status": result.get("status"),
                "intent": result.get("intent"), "pending_field": result.get("pending_field"),
                "message": result.get("message"), "response_model": result.get("model"),
                "classification_model": result.get("classification_model"),
                "evidence_ids": [item["id"] for item in result.get("evidence", [])],
                "cited_ids": result.get("cited_ids", []), "suggested_amount_krw": result.get("suggested_amount_krw"),
                "elapsed_seconds": elapsed, "requests": budget.data["evaluation_requests"] - before,
                "automatic_issues": issues, "semantic_review": "미검토", "diagnostic": gateway.last_error,
            }
            report["cases"].append(record)
            save_results(report, result_path)
            print(f"{model} {case['id']}: {record['status']} / {'통과' if not issues else ', '.join(issues)} / {elapsed}초", flush=True)
            if case.get("followup") and result.get("status") == "need_more_info" and result.get("pending_field") == case["pending"]:
                before = budget.data["evaluation_requests"]
                started = time.perf_counter()
                follow = service.chat_auto({"user_id": case["input"]["user_id"], "question": case["followup"], "context": result.get("context", {})})
                elapsed = round(time.perf_counter() - started, 3)
                follow_record = {
                    "model": model, "case": case["id"] + "_followup", "status": follow.get("status"),
                    "intent": follow.get("intent"), "pending_field": follow.get("pending_field"),
                    "message": follow.get("message"), "response_model": follow.get("model"),
                    "classification_model": follow.get("classification_model"),
                    "evidence_ids": [item["id"] for item in follow.get("evidence", [])],
                    "cited_ids": follow.get("cited_ids", []), "suggested_amount_krw": follow.get("suggested_amount_krw"),
                    "elapsed_seconds": elapsed, "requests": budget.data["evaluation_requests"] - before,
                    "automatic_issues": [] if follow.get("status") == "answer" else ["후속 답변 미완료"], "semantic_review": "미검토",
                }
                report["cases"].append(follow_record)
                save_results(report, result_path)
                print(f"{model} {follow_record['case']}: {follow_record['status']} / {elapsed}초", flush=True)

    report["summary"] = {}
    for model in report["models"]:
        rows = [row for row in report["cases"] if row["model"] == model]
        timings = [row["elapsed_seconds"] for row in rows]
        report["summary"][model] = {
            "cases": len(rows), "automatic_passes": sum(not row["automatic_issues"] for row in rows),
            "median_seconds": round(statistics.median(timings), 3) if timings else None,
            "max_seconds": max(timings) if timings else None,
        }
    report["budget"] = budget.data
    save_results(report, result_path)
    run_requests = budget.data["evaluation_requests"] - first_request_count
    print(f"이번 평가 요청 {run_requests}회, 이전 예약 포함 누적 {budget.data['previous_reserved'] + budget.data['evaluation_requests']}회", flush=True)
    print(f"결과 파일: evaluation/{result_path.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
