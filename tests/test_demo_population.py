"""100명 인맥과 세 계정의 실제 2촌 추천을 임시 SQLite에서 검증한다."""

import json
from collections import Counter
from datetime import date

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.account_store import AccountStore, LoginInput, SignupInput, workspace_owner
from gyeongjosa_ai.api import app
from gyeongjosa_ai.demo_population import (
    BRIDGE, NOTICE_TITLE, RECIPIENT, apply_demo_population, main_workspace, recipient_workspace,
)
from gyeongjosa_ai.demo_state import _db as account_db
from gyeongjosa_ai.dependencies import get_service
from gyeongjosa_ai.integration_api import get_shared_store
from gyeongjosa_ai.test_account_seed import TEST_USER_ID
from gyeongjosa_ai.workspace_store import WorkspaceInput, load_workspace, save_workspace


TODAY = date(2026, 10, 31)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """원래 데이터베이스를 건드리지 않는 임시 시연 환경을 구성한다."""
    monkeypatch.setenv("GYEONGJOSA_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    monkeypatch.setenv("GYEONGJOSA_SHARED_EVENTS_DB", str(tmp_path / "shared.sqlite3"))
    get_service.cache_clear()
    yield tmp_path
    get_service.cache_clear()


def test_population_distributions_and_integrity():
    """기존 상담 인맥을 건드리지 않고 정확히 78명을 생성한다."""
    first = main_workspace(TODAY).model_dump(mode="json")
    assert first == main_workspace(TODAY).model_dump(mode="json")
    assert len(first["people"]) == 78
    assert len([e for e in first["events"] if e["id"].startswith("POP-UPCOMING")]) == 20
    assert Counter(p["relation"] for p in first["people"]) == {
        "직장 동료": 25, "친구": 12, "가족": 15,
        "학교 선후배": 14, "동호회 지인": 12,
    }
    assert Counter(p["closeness_score"] for p in first["people"]) == {
        1: 8, 2: 18, 3: 23, 4: 23, 5: 6,
    }
    counts = Counter(record["personId"] for record in first["records"])
    assert len([p for p in first["people"] if counts[p["id"]] == 0]) == 18
    assert 111 <= len(first["records"]) <= 151
    assert all(record["amount"] > 0 and record["amount"] % 10000 == 0 for record in first["records"])
    assert set(record["direction"] for record in first["records"]) == {"받은 마음", "보낸 마음"}
    event_owner = {event["id"]: event["personId"] for event in first["events"]}
    assert all(event_owner[record["eventId"]] == record["personId"] for record in first["records"])
    assert len(recipient_workspace(TODAY).people) == 15
    assert len(recipient_workspace(TODAY).records) == 20


def test_two_hop_recommendation_and_logins(isolated):
    """세 계정은 같은 비밀번호이고 직접 친구가 아닌 2촌 수신자에게 소식이 추천된다."""
    result = apply_demo_population(TODAY, isolated / "backups")
    assert result["main_people"] == 100
    assert 211 <= result["main_records"] <= 251
    assert result["recipient_people"] == 15
    assert result["recipient_records"] == 20
    assert result["recommendation_reason"] == "friend_of_friend"
    accounts = AccountStore()
    for username in ("test1234", RECIPIENT, BRIDGE):
        signed_in = accounts.login(LoginInput(username=username, password="test1234"))
        accounts.logout(signed_in["token"])
    data = get_service().data
    receiver = workspace_owner(RECIPIENT)
    bridge = workspace_owner(BRIDGE)
    assert bridge in data.graph[TEST_USER_ID]
    assert bridge in data.graph[receiver]
    assert receiver not in data.graph[TEST_USER_ID]
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={
            "username": RECIPIENT, "password": "test1234",
        }).status_code == 200
        feed = client.get("/api/shared-events/recommendations", headers={
            "X-Demo-User-Id": receiver,
        })
        assert feed.status_code == 200
        item = next(item for item in feed.json()["items"] if item["id"] == result["notice_id"])
        assert item["reason_code"] == "friend_of_friend"
        assert client.get("/api/workspace/personal", headers={
            "X-Demo-User-Id": TEST_USER_ID,
        }).status_code == 401
        assert client.get("/api/workspace/personal", headers={
            "X-Demo-User-Id": receiver,
        }).json()["people"]


def test_repeat_does_not_overwrite_user_changes_or_duplicate_links(isolated):
    """재실행해도 시드 자료·계정·친구 링크가 늘지 않고 사용자 수정값이 남는다."""
    first = apply_demo_population(TODAY, isolated / "backups")
    snapshot = load_workspace(TEST_USER_ID)
    current = snapshot["revision"]
    people = list(snapshot["people"])
    people[22]["memo"] = "내가 수정한 메모"
    records = list(snapshot["records"])
    records[-1]["amount"] = 130000
    save_workspace(TEST_USER_ID, WorkspaceInput.model_validate({
        "revision": current, "people": people, "events": snapshot["events"], "records": records,
    }))
    with account_db(AccountStore()) as db:
        old_revision = db.execute("SELECT revision FROM social_state WHERE id=1").fetchone()["revision"]
    second = apply_demo_population(TODAY, isolated / "backups")
    assert second["notice_id"] == first["notice_id"]
    assert second["main_people"] == first["main_people"]
    assert second["main_records"] == first["main_records"]
    assert load_workspace(TEST_USER_ID)["people"][22]["memo"] == "내가 수정한 메모"
    assert load_workspace(TEST_USER_ID)["records"][-1]["amount"] == 130000
    with account_db(AccountStore()) as db:
        row = db.execute("SELECT revision, payload FROM social_state WHERE id=1").fetchone()
        assert row["revision"] == old_revision
        friends = json.loads(row["payload"])["friendships"]
        assert len([f for f in friends if f["status"] == "accepted"]) == 2
    assert len([n for n in get_shared_store().list_all() if n["title"] == NOTICE_TITLE]) == 1
    assert set(second["backed_up"]) == {"accounts", "workspace", "shared_events"}


def test_existing_direct_friendship_blocks_seed_without_erasing_it(isolated):
    """시연 목적과 충돌하는 기존 직접 관계를 임의로 삭제하지 않는다."""
    store = AccountStore()
    result = store.login(LoginInput(username="test1234", password="test1234"))
    store.logout(result["token"])
    signed_up = store.signup(SignupInput(
        username=RECIPIENT, name="기존 계정", password="test1234",
        phone="01012345678", email="existing@example.invalid", workplace="",
        organization="", workType="일반 회사원", visibility="전체 공개",
    ))
    store.logout(signed_up["token"])
    with account_db(store) as db:
        db.execute("UPDATE social_state SET revision=1, payload=? WHERE id=1", (json.dumps({
            "friendships": [{"id": "manual", "from": RECIPIENT, "to": "test1234", "status": "accepted"}],
            "shares": [], "receipts": {},
        }),))
        db.commit()
    with pytest.raises(ValueError, match="직접 친구"):
        apply_demo_population(TODAY, isolated / "backups")
    assert not load_workspace(TEST_USER_ID)["initialized"]
    assert BRIDGE not in {m["username"] for m in store.members()}


def test_existing_password_mismatch_is_not_reset(isolated):
    """기존 계정 비밀번호가 다르면 조용히 바꾸지 않고 중단한다."""
    store = AccountStore()
    existing = store.signup(SignupInput(
        username=RECIPIENT, name="기존 계정", password="different1234",
        phone="01012345678", email="existing@example.invalid", workplace="",
        organization="", workType="일반 회사원", visibility="전체 공개",
    ))
    store.logout(existing["token"])
    with pytest.raises(ValueError, match="비밀번호"):
        apply_demo_population(TODAY, isolated / "backups")
    assert store.login(LoginInput(username=RECIPIENT, password="different1234"))


def test_revoked_notice_is_not_created_again(isolated):
    """사용자가 공유를 철회하면 다음 시드 실행이 공개를 복구하지 않는다."""
    first = apply_demo_population(TODAY, isolated / "backups")
    store = get_shared_store()
    store.revoke(first["notice_id"], TEST_USER_ID)
    next_run = apply_demo_population(TODAY, isolated / "backups")
    assert next_run["notice_id"] == first["notice_id"]
    assert next_run["recommendation_reason"] is None
    assert len([n for n in store.list_all() if n["title"] == NOTICE_TITLE]) == 1
