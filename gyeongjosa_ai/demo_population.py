"""발표용 100명 인맥과 두 계정 사이의 2촌 공유 추천 데이터를 1회 준비한다."""

import json
import random
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

from .account_store import AccountStore, LoginInput, SignupInput, workspace_owner
from .demo_state import _db as account_db
from .dependencies import get_service
from .integration_api import get_shared_store
from .test_account_seed import TEST_USER_ID, ensure_test_workspace
from .workspace_store import WorkspaceInput, _db_path, seed_workspace_once


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "test1234"
RECIPIENT = "test12345"
BRIDGE = "testbridge"
MAIN_SEED = "test1234-population-v1"
RECIPIENT_SEED = "test12345-population-v1"
NOTICE_TITLE = "[합성 2촌 시연] 테스트 사용자의 결혼 소식"
SURNAMES = ("김", "이", "박", "최", "정", "강", "조", "윤", "장", "한")
GIVEN_NAMES = ("가온", "나린", "다예", "도경", "라온", "민서", "서현", "예나", "유준", "하율")
RELATIONS = (["직장 동료"] * 25 + ["친구"] * 12 + ["가족"] * 15
             + ["학교 선후배"] * 14 + ["동호회 지인"] * 12)
CLOSENESS = [1] * 8 + [2] * 18 + [3] * 23 + [4] * 23 + [5] * 6
HISTORY_COUNTS = ([0] * 18 + [1] * 30 + [2] * 11 + [3] * 10
                  + [4] * 3 + [5] * 3 + [6] * 2 + [8])
EVENT_TYPES = ("결혼식", "장례식", "돌잔치", "환갑잔치")
AMOUNTS = (10000, 20000, 30000, 50000, 70000, 100000, 150000, 200000, 300000)
AMOUNT_WEIGHTS = (4, 4, 18, 35, 15, 16, 4, 3, 1)


def _history(rng, person_id, name, count, today, prefix):
    """지급·수령을 구분하고 과거 날짜와 행사 참조가 맞는 장부를 만든다."""
    events, records = [], []
    for index in range(count):
        event_type = rng.choices(EVENT_TYPES, weights=(55, 30, 10, 5))[0]
        event_date = today - timedelta(days=rng.randint(30, 1200))
        event_id = f"{prefix}-E-{person_id}-{index + 1:02d}"
        events.append({
            "id": event_id, "personId": person_id,
            "title": f"[합성] {name} 관련 {event_type}", "type": event_type,
            "date": event_date.isoformat(), "attendance": "unknown",
        })
        records.append({
            "id": f"{prefix}-T-{person_id}-{index + 1:02d}",
            "personId": person_id, "eventId": event_id,
            "type": event_type, "date": event_date.isoformat(),
            "direction": "보낸 마음" if rng.random() < 0.6 else "받은 마음",
            "amount": rng.choices(AMOUNTS, weights=AMOUNT_WEIGHTS)[0],
        })
    return events, records


def main_workspace(today=None):
    """기존 22명과 겹치지 않는 신규 78명의 분포형 인맥을 만든다."""
    today = today or date.today()
    rng = random.Random(20261031)
    names = [surname + given for surname in SURNAMES for given in GIVEN_NAMES]
    rng.shuffle(names)
    relations, scores, counts = list(RELATIONS), list(CLOSENESS), list(HISTORY_COUNTS)
    for values in (relations, scores, counts):
        rng.shuffle(values)
    people, events, records = [], [], []
    for index in range(78):
        person_id = f"POP-P{index + 1:03d}"
        name, relation, score = names[index], relations[index], scores[index]
        people.append({
            "id": person_id, "name": name, "relation": relation,
            "group": "가상 " + ("새봄기획팀" if relation == "직장 동료" else "인맥"),
            "closeness_score": score,
            "importance": "중요" if rng.random() < 0.22 else "보통",
            "special": rng.random() < 0.1,
            "lastMet": (today - timedelta(days=rng.randint(1, 500))).isoformat(),
            "memo": "합성 시연용 인물입니다.",
        })
        past_events, past_records = _history(rng, person_id, name, counts[index], today, "POP")
        events.extend(past_events)
        records.extend(past_records)
        if index < 20:
            event_type = rng.choice(("결혼식", "장례식", "돌잔치"))
            events.append({
                "id": f"POP-UPCOMING-{index + 1:03d}", "personId": person_id,
                "title": f"[합성 예정] {name} {event_type}", "type": event_type,
                "date": (today + timedelta(days=index + 1)).isoformat(),
                "attendance": "unknown", "memo": "발표용 예정 행사",
            })
    return WorkspaceInput.model_validate({
        "revision": 0, "people": people, "events": events, "records": records,
    })


def recipient_workspace(today=None):
    """추천 수신 계정의 독립적인 인맥 15명과 장부 20건을 만든다."""
    today = today or date.today()
    rng = random.Random(20261032)
    names = [surname + given for surname in SURNAMES[2:5] for given in GIVEN_NAMES[:5]]
    people, events, records = [], [], []
    for index, name in enumerate(names):
        person_id = f"POP-RP{index + 1:03d}"
        people.append({
            "id": person_id, "name": name,
            "relation": ("친구", "직장 동료", "학교 선후배")[index % 3],
            "group": "가상 인맥", "closeness_score": index % 5 + 1,
            "importance": "보통", "memo": "합성 시연용 인물입니다.",
        })
        count = 2 if index < 5 else 1
        past_events, past_records = _history(rng, person_id, name, count, today, "POP-R")
        events.extend(past_events)
        records.extend(past_records)
    return WorkspaceInput.model_validate({
        "revision": 0, "people": people, "events": events, "records": records,
    })


def _backup_runtime_databases(paths, backup_dir=None):
    """실행 DB를 SQLite 백업 API로 복제하며 기존 파일은 삭제하지 않는다."""
    folder = Path(backup_dir or ROOT / "data" / (
        "runtime_backup_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    ))
    backed_up = []
    for name, path in paths.items():
        if not path.exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as source, sqlite3.connect(folder / (name + ".sqlite3")) as target:
            source.backup(target)
        backed_up.append(name)
    return backed_up


def _check_accounts(store):
    """기존 계정의 비밀번호를 바꾸지 않고 지정된 비밀번호로 접속 가능한지 확인한다."""
    existing = {member["username"] for member in store.members()}
    for username in ("test1234", RECIPIENT, BRIDGE):
        if username not in existing:
            continue
        try:
            result = store.login(LoginInput(username=username, password=PASSWORD))
        except HTTPException as error:
            raise ValueError(f"기존 {username} 계정의 비밀번호가 다릅니다. 수정하지 않았습니다.") from error
        store.logout(result["token"])
    return existing


def _ensure_accounts(store, existing):
    """일반 회원가입의 검증·암호 해시 경로를 재사용해 합성 계정만 추가한다."""
    if "test1234" not in existing:
        result = store.login(LoginInput(username="test1234", password=PASSWORD))
        store.logout(result["token"])
    for username, name, phone in (
        (RECIPIENT, "추천 수신 시연자", "01000000045"),
        (BRIDGE, "합성 중간 친구", "01000000046"),
    ):
        if username in existing:
            continue
        result = store.signup(SignupInput(
            username=username, name=name, password=PASSWORD,
            phone=phone, email=username + "@example.invalid", workplace="가상 시연팀",
            organization="해커톤", workType="일반 회사원", visibility="전체 공개",
        ))
        store.logout(result["token"])


def _has_direct(friendships):
    """양방향으로 수락된 직접 관계의 충돌을 확인한다."""
    return any(
        link.get("status") == "accepted"
        and {link.get("from"), link.get("to")} == {"test1234", RECIPIENT}
        for link in friendships
    )


def _ensure_two_hop(store):
    """기존 사회관계 자료를 보존하면서 두 개의 수락 관계만 보탠다."""
    from .demo_state import _invalidate_recommendation_cache

    with account_db(store) as db:
        row = db.execute("SELECT revision, payload FROM social_state WHERE id=1").fetchone()
        social = json.loads(row["payload"])
        friends = social["friendships"]
        if _has_direct(friends):
            raise ValueError("시연 계정 사이에 직접 친구 관계가 있어 2촌 추천을 구성할 수 없습니다.")
        changed = False
        for left, right in (("test1234", BRIDGE), (BRIDGE, RECIPIENT)):
            if any(link.get("status") == "accepted"
                   and {link.get("from"), link.get("to")} == {left, right} for link in friends):
                continue
            friends.append({
                "id": f"seed-two-hop-{left}-{right}", "from": left, "to": right,
                "status": "accepted", "createdAt": datetime.now(timezone.utc).isoformat(),
            })
            changed = True
        if changed:
            db.execute("UPDATE social_state SET revision=?, payload=? WHERE id=1",
                       (row["revision"] + 1, json.dumps(social, ensure_ascii=False)))
        db.commit()
    _invalidate_recommendation_cache()


def _ensure_shared_notice(today):
    """2촌 수신용 행사 하나를 생성하고 사용자 철회·수정은 복원하지 않는다."""
    store = get_shared_store()
    existing = next((item for item in store.list_all()
                     if item["publisher_user_id"] == TEST_USER_ID and item["title"] == NOTICE_TITLE), None)
    if existing:
        return existing["id"]
    item = store.create(TEST_USER_ID, {
        "category": "결혼", "title": NOTICE_TITLE,
        "start_date": (today + timedelta(days=7)).isoformat(),
        "end_date": (today + timedelta(days=7)).isoformat(),
        "region": "서울", "venue": "가상 시연 웨딩홀",
        "audience_scope": "friends_and_friends_of_friends",
        "recipient_user_ids": [], "recipient_group": None,
        "sharing_authorization": "confirmed",
        "direct_friend_attendance": "allowed",
        "friend_of_friend_attendance": "allowed",
        "publisher_name_visible": True,
        "related_role": "subject",
        "related_user_recommendation_allowed": False,
    })
    return item["id"]


def apply_demo_population(today=None, backup_dir=None):
    """기존 자료를 백업한 뒤 계정·인맥·2촌 관계를 중복 없이 적용한다."""
    today = today or date.today()
    account_store = AccountStore()
    shared_store = get_shared_store()
    existing = _check_accounts(account_store)
    with account_db(account_store) as db:
        social = json.loads(db.execute("SELECT payload FROM social_state WHERE id=1").fetchone()["payload"])
    if _has_direct(social["friendships"]):
        raise ValueError("test1234와 test12345의 직접 친구 관계를 먼저 확인해야 합니다.")
    backups = _backup_runtime_databases({
        "accounts": account_store.path, "workspace": _db_path(), "shared_events": shared_store.path,
    }, backup_dir)
    _ensure_accounts(account_store, existing)
    ensure_test_workspace()
    main = seed_workspace_once(TEST_USER_ID, MAIN_SEED, main_workspace(today))
    receiver = seed_workspace_once(workspace_owner(RECIPIENT), RECIPIENT_SEED, recipient_workspace(today))
    _ensure_two_hop(account_store)
    notice_id = _ensure_shared_notice(today)
    get_service.cache_clear()
    candidates = get_service().data.shared_event_recommendations(
        workspace_owner(RECIPIENT), shared_store.list_all(), today
    )
    notice = next((item for item in candidates if item["notice"]["id"] == notice_id), None)
    return {
        "main_people": len(main["people"]), "main_records": len(main["records"]),
        "recipient_people": len(receiver["people"]), "recipient_records": len(receiver["records"]),
        "bridge_user_id": workspace_owner(BRIDGE),
        "recipient_user_id": workspace_owner(RECIPIENT),
        "notice_id": notice_id,
        "recommendation_reason": notice["reason_code"] if notice else None,
        "backed_up": backups,
    }


def main():
    """로컬 DB에 발표용 데이터셋을 적용하고 핵심 결과만 출력한다."""
    result = apply_demo_population()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
