"""가상 계정별 기록과 공유 가능한 부고를 조회한다."""

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from .relationship_priority import priority_score


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DATE = date(2026, 10, 30)


def load_data(path=None):
    """고정된 시연 데이터를 읽어 조회 객체로 만든다."""
    source = Path(path) if path is not None else ROOT / "data" / "demo.json"
    dataset = json.loads(source.read_text(encoding="utf-8-sig"))
    if path is None:
        from .special_fixtures import merge_special_fixtures
        dataset = merge_special_fixtures(dataset)
        dataset = merge_designated_notices(dataset)
    return DemoData(dataset)


def merge_designated_notices(dataset):
    """보낸 사람이 받는 사람을 직접 지정한 시연 소식을 메모리에서만 추가한다."""
    source = ROOT / "data" / "designated_notices.json"
    if not source.exists():
        return dataset
    extra = json.loads(source.read_text(encoding="utf-8-sig"))
    existing = {row["id"] for row in dataset["shared_notices"]}
    users = {row["id"] for row in dataset["users"]}
    for notice in extra:
        if notice["id"] in existing:
            raise ValueError("지정 공유 소식 식별자가 중복됩니다.")
        if notice["publisher_user_id"] not in users or any(uid not in users for uid in notice.get("recipient_user_ids", [])):
            raise ValueError("지정 공유 소식의 계정 참조가 잘못되었습니다.")
    return {**dataset, "shared_notices": [*dataset["shared_notices"], *extra]}


def designated_for(notice, user_id):
    """보낸 사람이 이 계정을 받는 사람으로 직접 지정했는지 확인한다."""
    return (notice.get("audience_scope") == "designated"
            and user_id in (notice.get("recipient_user_ids") or [])
            and notice.get("sharing_authorization") == "confirmed")


def public_legacy_candidate(candidate):
    """기존 부고 화면에 필요한 필드만 반환한다."""
    notice = candidate["notice"]
    fields = ("id", "category", "title", "start_date", "end_date", "time", "region",
              "venue", "address", "room", "visiting_hours")
    public_notice = {key: notice[key] for key in fields if key in notice}
    if "mourner" in notice:
        mourner = notice["mourner"]
        public_notice["mourner"] = (
            {key: mourner[key] for key in ("name", "affiliation", "deceased_relation") if key in mourner}
            if isinstance(mourner, dict) else None
        )
    result = {key: candidate[key] for key in ("relation_type", "publisher_name", "publisher_user_id", "mutual_count", "score", "details",
                                              "priority_score", "priority_reasons", "recipient_group") if key in candidate}
    result["notice"] = public_notice
    return result


class DemoData:
    """데이터 소유자와 공유 조건을 확인하는 시연용 저장소."""

    def __init__(self, dataset):
        self.dataset = dataset
        self.users = {user["id"]: user for user in dataset["users"]}
        self.people_by_id = {person["id"]: person for person in dataset["people"]}
        self.graph = defaultdict(set)
        for relation in dataset["friendships"]:
            if relation["status"] == "accepted" and relation["allow_connection_for_recommendation"]:
                left, right = relation["user_a_id"], relation["user_b_id"]
                self.graph[left].add(right)
                self.graph[right].add(left)

    def list_users(self):
        """계정 선택에 필요한 가상 사용자 정보만 반환한다."""
        return [
            {"id": user["id"], "name": user["name"], "affiliation": user["fictional_affiliation"]}
            for user in self.dataset["users"] if not user["id"].startswith("V4U")
        ]

    def people(self, user_id):
        """해당 계정에 속한 지인만 반환한다."""
        if user_id not in self.users:
            return []
        return [person for person in self.dataset["people"] if person["owner_user_id"] == user_id]

    def events(self, user_id):
        """개인 행사와 명시된 거래를 함께 반환한다."""
        if user_id not in self.users:
            return []
        result = []
        for event in self.dataset["private_events"]:
            if event["owner_user_id"] != user_id:
                continue
            transactions = [
                item for item in self.dataset["transactions"]
                if item["owner_user_id"] == user_id and item["private_event_id"] == event["id"]
            ]
            result.append({
                **event,
                "amount_krw": transactions[0]["amount_krw"] if len(transactions) == 1 else None,
                "transactions": transactions,
            })
        return result

    def history(self, user_id, person_id):
        """선택한 지인의 행사와 받은·낸 거래를 소유자 기준으로 모은다."""
        person = self.people_by_id.get(person_id)
        if person is None or person["owner_user_id"] != user_id:
            return None
        events = [event for event in self.events(user_id) if event["contact_person_id"] == person_id]
        transactions = [transaction for event in events for transaction in event["transactions"]
                        if transaction["contact_person_id"] == person_id]
        return {
            "person": person,
            "events": events,
            "transactions": transactions,
            "received_total_krw": sum(t["amount_krw"] for t in transactions if t["direction"] == "received"),
            "paid_total_krw": sum(t["amount_krw"] for t in transactions if t["direction"] == "paid"),
        }

    def dashboard(self, user_id):
        """해당 계정의 거래 합계와 명시적 0원 기록 건수를 계산한다."""
        # 추가 합성 관계 시연의 거래는 기존 전체 장부 합계에 포함하지 않는다.
        transactions = [item for item in self.dataset["transactions"]
                        if item["owner_user_id"] == user_id and not item["id"].startswith("V4T")]
        return {
            "received_total_krw": sum(t["amount_krw"] for t in transactions if t["direction"] == "received"),
            "paid_total_krw": sum(t["amount_krw"] for t in transactions if t["direction"] == "paid"),
            "received_entry_count": sum(t["direction"] == "received" for t in transactions),
            "paid_entry_count": sum(t["direction"] == "paid" for t in transactions),
            "explicit_zero_entry_count": sum(t["amount_krw"] == 0 for t in transactions),
        }

    def shared_event_for_user(self, user_id, notice, today):
        """공유 조건을 통과한 소식과 확인된 추천 이유를 반환한다."""
        publisher_id = notice.get("publisher_user_id")
        if user_id not in self.users or publisher_id not in self.users or publisher_id == user_id:
            return None
        direct = publisher_id in self.graph[user_id]
        mutual = bool(self.graph[user_id] & self.graph[publisher_id])
        designated = designated_for(notice, user_id)
        if not designated:
            if not direct and not mutual:
                return None
            scope = notice.get("audience_scope")
            if scope != "friends_and_friends_of_friends" and not (scope == "friends_only" and direct):
                return None
            attendance = "direct_friend_attendance" if direct else "friend_of_friend_attendance"
            if notice.get("sharing_authorization") != "confirmed" or notice.get(attendance) != "allowed":
                return None
        if notice.get("status") not in {"active", "scheduled", "ongoing"}:
            return None
        try:
            start = date.fromisoformat(notice["start_date"])
            end = date.fromisoformat(notice["end_date"])
        except (KeyError, TypeError, ValueError):
            return None
        if start > end or end < today:
            return None

        reason = "designated" if designated else "direct_friend" if direct else "friend_of_friend"
        valid_role = "mourner" if notice.get("category") == "장례" else "subject"
        if (notice.get("publisher_name_visible") is True
                and notice.get("related_user_recommendation_allowed") is True
                and notice.get("related_user_id") == publisher_id
                and notice.get("related_role") == valid_role):
            for person in self.people(user_id):
                if (person.get("linked_user_id") == publisher_id
                        and person.get("linked_user_confirmed_for_recommendation") is True
                        and str(person.get("relationship", "")).replace(" ", "") == "직장동료"):
                    reason = "confirmed_colleague"
                    break
        return {
            "notice": notice,
            "reason_code": reason,
            "publisher_name": self.users[publisher_id]["name"] if notice.get("publisher_name_visible") is True else None,
        }

    def shared_event_recommendations(self, user_id, extra_notices, today):
        """허용된 소식에서 확인된 개인 일정 중복을 제외하고 정렬한다."""
        owned_occurrences = {
            event.get("shared_occurrence_id") for event in self.dataset["private_events"]
            if event.get("owner_user_id") == user_id and event.get("status") != "cancelled"
            and event.get("shared_occurrence_id")
        }
        result = []
        for notice in [*self.dataset["shared_notices"], *extra_notices]:
            candidate = self.shared_event_for_user(user_id, notice, today)
            if candidate is None or notice.get("shared_occurrence_id") in owned_occurrences:
                continue
            result.append(candidate)
        priority = {"designated": 0, "confirmed_colleague": 1, "direct_friend": 2, "friend_of_friend": 3}
        result.sort(key=lambda item: (priority[item["reason_code"]], item["notice"]["end_date"],
                                      item["notice"]["start_date"], item["notice"]["id"]))
        return result

    def recommendations(self, user_id, priorities=None):
        """볼 수 있는 소식을 고른 뒤, 사용자가 기록한 관계 중요도로 순서를 정한다.

        볼 수 있는 조건: 친구·친구의 친구에게 공유된 부고, 또는 보낸 사람이 나를 직접 지정한 소식.
        priorities(대상 계정별 중요도)는 순서에만 쓰이고 볼 수 있는 범위를 넓히지 않는다.
        """
        user = self.users.get(user_id)
        if user is None:
            return []
        priorities = priorities or {}
        result = []
        for notice in self.dataset["shared_notices"]:
            publisher_id = notice["publisher_user_id"]
            mutual_ids = self.graph[user_id] & self.graph[publisher_id]
            is_direct = publisher_id in self.graph[user_id]
            if publisher_id == user_id:
                continue
            designated = designated_for(notice, user_id)
            if designated:
                if notice.get("status") not in {"scheduled", "ongoing", "active"}:
                    continue
            else:
                if not is_direct and not mutual_ids:
                    continue
                if notice["category"] != "장례" or notice["status"] not in {"scheduled", "ongoing"}:
                    continue
                if notice["audience_scope"] != "friends_and_friends_of_friends":
                    continue
                attendance_key = "direct_friend_attendance" if is_direct else "friend_of_friend_attendance"
                if notice.get(attendance_key) != "allowed" or notice["sharing_authorization"] != "confirmed":
                    continue
            start = date.fromisoformat(notice["start_date"])
            end = date.fromisoformat(notice["end_date"])
            if end < REFERENCE_DATE:
                continue

            mutual_count = len(mutual_ids)
            mutual_points = 40 * min(mutual_count / 3, 1)
            days = max(0, (start - REFERENCE_DATE).days)
            date_points = 10 * max(0, 30 - days) / 30
            total, weight = mutual_points + date_points, 50
            region_match = None
            if user["preferred_region"] and notice.get("region"):
                region_match = user["preferred_region"] == notice["region"]
                total += 30 * region_match
                weight += 30
            interest_match = None
            if user["preferred_event_types"]:
                interest_match = notice["category"] in user["preferred_event_types"]
                total += 20 * interest_match
                weight += 20
            visible = notice.get("publisher_name_visible") is True
            # 보낸 사람이 공개된 경우에만 내가 기록한 중요도를 반영한다. (숨겨진 보낸 사람을 순서로 추측하지 못하게)
            priority = priority_score(priorities.get(publisher_id) if visible else None, days)
            result.append({
                "notice": notice,
                "relation_type": "designated" if designated else "direct_friend" if is_direct else "friend_of_friend",
                "publisher_name": self.users[publisher_id]["name"] if visible else None,
                "publisher_user_id": publisher_id if visible else None,
                "mutual_count": mutual_count,
                "score": round(total * 100 / weight, 1),
                "details": {"region_match": region_match, "interest_match": interest_match, "days_until_start": days},
                "priority_score": priority["score"],
                "priority_reasons": priority["reasons"],
                "recipient_group": notice.get("recipient_group") if designated else None,
            })
        result.sort(key=lambda item: (-item["priority_score"], -item["score"], item["notice"]["start_date"], item["notice"]["id"]))
        return result

    def notice_for_user(self, user_id, notice_id):
        """추천 조건을 통과한 부고만 식별자로 다시 조회한다."""
        return next((item for item in self.recommendations(user_id) if item["notice"]["id"] == notice_id), None)

    def matching_people(self, user_id, notice):
        """상주 이름이 같은 지인을 후보로 찾되 동일인을 확정하지 않는다."""
        mourner = notice.get("mourner") or {}
        result = []
        for person in self.people(user_id):
            if person["name"] != mourner.get("name"):
                continue
            affiliation = mourner.get("affiliation")
            result.append({
                "person": person,
                "affiliation_match": person["fictional_affiliation"] == affiliation if affiliation else None,
                "requires_user_confirmation": True,
            })
        return result
