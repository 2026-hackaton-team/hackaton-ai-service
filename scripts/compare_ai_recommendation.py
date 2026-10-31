"""같은 합성 상담을 모델 설명 유무로 비교해 실제 생성 여부를 표시한다."""

import json

from gyeongjosa_ai.ai import ModelGateway
from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.service import ChatService


def main():
    """고정된 요청과 자료를 재사용하며 추천 결과와 AI 해석을 나란히 확인한다."""
    data = load_data()
    user_id = "U001"
    person = data.people(user_id)[0]
    request = {
        "user_id": user_id,
        "person_id": person["id"],
        "mode": "amount",
        "event_type": "결혼",
        "attendance_with_meal": True,
        "budget_krw": 70000,
        "question": f"{person['name']} 결혼식에 참석해서 식사해요. 예산은 7만원이에요.",
    }

    no_model = ChatService(data, ModelGateway(api_key="")).chat(request)
    gateway = ModelGateway()
    with_model = ChatService(data, gateway).chat(request) if gateway.api_key else None

    for label, result in (("기존 추천 엔진", no_model), ("추천 엔진 + 실제 LLM", with_model)):
        if result is None:
            print(f"{label}: 실제 LLM 미실행 (API 키 미설정)")
            continue
        print(json.dumps({
            "비교 방식": label,
            "추천 금액": result.get("suggested_amount_krw"),
            "정책 판정": (result.get("v4_analysis") or {}).get("status"),
            "AI 상태": (result.get("v4_analysis") or {}).get("ai_status"),
            "사용 모델": result.get("model"),
            "답변": result.get("message"),
        }, ensure_ascii=False, indent=2))

    if with_model is None or (with_model.get("v4_analysis") or {}).get("ai_status") != "generated":
        raise SystemExit("실제 모델 해석이 확인되지 않아 AI 유무 비교를 완료하지 않았습니다.")
    if no_model.get("suggested_amount_krw") != with_model.get("suggested_amount_krw"):
        raise SystemExit("동일한 입력에서 추천 금액이 달라져 추가 검증이 필요합니다.")


if __name__ == "__main__":
    main()
