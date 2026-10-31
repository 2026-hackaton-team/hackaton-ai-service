"""발표용 test1234 가상 계정의 서버 시드 데이터를 구성한다."""

from datetime import datetime, timedelta, timezone

TEST_USER_ID = "TEST1234"
TEST_LOGIN = "test1234"
PERSON_NAMES = (
    "김도윤", "박하은", "이수빈", "정유림", "한소민", "최유정",
    "오지훈", "서예린", "강민혁", "윤지아", "송재현", "조하람",
    "노서윤", "문지환", "백채원", "임현우", "전소희", "홍서준",
    "장유나", "고태현", "신채린", "배성민", "유하진", "남지후",
)
RELATIONS = ("친구", "직장동료", "가족", "선후배", "거래처", "동호회")


def _today():
    """서울 기준의 오늘 날짜를 사용해 시연 일정 만료를 방지한다."""
    return datetime.now(timezone(timedelta(hours=9))).date()


def _notice(number, owner, category, title, days, scope, recipients=None):
    """추천 공개 조건을 만족하는 합성 소식 한 건을 만든다."""
    day = (_today() + timedelta(days=days)).isoformat()
    return {
        "id": "TEST-SHARED-" + str(number).zfill(2),
        "publisher_user_id": owner, "category": category, "title": title,
        "start_date": day, "end_date": day, "region": "서울",
        "venue": "가상 서울 행사장", "status": "active",
        "audience_scope": scope, "recipient_user_ids": recipients or [],
        "sharing_authorization": "confirmed",
        "direct_friend_attendance": "allowed",
        "friend_of_friend_attendance": "allowed",
        "publisher_name_visible": True,
        "related_role": "mourner" if category == "장례" else "subject",
        "related_user_id": owner,
        "related_user_recommendation_allowed": True,
        "shared_occurrence_id": None,
    }


def extend_test_dataset(dataset):
    """기존 가상 사용자·인맥·공유 소식에 테스트 계정만 추가한다."""
    if any(user["id"] == TEST_USER_ID for user in dataset["users"]):
        raise ValueError("테스트 계정 ID가 기존 데이터와 충돌합니다.")
    user = {
        "id": TEST_USER_ID, "name": "테스트 사용자", "login_id": TEST_LOGIN,
        "demo_account": True, "fictional_affiliation": "마음결 시연팀",
        "preferred_region": "서울",
        "preferred_event_types": ["결혼", "장례", "돌"],
    }
    links = [
        {"id": "TEST-FRIEND-" + str(i), "user_a_id": TEST_USER_ID,
         "user_b_id": other, "status": "accepted",
         "allow_connection_for_recommendation": True}
        for i, other in enumerate(("SCU001", "SCU002"), 1)
    ]
    notices = [
        _notice(1, "SCU001", "결혼", "친구가 공유한 김서연 결혼식", 12, "friends_only"),
        _notice(2, "SCU006", "결혼", "친구의 친구가 공유한 오하늘 결혼식", 19,
                "friends_and_friends_of_friends"),
        _notice(3, "SCU006", "돌", "함께 아는 인연의 돌잔치", 27,
                "friends_and_friends_of_friends"),
        _notice(4, "SCU003", "장례", "지정 수신한 직장 관계자 부고", 4,
                "designated", [TEST_USER_ID]),
    ]
    users = {row["id"] for row in dataset["users"]}
    if any(link["user_b_id"] not in users for link in links) or "SCU003" not in users:
        raise ValueError("테스트용 공유자 또는 친구 계정이 없습니다.")
    return {
        **dataset,
        "users": [*dataset["users"], user],
        "friendships": [*dataset["friendships"], *links],
        "shared_notices": [*dataset["shared_notices"], *notices],
    }


def test_workspace():
    """많은 개인 인맥·본인 행사·양방향 거래를 생성한다."""
    today = _today()
    people = []
    for i, name in enumerate(PERSON_NAMES):
        people.append({
            "id": "TEST-P" + str(i + 1).zfill(3),
            "name": name, "relation": RELATIONS[i % len(RELATIONS)],
            "group": ("대학 동기", "회사", "가족", "동호회")[i % 4],
            "importance": ("매우 중요", "중요", "보통")[i % 3],
            "closeness_score": 5 - (i % 5), "special": i % 7 == 0,
            "lastMet": (today - timedelta(days=i * 11)).isoformat(),
            "memo": "경조사 시연을 위한 합성 관계 · 금액은 개인 기록으로 가정",
            "interactions": [],
        })
    events = []
    for i in range(15):
        person = people[i]
        kind = ("결혼식", "장례식", "돌잔치", "생일")[i % 4]
        events.append({
            "id": "TEST-E" + str(i + 1).zfill(3),
            "personId": person["id"], "title": person["name"] + " " + kind,
            "type": kind, "date": (today + timedelta(days=2 + i * 4)).isoformat(),
            "time": "13:00", "location": "가상 서울 행사장",
            "attendance": "참석" if i % 3 else "",
            "reminderDays": 3, "memo": "테스트용 가상 일정",
        })
    for i, (title, kind) in enumerate((("내 결혼식", "결혼식"),
                                       ("우리 아이 돌잔치", "돌잔치"),
                                       ("가족 환갑잔치", "환갑"))):
        events.append({
            "id": "TEST-ME" + str(i + 1), "owner": "me", "personId": "",
            "title": title, "type": kind,
            "date": (today + timedelta(days=21 + 15 * i)).isoformat(),
            "time": "12:00", "location": "가상 서울 연회장",
            "attendance": "", "reminderDays": 7, "memo": "내가 등록한 합성 행사",
        })
    amounts = (30000, 50000, 70000, 100000, 150000, 200000)
    records = []
    for i in range(120):
        person = people[i % 20]
        direction = "보낸 마음" if i % 2 == 0 else "받은 마음"
        amount = amounts[(i // 3 + i % 5) % len(amounts)]
        if i == 119:
            amount = 300000
        records.append({
            "id": "TEST-R" + str(i + 1).zfill(3),
            "personId": person["id"], "eventId": "",
            "type": ("결혼식", "장례식", "돌잔치")[i % 3],
            "date": (today - timedelta(days=1 + i * 6)).isoformat(),
            "direction": direction, "amount": amount,
            "memo": "합성 거래 · 상대의 의도는 알 수 없음",
        })
    return {"revision": 0, "people": people, "events": events, "records": records}


def own_shared_events():
    """서버가 소유권과 공유 철회를 관리할 등록 소식을 만든다."""
    now = datetime.now(timezone.utc).isoformat()
    result = []
    for i, (category, title, days) in enumerate((
        ("결혼", "내가 등록한 시연 결혼 소식", 21),
        ("돌", "내가 등록한 시연 돌잔치", 36),
        ("환갑", "내가 등록한 시연 환갑 소식", 51),
    ), 1):
        day = (_today() + timedelta(days=days)).isoformat()
        result.append({
            "id": "TEST-MINE-" + str(i), "publisher_user_id": TEST_USER_ID,
            "category": category, "title": title,
            "start_date": day, "end_date": day,
            "region": "서울", "venue": "가상 서울 연회장", "status": "active",
            "audience_scope": "friends_only", "recipient_user_ids": [],
            "recipient_group": None, "sharing_authorization": "confirmed",
            "direct_friend_attendance": "allowed",
            "friend_of_friend_attendance": "not_allowed",
            "publisher_name_visible": True,
            "related_role": "subject",
            "related_user_id": TEST_USER_ID,
            "related_user_recommendation_allowed": True,
            "shared_occurrence_id": None,
            "created_at": now, "updated_at": now,
        })
    return result
