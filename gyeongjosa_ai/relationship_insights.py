"""사용자 소유 가상 거래와 관계 메모를 감정 단정 없이 해석한다."""
from __future__ import annotations

from statistics import mean

from app.recommender import DEMO, owned_person


def analyze_relationship_case(*, user_id: str, person_id: str, scenario_id: str) -> dict:
    """금액의 양방향 기록·최근 변화·사용자 메모를 구분해 요약한다."""
    person = owned_person(user_id, person_id)
    if not person or "relationship_context" not in person:
        raise ValueError("이 계정의 관계 시연 인물을 조회할 수 없습니다.")
    context = person["relationship_context"]
    events = {row["id"]: row for row in DEMO["private_events"]
              if row["owner_user_id"] == user_id}
    history = sorted((
        {**row, "date": events[row["private_event_id"]]["start_date"]}
        for row in DEMO["transactions"]
        if row["owner_user_id"] == user_id and row["contact_person_id"] == person_id
        and row["private_event_id"] in events
    ), key=lambda item: (item["date"], item["id"]))
    paid = [row for row in history if row["direction"] == "paid"]
    received = [row for row in history if row["direction"] == "received"]
    paid_avg = round(mean(row["amount_krw"] for row in paid)) if paid else None
    received_avg = round(mean(row["amount_krw"] for row in received)) if received else None
    messages = []
    if paid and received:
        messages.append(
            f"내가 낸 기록 {len(paid)}건의 평균은 {paid_avg:,}원, "
            f"상대에게서 받은 기록 {len(received)}건의 평균은 {received_avg:,}원입니다."
        )
    elif history:
        messages.append("한 방향의 거래 기록만 있으므로 호혜성을 비교할 수 없습니다.")

    if scenario_id == "relation_give_more" and paid_avg and received_avg:
        if paid_avg > received_avg:
            messages.append("내 지급 평균이 더 높지만 이 차이만으로 상대의 인성이나 배려 정도를 판단할 수 없습니다.")
    elif scenario_id == "relation_receive_more" and paid_avg and received_avg:
        if received_avg > paid_avg:
            messages.append("받은 금액이 더 많아도 같은 액수를 갚아야 할 의무가 생기는 것은 아닙니다.")
    elif scenario_id in {"relation_recent_large", "relation_recent_small"} and len(received) >= 3:
        latest = received[-1]["amount_krw"]
        preceding = round(mean(row["amount_krw"] for row in received[:-1]))
        if preceding:
            messages.append(
                f"가장 최근 받은 금액 {latest:,}원은 이전 {len(received)-1}건 평균 "
                f"{preceding:,}원과 차이가 있습니다. 금액만으로 상대의 의도나 관계 변화를 확정할 수 없습니다."
            )

    closeness = context.get("closeness_score")
    if closeness is not None and scenario_id in {
        "relation_close_friend", "relation_nonmonetary", "relation_drift", "relation_peer_pressure",
    }:
        messages.append(f"인맥관리에서 사용자가 기록한 현재 친밀도는 5점 만점에 {closeness}점입니다.")
    if scenario_id == "relation_attendance" and context.get("attendance_summary"):
        attendance = context["attendance_summary"]
        messages.append(
            f"사용자 기록상 본인 참석은 {attendance['my_attended']}/{attendance['my_events']}회, "
            f"상대 참석은 {attendance['their_attended']}/{attendance['their_events']}회입니다. "
            "불참 이유는 알 수 없으므로 무관심으로 단정하지 않습니다."
        )
    if scenario_id == "relation_nonmonetary" and context.get("non_monetary_support"):
        messages.append(
            "사용자는 비금전적 도움으로 " + ", ".join(context["non_monetary_support"]) +
            "을 기록했습니다. 도움을 금액으로 환산하지 않습니다."
        )
    if scenario_id == "relation_drift":
        history_scores = context.get("closeness_history", [])
        if len(history_scores) >= 2:
            messages.append(
                f"사용자 친밀도 기록은 {history_scores[0]['score']}점에서 "
                f"{history_scores[-1]['score']}점으로 변했습니다. "
                f"마지막 교류 기록은 {context.get('last_contact_date', '미상')}입니다."
            )
    if scenario_id == "relation_budget" and context.get("monthly_event_count"):
        messages.append(
            f"사용자 메모에는 이번 달 경조사 {context['monthly_event_count']}건으로 "
            "경제적 부담이 있다고 적혀 있습니다. 과거 금액을 유지할 의무는 없습니다."
        )
    if scenario_id == "relation_peer_pressure" and context.get("group_reference_amount_krw"):
        messages.append(
            f"주변 모임의 {context['group_reference_amount_krw']:,}원은 "
            "사용자가 들었다고 기록한 가상 관행이며, 검증된 통계나 의무 기준은 아닙니다."
        )
    if scenario_id == "relation_close_friend":
        messages.append("사용자가 높이 평가한 친밀도를 존중하되 금액을 자동으로 올리는 근거로 사용하지 않습니다.")

    messages.append("금전 내역과 관계 메모는 선택의 참고 자료입니다. 상대방의 감정·경제 사정을 추측하거나 보답을 강요하지 않습니다.")
    return {
        "messages": messages,
        "paid_count": len(paid), "received_count": len(received),
        "paid_average_krw": paid_avg, "received_average_krw": received_avg,
        "closeness_score": closeness, "relationship_note": context.get("relationship_note"),
        "comparison_reference_krw": context.get("comparison_reference_krw"),
        "reference_provenance": context.get("reference_provenance"),
        "history": [{"id": row["id"], "date": row["date"],
                     "direction": row["direction"], "amount_krw": row["amount_krw"]}
                    for row in history],
    }
