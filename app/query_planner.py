"""비식별 필드로 검색 질의를 계획한다. 필수 법률 검색은 생략 불가."""
from __future__ import annotations
import json
import os

def plan(event_type: str, relationship: str, attendance_with_meal: bool | None,
         mode: str = "auto") -> dict:
    queries = {
        "legal": "청탁금지법 공직자등 직무 관련 부조 경조사비 예외 5만원",
        "statistical": f"{event_type} {relationship} 축의금 부의금 설문 적정 금액" + (" 참석 식사" if attendance_with_meal else ""),
    }
    # LLM은 추가 검색어 제안만 허용. 공식 법률 검색은 항상 고정한다.
    if mode == "offline" or not os.getenv("OPENAI_API_KEY"):
        return {"mode": "deterministic", "llm_used": False, "queries": queries}
    try:
        from openai import OpenAI
        response = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=12, max_retries=0).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=("경조사 공개 통계 검색용 짧은 한국어 질의 하나만 JSON 객체로 반환. "
                          "키는 statistical이어야 하며 공직자등 법률 검색을 생략하거나 개인의 인명을 생성하지 말 것."),
            input=json.dumps({"event_type": event_type, "relationship": relationship,
                              "attendance_with_meal": attendance_with_meal}, ensure_ascii=False),
            max_output_tokens=90, store=False,
        )
        obj = json.loads(response.output_text.strip())
        q = obj.get("statistical")
        if isinstance(q, str) and 5 <= len(q) <= 120:
            queries["statistical"] = q
            return {"mode": "llm_assisted", "llm_used": True, "queries": queries}
    except Exception:
        pass
    return {"mode": "deterministic_fallback", "llm_used": False, "queries": queries}
