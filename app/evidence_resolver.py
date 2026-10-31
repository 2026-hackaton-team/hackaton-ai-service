"""공개 근거 검색 및 실제 적용/제외 사유 추적."""
from __future__ import annotations
from .knowledge import KB

def collect(*, event_type: str, relationship: str, attendance_with_meal: bool | None,
            legal_assessment: dict, kb=None, search_plan: dict | None = None) -> dict:
    kb = kb or KB
    p = search_plan or {}
    survey = kb.eligible_amount_source(event_type=event_type, relationship=relationship,
                                       attendance_with_meal=attendance_with_meal)
    legal = kb.retrieve(p.get("legal", "청탁금지법 공직자등 직무 관련 부조 경조사비 예외 5만원"),
                        event_type=event_type, legal_risk=True, top_k=10)
    stats = kb.retrieve(p.get("statistical", f"{event_type} {relationship} 축의금 부의금 설문"),
                        event_type=event_type, relationship=relationship, top_k=10)
    selected = set(legal_assessment["source_ids"])
    if survey: selected.add(survey["id"])
    rows = {d["id"]: dict(d) for d in (stats+legal)}
    for doc in kb.documents:
        if doc["id"] in selected and doc["id"] not in rows:
            rows[doc["id"]] = {
                "id": doc["id"], "title": doc["title"], "publisher": doc["publisher"],
                "url": doc["url"], "published_at": doc["published_at"], "source_type": doc["source_type"],
                "excerpt": doc["text"], "score": 0.0, "amount_reference_eligible": False
            }
    for d in rows.values():
        if d["id"] in legal_assessment["source_ids"]:
            d["decision_role"] = "applied_legal"
        elif survey and d["id"] == survey["id"]:
            d["decision_role"] = "applied_statistic"
        else:
            d["decision_role"] = "context_only"
        d["amount_reference_eligible"] = bool(survey and d["id"] == survey["id"])
        d["excluded_reason"] = None if d["decision_role"] != "context_only" else (
            "프로필과 법적 적용 요건 일치가 확인되지 않음" if d["source_type"] == "legal_guidance"
            else "직접 일치하는 행사·관계·참석 통계가 아니므로 금액 계산에 미사용"
        )
    evidence = sorted(rows.values(), key=lambda x: (
        0 if x["decision_role"].startswith("applied") else 1, -x.get("score",0), x["id"]
    ))
    return {"evidence":evidence[:12], "amount_source":survey,
            "applied_ids":sorted(selected), "excluded_ids":sorted(set(rows)-selected)}
