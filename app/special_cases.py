"""검증된 공식 근거와 합성 가정만으로 특별 경조사비 경계를 검사한다."""
from __future__ import annotations

import hashlib

from .knowledge import KB
from .legal_policy import RULEBOOK

SOURCES = {
    "teacher_parent": "ACRC-TEACHER-PARENT",
    "cash_and_wreath": "ACRC-CASH-WREATH",
    "public_dol": "ACRC-DOL-EXCEPTION",
}


def assess_special(scenario_id: str, *, cash_krw: int | None = None,
                   wreath_krw: int | None = None) -> dict | None:
    """공식 근거를 검증하지 못하면 허용 결론을 내리지 않는다."""
    source_id = SOURCES.get(scenario_id)
    if source_id is None:
        return None
    doc = KB.by_id.get(source_id)
    valid = bool(doc and doc.get("verified") is True and doc.get("url")
                 and hashlib.sha256(doc["text"].encode("utf-8")).hexdigest()
                 == RULEBOOK["source_checksums"].get(source_id))
    if not valid:
        return {
            "status": "NEEDS_EXPERT_REVIEW", "reason": "특별 사례의 공식 근거를 검증하지 못했습니다.",
            "source_ids": [], "missing_questions": ["공식 자료의 최신성·적용 조건을 확인해 주세요."],
        }
    base = {"source_ids": [source_id], "missing_questions": []}
    if scenario_id == "teacher_parent":
        return {**base, "status": "POTENTIALLY_PROHIBITED",
                "reason": "가상 학부모와 현직 담임교사 사이의 축의금은 소액이어도 해당 부조 예외가 적용되기 어려워 금전 제공을 권하지 않습니다."}
    if scenario_id == "public_dol":
        return {**base, "status": "NEEDS_EXPERT_REVIEW",
                "reason": "돌잔치는 결혼·장례 경조사비 예외에 포함되지 않습니다. 다른 허용 사유의 적용 여부는 별도로 확인해야 합니다.",
                "missing_questions": ["별도 예외 사유 및 상대와의 현재 직무 관련성을 확인해 주세요."]}
    if cash_krw is None or wreath_krw is None:
        return {**base, "status": "NEEDS_FACTS",
                "reason": "조의금과 조화 금액을 각각 확인해야 합니다.",
                "missing_questions": ["현금과 조화의 금액을 각각 알려 주세요."]}
    total = cash_krw + wreath_krw
    if cash_krw > 50000 or wreath_krw > 100000 or total > 100000:
        return {**base, "status": "POTENTIALLY_PROHIBITED",
                "reason": f"현금 {cash_krw:,}원 + 조화 {wreath_krw:,}원 = {total:,}원으로, 가정한 부조 예외의 종류별·합계 가액 조건을 초과합니다."}
    return {**base, "status": "CONDITIONALLY_ALLOWED",
            "reason": f"현금 {cash_krw:,}원 + 조화 {wreath_krw:,}원 = {total:,}원은 가정한 부조 예외의 가액 조건 안입니다. 실제 부조 목적 및 이해관계에 따라 허용 여부는 달라집니다."}
