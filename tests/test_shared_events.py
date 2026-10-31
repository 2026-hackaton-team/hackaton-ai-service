"""가상 공유 경조사의 공개 조건과 계정별 동작을 확인한다."""

import copy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app
from gyeongjosa_ai.data import DemoData, load_data


TODAY = date(2026, 10, 30)


def notice(**changes):
    """추천 조건을 통과하는 가상 공유 소식을 만든다."""
    item = {
        "id": "DSE-TEST",
        "publisher_user_id": "SCU006",
        "category": "결혼",
        "title": "가상 결혼 소식",
        "start_date": "2026-10-30",
        "end_date": "2026-11-01",
        "region": "서울",
        "venue": None,
        "status": "active",
        "audience_scope": "friends_and_friends_of_friends",
        "sharing_authorization": "confirmed",
        "direct_friend_attendance": "allowed",
        "friend_of_friend_attendance": "allowed",
        "publisher_name_visible": True,
        "related_user_id": "SCU006",
        "related_role": "subject",
        "related_user_recommendation_allowed": True,
        "shared_occurrence_id": None,
    }
    item.update(changes)
    return item


def data_with_colleague():
    """명시적으로 확인된 가상 직장동료를 추가한다."""
    dataset = copy.deepcopy(load_data().dataset)
    dataset["people"] = [person for person in dataset["people"] if person["id"] != "SCP019"]
    dataset["people"].append({
        "id": "TEST-COLLEAGUE",
        "owner_user_id": "SCU001",
        "linked_user_id": "SCU006",
        "name": "한소민",
        "relationship": "직장동료",
        "fictional_affiliation": "가상 회사",
        "linked_user_confirmed_for_recommendation": True,
    })
    return DemoData(dataset)


def test_existing_weddings_and_restricted_notices():
    data = load_data()
    items = data.shared_event_recommendations("SCU001", [], TODAY)
    by_id = {item["notice"]["id"]: item for item in items}
    assert by_id["SCN007"]["reason_code"] == "direct_friend"
    assert by_id["SCN008"]["reason_code"] == "friend_of_friend"
    assert not {"SCN003", "SCN004", "SCN005", "SCN006", "SCN010", "SCN011", "SCN012"} & set(by_id)


def test_colleague_requires_confirmed_link_and_subject_disclosure():
    data = data_with_colleague()
    assert data.shared_event_for_user("SCU001", notice(), TODAY)["reason_code"] == "confirmed_colleague"
    for changes in (
        {"publisher_name_visible": False},
        {"related_user_recommendation_allowed": False},
        {"related_user_id": None},
        {"related_user_id": "SCU005"},
        {"related_role": None},
    ):
        assert data.shared_event_for_user("SCU001", notice(**changes), TODAY)["reason_code"] == "direct_friend"
    person = data.people_by_id["TEST-COLLEAGUE"]
    person["linked_user_confirmed_for_recommendation"] = False
    assert data.shared_event_for_user("SCU001", notice(), TODAY)["reason_code"] == "direct_friend"
    person["linked_user_confirmed_for_recommendation"] = True
    person["linked_user_id"] = None
    assert data.shared_event_for_user("SCU001", notice(), TODAY)["reason_code"] == "direct_friend"


def test_visibility_never_uses_friend_of_friend_to_bypass_direct_denial():
    data = data_with_colleague()
    data.graph["SCU001"].add("SCU005")
    data.graph["SCU005"].add("SCU001")
    assert data.graph["SCU001"] & data.graph["SCU006"]
    assert data.shared_event_for_user("SCU001", notice(direct_friend_attendance="not_allowed"), TODAY) is None
    assert data.shared_event_for_user("SCU004", notice(audience_scope="friends_only"), TODAY) is None
    assert data.shared_event_for_user("SCU001", notice(audience_scope="friends_only"), TODAY) is not None
    assert data.shared_event_for_user("SCU003", notice(), TODAY) is None
    assert data.shared_event_for_user("SCU006", notice(), TODAY) is None


@pytest.mark.parametrize("changes", [
    {"sharing_authorization": "unknown"},
    {"audience_scope": "private"},
    {"direct_friend_attendance": "unknown"},
    {"status": "cancelled"},
    {"status": "finished"},
    {"start_date": "2026-10-27", "end_date": "2026-10-29"},
    {"start_date": "2026-11-02", "end_date": "2026-11-01"},
])
def test_ineligible_notice_is_not_visible(changes):
    data = data_with_colleague()
    assert data.shared_event_for_user("SCU001", notice(**changes), TODAY) is None


def test_expiration_includes_today_and_sorting_is_deterministic():
    data = data_with_colleague()
    today_end = notice(id="DSE-TODAY", end_date="2026-10-30")
    next_end = notice(id="DSE-NEXT", end_date="2026-10-31")
    unrelated = notice(id="DSE-DIRECT", related_user_id=None, related_role=None)
    items = data.shared_event_recommendations("SCU001", [next_end, unrelated, today_end], TODAY)
    ids = [item["notice"]["id"] for item in items]
    assert ids.index("DSE-TODAY") < ids.index("DSE-NEXT") < ids.index("DSE-DIRECT")
    assert data.shared_event_for_user("SCU001", today_end, TODAY) is not None
    assert data.shared_event_for_user("SCU001", today_end, date(2026, 10, 31)) is None


def test_only_confirmed_owned_occurrence_is_hidden_from_recommendations():
    data = data_with_colleague()
    item = notice(shared_occurrence_id="O-TEST")
    data.dataset["private_events"].append({
        "id": "TEST-PRIVATE", "owner_user_id": "SCU001", "status": "scheduled",
        "shared_occurrence_id": "O-TEST",
    })
    assert data.shared_event_for_user("SCU001", item, TODAY) is not None
    assert item["id"] not in {x["notice"]["id"] for x in data.shared_event_recommendations("SCU001", [item], TODAY)}
    data.dataset["private_events"][-1]["status"] = "cancelled"
    assert item["id"] in {x["notice"]["id"] for x in data.shared_event_recommendations("SCU001", [item], TODAY)}
    data.dataset["private_events"][-1]["status"] = "scheduled"
    data.dataset["private_events"][-1]["owner_user_id"] = "SCU002"
    assert item["id"] in {x["notice"]["id"] for x in data.shared_event_recommendations("SCU001", [item], TODAY)}
    item["shared_occurrence_id"] = None
    data.dataset["private_events"][-1].update(owner_user_id="SCU001", shared_occurrence_id=None)
    assert item["id"] in {x["notice"]["id"] for x in data.shared_event_recommendations("SCU001", [item], TODAY)}


@pytest.fixture
def client(tmp_path):
    from gyeongjosa_ai.integration_api import get_shared_store, shared_today
    from gyeongjosa_ai.shared_events_store import SharedEventsStore

    store = SharedEventsStore(tmp_path / "shared.sqlite3")
    app.dependency_overrides[get_shared_store] = lambda: store
    app.dependency_overrides[shared_today] = lambda: TODAY
    try:
        with TestClient(app) as client:
            yield client, store
    finally:
        app.dependency_overrides.clear()


def headers(user_id):
    return {"X-Demo-User-Id": user_id}


def payload(**changes):
    item = {
        "category": "결혼",
        "title": "한소민의 가상 결혼식",
        "start_date": "2026-11-14",
        "end_date": "2026-11-14",
        "region": "서울",
        "venue": None,
        "audience_scope": "friends_and_friends_of_friends",
        "sharing_authorization": "confirmed",
        "direct_friend_attendance": "allowed",
        "friend_of_friend_attendance": "allowed",
        "publisher_name_visible": True,
        "related_role": "subject",
        "related_user_recommendation_allowed": True,
    }
    item.update(changes)
    return item


def test_share_recommend_revoke_and_persist(client):
    client, store = client
    response = client.post("/api/shared-events", headers=headers("SCU006"), json=payload())
    assert response.status_code == 201, response.text
    event_id = response.json()["id"]
    assert event_id.startswith("DSE-")
    for user_id, reason in (("SCU001", "confirmed_colleague"), ("SCU004", "friend_of_friend")):
        result = client.get("/api/shared-events/recommendations", headers=headers(user_id))
        assert result.status_code == 200
        item = next(item for item in result.json()["items"] if item["id"] == event_id)
        assert item["reason_code"] == reason
        assert "publisher_user_id" not in item and "related_user_id" not in item
        assert client.get(f"/api/shared-events/{event_id}", headers=headers(user_id)).status_code == 200
    assert client.get(f"/api/shared-events/{event_id}", headers=headers("SCU003")).status_code == 404
    assert client.patch(f"/api/shared-events/{event_id}", headers=headers("SCU001"), json={"audience_scope": "private"}).status_code == 404
    assert client.patch(f"/api/shared-events/{event_id}", headers=headers("SCU006"), json={"audience_scope": "private"}).status_code == 200
    assert client.get(f"/api/shared-events/{event_id}", headers=headers("SCU001")).status_code == 404
    assert event_id not in {item["id"] for item in client.get("/api/shared-events/recommendations", headers=headers("SCU001")).json()["items"]}
    mine = client.get("/api/shared-events/mine", headers=headers("SCU006")).json()["items"]
    assert next(item for item in mine if item["id"] == event_id)["audience_scope"] == "private"
    from gyeongjosa_ai.shared_events_store import SharedEventsStore
    assert SharedEventsStore(store.path).get(event_id)["audience_scope"] == "private"


@pytest.mark.parametrize("changes", [
    {"title": " "},
    {"start_date": "2026-02-30"},
    {"start_date": "2026-11-15", "end_date": "2026-11-14"},
    {"sharing_authorization": "unknown"},
    {"publisher_user_id": "SCU001"},
    {"related_user_id": "SCU001"},
    {"related_role": "mourner"},
    {"related_role": None, "related_user_recommendation_allowed": True},
])
def test_invalid_share_is_rejected_without_saving(client, changes):
    client, store = client
    assert client.post("/api/shared-events", headers=headers("SCU006"), json=payload(**changes)).status_code == 422
    assert store.list_all() == []


def test_private_default_and_no_account(client):
    client, _ = client
    assert client.get("/api/shared-events/recommendations").status_code == 401
    assert client.get("/api/shared-events/recommendations", headers=headers("UNKNOWN")).status_code == 401
    minimal = {"category": "생일", "title": "가상 생일", "start_date": "2026-11-14", "end_date": "2026-11-14"}
    response = client.post("/api/shared-events", headers=headers("SCU006"), json=minimal)
    assert response.status_code == 201
    event_id = response.json()["id"]
    assert client.get(f"/api/shared-events/{event_id}", headers=headers("SCU001")).status_code == 404
    assert client.get(f"/api/shared-events/{event_id}", headers=headers("SCU006")).status_code == 200


def test_legacy_notice_responses_hide_publisher_ids(client):
    client, _ = client
    responses = [
        client.get("/api/notices", headers=headers("U001")).json()["items"],
        client.get("/api/users/U001/notices").json()["notices"],
        [client.get("/api/notices/N002", headers=headers("U001")).json()["notice"]],
    ]
    for items in responses:
        hidden = next(item for item in items if item["notice"]["id"] == "N002")
        assert hidden["publisher_name"] is None
        assert "publisher_user_id" not in hidden["notice"]
