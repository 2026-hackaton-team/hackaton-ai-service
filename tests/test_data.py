"""가상 데이터와 부고 추천의 핵심 경계를 확인한다."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

from gyeongjosa_ai import seed_db
from gyeongjosa_ai.data import DemoData
from gyeongjosa_ai import generate_data as generator
from gyeongjosa_ai.generate_data import generate_dataset


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def original():
    return seed_db.load("original_demo")


@pytest.fixture(scope="module")
def generated(original):
    return generate_dataset(original)


@pytest.fixture(scope="module")
def data(generated):
    return DemoData(generated)


def test_original_copy_matches_source():
    source = ROOT.parent / "data" / "gyeongjosa_demo.json"
    copied = ROOT / "data" / "json_backup" / "original_demo.json"
    # 줄바꿈을 정규화해 윈도와 리눅스에서 같은 원본 내용을 확인한다.
    expected_sha256 = "1f9cee2d3e971013298c7de0ff7dbda11a284e955d3a7208f0228a57cf3f6b5e"
    copied_bytes = copied.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(copied_bytes).hexdigest() == expected_sha256
    if source.exists():
        assert hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).digest() == hashlib.sha256(copied_bytes).digest()


def test_generated_data_is_repeatable_and_does_not_modify_input(original, generated):
    before = copy.deepcopy(original)
    assert generate_dataset(original) == generated
    assert original == before
    assert len(generated["users"]) == len(original["users"]) + 100 + 6


def test_new_accounts_have_expected_contacts_and_events(original, generated):
    new_ids = {scenario["user_id"] for scenario in generated["generated_scenarios"]}
    assert len(new_ids) == 100
    for user_id in new_ids:
        contacts = [person for person in generated["people"] if person["owner_user_id"] == user_id]
        events = [event for event in generated["private_events"] if event["owner_user_id"] == user_id]
        assert 3 <= len(contacts) <= 8
        assert 2 <= len(events) <= 10
    for relation in generated["friendships"][len(original["friendships"]):]:
        if not relation["id"].startswith("SCF"):
            assert relation["user_a_id"] in new_ids and relation["user_b_id"] in new_ids


def test_generated_questions_include_varied_expressions(generated):
    people = {person["id"]: person for person in generated["people"]}
    for mode in ("history", "amount", "attendance", "message"):
        templates = {
            scenario["questions"][mode].replace(people[scenario["person_id"]]["name"], "{이름}")
            for scenario in generated["generated_scenarios"]
        }
        assert len(templates) >= 8


def test_generator_does_not_overwrite_without_explicit_force(tmp_path, monkeypatch, original):
    seed = tmp_path / "seed.sqlite3"
    seed_db.save("original_demo", original, seed)
    seed_db.save("scenario_fixtures", seed_db.load("scenario_fixtures"), seed)
    seed_db.save("demo", {"note": "기존 작업 데이터"}, seed)
    monkeypatch.setattr(seed_db, "SEED_DB", seed)
    monkeypatch.setattr(sys, "argv", ["generate_data"])
    with pytest.raises(SystemExit):
        generator.main()
    assert seed_db.load("demo") == {"note": "기존 작업 데이터"}
    monkeypatch.setattr(sys, "argv", ["generate_data", "--force"])
    generator.main()
    assert len(seed_db.load("demo")["users"]) == 117


def test_generated_references_and_ids_are_consistent(generated):
    for name in ("users", "friendships", "people", "private_events", "transactions", "shared_notices"):
        identifiers = [item["id"] for item in generated[name]]
        assert len(identifiers) == len(set(identifiers))
    users = {item["id"] for item in generated["users"]}
    people = {item["id"]: item for item in generated["people"]}
    events = {item["id"]: item for item in generated["private_events"]}
    for person in people.values():
        assert person["owner_user_id"] in users
        assert not person["linked_user_id"] or person["linked_user_id"] in users
    for event in events.values():
        assert event["owner_user_id"] in users
        assert people[event["contact_person_id"]]["owner_user_id"] == event["owner_user_id"]
    for transaction in generated["transactions"]:
        event = events[transaction["private_event_id"]]
        assert transaction["owner_user_id"] == event["owner_user_id"]
        assert transaction["contact_person_id"] == event["contact_person_id"]
        assert transaction["amount_krw"] >= 0


def test_recommendations_are_funeral_only_and_preserve_demo_cases(data):
    candidates = data.recommendations("U001")
    assert [item["notice"]["id"] for item in candidates] == ["N001", "N002"]
    assert candidates[0]["mutual_count"] == 3
    assert candidates[0]["score"] == 100.0
    assert all(item["notice"]["category"] == "장례" for item in candidates)
    assert data.notice_for_user("U001", "N003") is None
    assert data.notice_for_user("U001", "N006") is None


def test_missing_interests_are_not_counted_as_zero(data):
    candidate = next(item for item in data.recommendations("U004") if item["notice"]["id"] == "N001")
    assert candidate["mutual_count"] == 4
    assert candidate["score"] == 62.5
    assert candidate["details"]["interest_match"] is None


def test_direct_friends_require_explicit_attendance_permission(generated):
    dataset = copy.deepcopy(generated)
    notice = next(item for item in dataset["shared_notices"] if item["id"] == "N001")
    repository = DemoData(dataset)
    assert repository.notice_for_user("U002", "N001") is None
    notice["direct_friend_attendance"] = "allowed"
    notice["friend_of_friend_attendance"] = "unknown"
    direct = repository.notice_for_user("U002", "N001")
    assert direct is not None and direct["relation_type"] == "direct_friend"
    assert repository.notice_for_user("U001", "N001") is None
    notice["direct_friend_attendance"] = "not_allowed"
    assert repository.notice_for_user("U002", "N001") is None


def test_generated_notices_have_explicit_direct_attendance(generated, original):
    original_count = len(original["shared_notices"])
    assert all(item["direct_friend_attendance"] == "unknown" for item in generated["shared_notices"][:original_count])
    assert any(item["direct_friend_attendance"] == "allowed" for item in generated["shared_notices"][original_count:])


def test_notice_details_are_fictional_and_optional_fields_stay_unknown(data):
    first = data.notice_for_user("U001", "N001")
    assert first["publisher_name"] == "이수빈"
    assert "가상" in first["notice"]["venue"] and "가상" in first["notice"]["address"]
    assert first["notice"]["room"] and first["notice"]["visiting_hours"]
    second = data.notice_for_user("U001", "N002")
    assert not second["notice"].get("venue") and second["publisher_name"] is None


def test_added_account_can_see_both_permitted_relationship_types(data):
    candidates = data.recommendations("U012")
    assert {item["relation_type"] for item in candidates} == {"direct_friend", "friend_of_friend"}
    for item in candidates:
        key = "direct_friend_attendance" if item["relation_type"] == "direct_friend" else "friend_of_friend_attendance"
        assert item["notice"][key] == "allowed"


def test_account_scoped_history_and_zero_vs_missing(data):
    history = data.history("U001", "P001")
    assert [item["id"] for item in history["transactions"]] == ["T001", "T002"]
    assert history["received_total_krw"] == 100000
    assert history["paid_total_krw"] == 50000
    assert data.history("U004", "P001") is None
    dashboard = data.dashboard("U001")
    assert dashboard["received_total_krw"] == 100000
    assert dashboard["paid_total_krw"] == 420000
    assert dashboard["explicit_zero_entry_count"] == 1
    event_without_amount = next(event for event in data.events("U001") if event["id"] == "E007")
    assert event_without_amount["amount_krw"] is None
