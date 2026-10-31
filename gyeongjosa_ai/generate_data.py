"""원본 시연 데이터에 재현 가능한 가상 사용자와 경조사 기록을 더한다."""

import argparse
import copy
import random
from datetime import date, timedelta

from . import seed_db

REFERENCE_DATE = date(2026, 10, 30)
SURNAMES = ("강", "고", "구", "권", "남", "노", "류", "문", "서", "한")
GIVEN_NAMES = ("가온", "다온", "도하", "라희", "로아", "서우", "수아", "예담", "이든", "하온")
AFFILIATIONS = ("새봄기획실", "모아디자인팀", "가람연구회", "온빛개발팀", "푸른교육실", "다정독서모임")
REGIONS = ("서울", "인천", "경기", "부산", "대전", None)
CATEGORIES = ("결혼", "장례", "백일", "돌", "생일", "환갑", "칠순", "팔순")
RELATIONS = ("직장 동료", "친구", "동호회 지인", "가족 지인", "학교 선후배")
HISTORY_QUESTIONS = (
    "{name}님과 주고받은 경조사 내역을 알려줘.",
    "{name}에게 받은 것과 내가 낸 기록이 있을까?",
    "{name} 경조사 이력을 날짜별로 정리해 줘.",
    "전에 {name}님과 어떤 경조사를 주고받았는지 확인하고 싶어.",
    "{name} 관련 금액 기록만 간단히 보여줄래?",
    "내 기록에서 {name}의 행사와 주고받은 금액을 찾아줘.",
    "{name}한테 예전에 낸 돈이랑 받은 돈이 있나?",
    "{name}님과의 경조사 기록을 확인해 주세요.",
)
AMOUNT_QUESTIONS = (
    "{name}님의 행사에 얼마를 내면 좋을까? 예산은 최대 8만 원이야.",
    "{name} 경조사에 낼 금액을 과거 기록과 예산 5만 원을 참고해서 생각해 줘.",
    "{name}님 행사에 대한 금액 선택지를 알려줘. 예산은 10만 원까지야.",
    "{name}에게 마음을 전할 금액을 고민 중이야. 7만 원 안에서 참고할 만한 게 있을까?",
    "이번 {name}님 경조사비를 정하려고 해. 최대 8만 원으로 선택지를 보여줘.",
    "{name}와 주고받은 내역을 참고해서 5만 원 이하로 금액을 생각해 줘.",
    "{name} 행사에 얼마를 준비하면 될까? 이번 예산은 10만 원이야.",
    "{name}님께 전할 경조사비가 고민돼. 7만 원까지 생각하고 있어.",
)
ATTENDANCE_QUESTIONS = (
    "{name}님 행사에 참석할지 고민이야. 무엇을 확인해야 할까?",
    "{name}의 행사에 직접 가는 게 좋을지 생각을 정리해 줘.",
    "{name}에게 방문하기 어렵다면 어떤 방법으로 마음을 전할 수 있을까?",
    "{name}님 소식에 어떻게 대응할지 시간과 상황을 함께 살펴봐 줘.",
    "{name} 행사에 갈 수 있을지 판단하려면 어떤 정보가 필요할까?",
    "직접 참석이 어려울 때 {name}님께 마음을 전할 방법을 알려줘.",
    "{name}님을 찾아뵐지 먼저 연락드릴지 고민돼.",
    "{name} 행사에 참석하는 것과 다른 방법의 고려 사항을 정리해 줘.",
)
MESSAGE_QUESTIONS = (
    "{name}님께 보낼 짧고 정중한 인사말 초안을 써 줘.",
    "{name}에게 부담스럽지 않게 마음을 전하는 문구를 만들어 줘.",
    "{name}님 행사에 전할 말을 예의 있게 작성해 줄래?",
    "{name}에게 전할 메시지를 한두 문장으로 정리해 줘.",
    "{name}님께 예의를 갖춰 전할 수 있는 말을 짧게 적어 줘.",
    "{name}에게 보낼 인사말을 너무 길지 않게 작성해 줘.",
    "{name}님께 전할 문구를 차분한 말투로 제안해 줘.",
    "{name}에게 마음을 담아 보낼 한 문장 초안을 보여줘.",
)
SITUATIONS = (
    "바쁜 일정으로 지인의 경조사 기록을 한 번에 정리하려는 가상 사용자",
    "주고받은 기록을 확인하고 현재 예산에 맞춰 결정하려는 가상 사용자",
    "경조사 기록이 적어 추가 정보를 입력하며 판단하려는 가상 사용자",
    "이름이 비슷한 지인들을 구분해 기록을 확인하려는 가상 사용자",
    "방문 가능 여부를 확인한 뒤 마음을 전할 방법을 고르려는 가상 사용자",
    "상대와의 관계에 맞는 짧은 인사말을 검토하려는 가상 사용자",
    "과거에 받은 금액과 이번에 낼 수 있는 예산을 따로 확인하려는 가상 사용자",
    "여러 경조사 중 권한이 확인된 부고부터 살펴보려는 가상 사용자",
)


def next_number(items, prefix):
    """기존 식별자와 겹치지 않는 다음 숫자를 구한다."""
    numbers = [int(item["id"][len(prefix):]) for item in items if item["id"].startswith(prefix)]
    return max(numbers, default=0) + 1


def add_demo_notice_details(data):
    """시연용 부고에만 가상의 장소와 공개 설정을 추가한다."""
    synthetic_users = {user["id"] for user in data["users"] if user["login_id"].startswith("synthetic_")}
    for index, notice in enumerate(data["shared_notices"]):
        if notice["category"] != "장례" or notice["id"] == "N002":
            continue
        region = notice.get("region") or "지역 미상"
        notice.setdefault("venue", f"가상 {region} 마음빛 장례식장")
        notice.setdefault("address", f"가상 주소: {region} 가상구 마음길 {10 + index}")
        notice.setdefault("room", f"가상 {1 + index % 5}호실")
        notice.setdefault("visiting_hours", "가상 조문 시간 10:00~20:00")
        notice.setdefault("publisher_name_visible", notice["id"] == "N001" or notice["publisher_user_id"] in synthetic_users)


def add_scenario_fixtures(data, fixtures):
    """참조와 소유자를 검증한 뒤 가상 시나리오 데이터를 추가한다."""
    version = fixtures["metadata"]["version"]
    collections = ("users", "friendships", "people", "private_events", "transactions", "shared_notices")
    for collection in collections:
        existing_ids = {item["id"] for item in data[collection]}
        addition_ids = [item["id"] for item in fixtures[collection]]
        if len(addition_ids) != len(set(addition_ids)) or existing_ids.intersection(addition_ids):
            raise ValueError(f"시나리오 데이터의 {collection} 식별자가 중복됩니다.")

    users = {item["id"] for item in data["users"] + fixtures["users"]}
    people = {item["id"]: item for item in data["people"] + fixtures["people"]}
    events = {item["id"]: item for item in data["private_events"] + fixtures["private_events"]}
    for friendship in fixtures["friendships"]:
        if (friendship["user_a_id"] not in users or friendship["user_b_id"] not in users
                or friendship["user_a_id"] == friendship["user_b_id"]
                or friendship["status"] not in {"accepted", "pending"}
                or type(friendship["allow_connection_for_recommendation"]) is not bool):
            raise ValueError("시나리오 친구 관계가 올바르지 않습니다.")
    for person in fixtures["people"]:
        if person["owner_user_id"] not in users or (person["linked_user_id"] and person["linked_user_id"] not in users):
            raise ValueError("시나리오 지인의 사용자 참조가 올바르지 않습니다.")
    for event in fixtures["private_events"]:
        person = people.get(event["contact_person_id"])
        if (person is None or person["owner_user_id"] != event["owner_user_id"]
                or event["category"] not in data["event_categories"]
                or event["status"] not in {"scheduled", "ongoing", "finished", "cancelled"}
                or date.fromisoformat(event["start_date"]) > date.fromisoformat(event["end_date"])):
            raise ValueError("시나리오 행사의 참조 또는 상태가 올바르지 않습니다.")
    for transaction in fixtures["transactions"]:
        event = events.get(transaction["private_event_id"])
        if (event is None or event["owner_user_id"] != transaction["owner_user_id"]
                or event["contact_person_id"] != transaction["contact_person_id"]
                or transaction["direction"] not in {"paid", "received"}
                or type(transaction["amount_krw"]) is not int or transaction["amount_krw"] < 0):
            raise ValueError("시나리오 거래의 참조 또는 금액이 올바르지 않습니다.")
    for notice in fixtures["shared_notices"]:
        if (notice["publisher_user_id"] not in users or notice["category"] not in data["event_categories"]
                or notice["status"] not in {"scheduled", "ongoing", "finished", "cancelled"}
                or notice["audience_scope"] not in {"private", "friends_and_friends_of_friends"}
                or notice["sharing_authorization"] not in {"confirmed", "unknown"}
                or notice["direct_friend_attendance"] not in {"allowed", "not_allowed", "unknown"}
                or notice["friend_of_friend_attendance"] not in {"allowed", "not_allowed", "unknown"}
                or date.fromisoformat(notice["start_date"]) > date.fromisoformat(notice["end_date"])):
            raise ValueError("시나리오 공유 소식의 참조 또는 상태가 올바르지 않습니다.")

    for collection in collections:
        data[collection].extend(copy.deepcopy(fixtures[collection]))
    data["metadata"]["scenario_fixtures_version"] = version


def generate_dataset(original):
    """원본을 보존하며 고정 시드 데이터와 검토용 사례를 생성한다."""
    data = copy.deepcopy(original)
    for notice in data["shared_notices"]:
        notice.setdefault("direct_friend_attendance", "unknown")
    rng = random.Random(20261030)
    user_number = next_number(data["users"], "U")
    friend_number = next_number(data["friendships"], "F")
    person_number = next_number(data["people"], "P")
    event_number = next_number(data["private_events"], "E")
    transaction_number = next_number(data["transactions"], "T")
    notice_number = next_number(data["shared_notices"], "N")

    added_users = []
    for index in range(100):
        name = SURNAMES[index // 10] + GIVEN_NAMES[index % 10]
        if index == 1:
            name = added_users[0]["name"]
        user = {
            "id": f"U{user_number + index:03}",
            "name": name,
            "login_id": f"synthetic_{index + 1:03}",
            "demo_account": False,
            "fictional_affiliation": AFFILIATIONS[index % len(AFFILIATIONS)],
            "preferred_region": REGIONS[index % len(REGIONS)],
            "preferred_event_types": None if index % 9 == 0 else ["장례", CATEGORIES[index % len(CATEGORIES)]],
        }
        if user["preferred_event_types"] and user["preferred_event_types"][1] == "장례":
            user["preferred_event_types"] = ["장례"]
        added_users.append(user)
    data["users"].extend(added_users)

    pairs = set()
    for index in range(100):
        for step in (1, 2):
            pairs.add(tuple(sorted((index, (index + step) % 100))))
        if index % 2 == 0:
            pairs.add(tuple(sorted((index, (index + 3) % 100))))

    neighbours = {index: [] for index in range(100)}
    for pair_index, (left, right) in enumerate(sorted(pairs)):
        neighbours[left].append(right)
        neighbours[right].append(left)
        data["friendships"].append({
            "id": f"F{friend_number:03}",
            "user_a_id": added_users[left]["id"],
            "user_b_id": added_users[right]["id"],
            "status": "pending" if pair_index % 29 == 0 else "accepted",
            "allow_connection_for_recommendation": pair_index % 17 != 0,
        })
        friend_number += 1

    people_by_owner = {}
    for index, user in enumerate(added_users):
        people_by_owner[user["id"]] = []
        for neighbour in sorted(neighbours[index]):
            other = added_users[neighbour]
            person = {
                "id": f"P{person_number:03}",
                "owner_user_id": user["id"],
                "linked_user_id": other["id"],
                "name": other["name"],
                "relationship": RELATIONS[(index + neighbour) % len(RELATIONS)],
                "fictional_affiliation": other["fictional_affiliation"],
            }
            person_number += 1
            data["people"].append(person)
            people_by_owner[user["id"]].append(person)

    generated_scenarios = []
    for index, user in enumerate(added_users):
        contacts = people_by_owner[user["id"]]
        for _ in range(rng.randint(2, 10)):
            person = rng.choice(contacts)
            event_day = REFERENCE_DATE + timedelta(days=rng.randint(-730, 90))
            status = "finished" if event_day < REFERENCE_DATE else "scheduled" if event_day > REFERENCE_DATE else "ongoing"
            category = rng.choice(CATEGORIES)
            event = {
                "id": f"E{event_number:03}",
                "owner_user_id": user["id"],
                "contact_person_id": person["id"],
                "category": category,
                "title": f"가상 지인의 {category} 행사",
                "subject_relation": "지인",
                "start_date": event_day.isoformat(),
                "end_date": event_day.isoformat(),
                "region": rng.choice(REGIONS[:-1]),
                "status": status,
                "actual_attendance": rng.choice(("attended", "not_attended", "unknown")) if status == "finished" else "unknown",
                "personal_attendance_plan": None,
                "shared_occurrence_id": None,
            }
            event_number += 1
            data["private_events"].append(event)
            if status == "finished" and rng.random() < 0.72:
                data["transactions"].append({
                    "id": f"T{transaction_number:03}",
                    "owner_user_id": user["id"],
                    "private_event_id": event["id"],
                    "contact_person_id": person["id"],
                    "direction": rng.choice(("paid", "paid", "received")),
                    "amount_krw": rng.choice((0, 30000, 50000, 70000, 100000)),
                    "note": None,
                })
                transaction_number += 1

        person = contacts[index % len(contacts)]
        name = person["name"]
        generated_scenarios.append({
            "user_id": user["id"],
            "person_id": person["id"],
            "situation": SITUATIONS[index % len(SITUATIONS)],
            "questions": {
                "history": HISTORY_QUESTIONS[index % len(HISTORY_QUESTIONS)].format(name=name),
                "amount": AMOUNT_QUESTIONS[index % len(AMOUNT_QUESTIONS)].format(name=name),
                "attendance": ATTENDANCE_QUESTIONS[index % len(ATTENDANCE_QUESTIONS)].format(name=name),
                "message": MESSAGE_QUESTIONS[index % len(MESSAGE_QUESTIONS)].format(name=name),
            },
        })

    for index in range(0, 100, 2):
        publisher = added_users[index]
        mourner = people_by_owner[publisher["id"]][index % len(people_by_owner[publisher["id"]])]
        start = REFERENCE_DATE + timedelta(days=(index % 27) - 1)
        end = start + timedelta(days=2)
        status = "ongoing" if start <= REFERENCE_DATE <= end else "scheduled"
        if index % 26 == 0:
            status = "cancelled"
        data["shared_notices"].append({
            "id": f"N{notice_number:03}",
            "publisher_user_id": publisher["id"],
            "source_type": "third_party",
            "category": "장례",
            "title": "가상 지인 가족의 부고",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "region": publisher["preferred_region"] or "서울",
            "status": status,
            "audience_scope": "private" if index % 22 == 0 else "friends_and_friends_of_friends",
            "friend_of_friend_attendance": "unknown" if index % 18 == 0 else "allowed",
            "direct_friend_attendance": "unknown" if index % 20 == 0 else "not_allowed" if index % 18 == 0 else "allowed",
            "sharing_authorization": "unknown" if index % 14 == 0 else "confirmed",
            "mourner": {
                "name": mourner["name"],
                "affiliation": mourner["fictional_affiliation"],
                "deceased_relation": "가족",
            },
            "registered_at": "2026-10-30T15:00:00+09:00",
            "shared_occurrence_id": None,
        })
        notice_number += 1

    data["metadata"]["version"] = "1.1-prototype"
    data["metadata"]["recommendation_weights"] = {"mutual": 40, "region": 30, "category": 20, "date": 10}
    data["metadata"]["generation_note"] = "추가된 100명과 질문은 허구이며 고정 시드와 작성된 예시 문구로 생성했다."
    data["generated_scenarios"] = generated_scenarios
    add_demo_notice_details(data)
    fixtures = seed_db.load("scenario_fixtures")
    add_scenario_fixtures(data, fixtures)
    return data


def main():
    """작업용 원본 사본에서 고정된 시연 데이터를 만들어 시드 DB에 저장한다."""
    parser = argparse.ArgumentParser(description="고정된 가상 시연 데이터를 생성합니다.")
    parser.add_argument("--force", action="store_true", help="기존 작업용 시연 데이터를 명시적으로 덮어씁니다.")
    args = parser.parse_args()
    original = seed_db.load("original_demo")
    if seed_db.has("demo") and not args.force:
        raise SystemExit("시드 DB에 demo 자료가 이미 있습니다. 보관 후 재생성하거나 --force를 명시하세요.")
    seed_db.save("demo", generate_dataset(original))
    print(f"가상 데이터 생성 완료: {seed_db.SEED_DB} (demo)")


if __name__ == "__main__":
    main()
