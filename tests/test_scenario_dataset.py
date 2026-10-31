"""시나리오 데이터와 기존 가상 시연의 경계를 확인한다."""

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from gyeongjosa_ai.data import DemoData, load_data
from gyeongjosa_ai.generate_data import add_scenario_fixtures, generate_dataset


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LEGACY_DIGEST = "812ee16e77ca5c2b768a668f307bfa4d90605621e3ae2c2cd23b14ef5c9a2f11"


def read_json(name):
    """저장된 가상 데이터 파일을 읽는다."""
    return json.loads((DATA / name).read_text(encoding="utf-8-sig"))


def test_fixture_additions_preserve_the_entire_existing_dataset():
    fixtures = read_json("scenario_fixtures.json")
    dataset = read_json("demo.json")
    restored = copy.deepcopy(dataset)
    for collection in ("users", "friendships", "people", "private_events", "transactions", "shared_notices"):
        added_ids = {item["id"] for item in fixtures[collection]}
        assert len(added_ids) == len(fixtures[collection])
        assert {item["id"] for item in dataset[collection]} >= added_ids
        restored[collection] = [item for item in dataset[collection] if item["id"] not in added_ids]
    restored["metadata"].pop("scenario_fixtures_version")
    encoded = json.dumps(restored, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == LEGACY_DIGEST
    assert generate_dataset(read_json("original_demo.json")) == dataset


def test_fixture_references_and_owner_boundaries():
    fixtures = read_json("scenario_fixtures.json")
    assert len(fixtures["users"]) == 6
    assert len(fixtures["people"]) == 19
    assert len(fixtures["private_events"]) == 32
    assert len(fixtures["transactions"]) == 24
    assert len(fixtures["shared_notices"]) == 12
    assert Counter(event["category"] for event in fixtures["private_events"]) == {
        category: 4 for category in read_json("original_demo.json")["event_categories"]
    }
    assert Counter(transaction["direction"] for transaction in fixtures["transactions"]) == {"paid": 18, "received": 6}
    assert sum(transaction["amount_krw"] == 0 for transaction in fixtures["transactions"]) >= 2
    people = {person["id"]: person for person in fixtures["people"]}
    events = {event["id"]: event for event in fixtures["private_events"]}
    users = {user["id"] for user in fixtures["users"]}
    assert Counter(person["owner_user_id"] for person in people.values()) == {
        user: 4 if user == "SCU001" else 3 for user in users
    }
    assert all(item["user_a_id"] in users and item["user_b_id"] in users for item in fixtures["friendships"])
    assert all(item["publisher_user_id"] in users for item in fixtures["shared_notices"])
    for event in events.values():
        assert event["owner_user_id"] in users
        assert people[event["contact_person_id"]]["owner_user_id"] == event["owner_user_id"]
    for transaction in fixtures["transactions"]:
        event = events[transaction["private_event_id"]]
        assert transaction["owner_user_id"] == event["owner_user_id"]
        assert transaction["contact_person_id"] == event["contact_person_id"]
        assert type(transaction["amount_krw"]) is int and transaction["amount_krw"] >= 0


def test_new_person_history_keeps_direction_and_separates_zero_from_missing():
    data = load_data()
    history = data.history("SCU001", "SCP001")
    assert {item["id"] for item in history["transactions"]} == {"SCT001", "SCT005", "SCT006", "SCT025"}
    assert history["received_total_krw"] == 170000
    assert history["paid_total_krw"] == 100000
    assert data.history("SCU002", "SCP001") is None
    zero = next(event for event in data.events("SCU006") if event["id"] == "SCE007")
    missing = next(event for event in data.events("SCU002") if event["id"] == "SCE032")
    assert zero["amount_krw"] == 0 and zero["transactions"][0]["id"] == "SCT007"
    assert missing["amount_krw"] is None and missing["transactions"] == []


def test_notice_visibility_and_duplicate_names_use_new_fixture_graph():
    data = load_data()
    ids = {item["notice"]["id"] for item in data.recommendations("SCU001")}
    assert {"SCN001", "SCN002"} <= ids
    assert not ids.intersection({"SCN003", "SCN004", "SCN005", "SCN006", "SCN007"})
    notice = data.notice_for_user("SCU001", "SCN001")["notice"]
    candidates = {item["person"]["id"]: item for item in data.matching_people("SCU001", notice)}
    assert set(candidates) == {"SCP001", "SCP002"}
    assert candidates["SCP001"]["affiliation_match"] is True
    assert candidates["SCP002"]["affiliation_match"] is False
    assert all(item["requires_user_confirmation"] for item in candidates.values())


def test_scenario_catalog_contract_and_splits():
    data = read_json("demo.json")
    cases = read_json("scenario_cases.json")
    scenarios = cases["scenarios"]
    assert len(scenarios) == 80
    assert len({item["id"] for item in scenarios}) == 80
    assert Counter(item["primary_group"] for item in scenarios) == {
        "기존 행사": 24, "확장 행사": 16, "특수 상황": 24, "자연어 대화": 16
    }
    assert Counter(item["split"] for item in scenarios) == {"개발용": 60, "평가용": 20}
    assert sum(item["priority"] == "P0" for item in scenarios) == 30
    assert sum(len(item["turns"]) > 1 for item in scenarios) >= 10
    personas = {item["id"] for item in data["users"]}
    identifiers = {item["id"] for name in ("users", "people", "private_events", "transactions", "shared_notices") for item in data[name]}
    split_users = {split: {item["persona_id"] for item in scenarios if item["split"] == split} for split in ("개발용", "평가용")}
    assert split_users["개발용"].isdisjoint(split_users["평가용"])
    for case in scenarios:
        assert case["persona_id"] in personas
        assert case["support_status"] in {"현재 검증 가능", "기능 확장 필요", "정책 결정 필요"}
        assert case["review_status"] == "초안" and case["verification_status"] == "NOT_RUN"
        assert case["title"] and case["initial_state"] and case["turns"]
        assert all(turn["user"] and turn["expected"] for turn in case["turns"])
        assert case["expected"]["behavior"] and case["must_not"]
        references = {identifier for group in case["fixture_refs"].values() for identifier in group}
        assert references <= identifiers
        assert set(case["expected"]["evidence_ids"]) <= references


def test_document_lists_every_scenario_once_and_expected_evidence_is_owned():
    data = load_data()
    cases = read_json("scenario_cases.json")["scenarios"]
    document = (ROOT / "docs" / "SCENARIO_CATALOG.md").read_text(encoding="utf-8")
    records = {item["id"]: item for name in ("people", "private_events", "transactions") for item in data.dataset[name]}
    for case in cases:
        assert document.count(f"| {case['id']} |") == 1
        for identifier in case["expected"]["evidence_ids"]:
            assert records[identifier]["owner_user_id"] == case["persona_id"]


def test_missing_and_zero_are_not_made_equal_by_the_fixture_layer():
    fixtures = read_json("scenario_fixtures.json")
    events_with_transactions = {item["private_event_id"] for item in fixtures["transactions"]}
    assert len({item["id"] for item in fixtures["private_events"]} - events_with_transactions) >= 4
    assert DemoData(read_json("demo.json")).dashboard("SCU006")["explicit_zero_entry_count"] == 2


@pytest.mark.parametrize("fault", ["duplicate", "missing_person", "wrong_owner", "negative_amount", "invalid_status", "invalid_permission"])
def test_invalid_fixture_is_rejected_without_changing_the_original(fault):
    original = read_json("original_demo.json")
    before = copy.deepcopy(original)
    fixtures = read_json("scenario_fixtures.json")
    if fault == "duplicate":
        fixtures["users"][0]["id"] = original["users"][0]["id"]
    elif fault == "missing_person":
        fixtures["private_events"][0]["contact_person_id"] = "SCP999"
    elif fault == "wrong_owner":
        fixtures["transactions"][0]["owner_user_id"] = "SCU002"
    elif fault == "negative_amount":
        fixtures["transactions"][0]["amount_krw"] = -1
    elif fault == "invalid_status":
        fixtures["shared_notices"][0]["status"] = "미확인"
    else:
        fixtures["shared_notices"][0]["sharing_authorization"] = "허용인듯"
    with pytest.raises(ValueError):
        add_scenario_fixtures(original, fixtures)
    assert original == before
