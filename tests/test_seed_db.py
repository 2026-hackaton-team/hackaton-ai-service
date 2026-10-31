"""SQLite 시드가 보관된 JSON과 같은 자료를 돌려주는지 확인한다."""

import json

import pytest

from gyeongjosa_ai import seed_db


@pytest.mark.parametrize("name", seed_db.DATASETS)
def test_seed_matches_json_backup_including_field_order(name):
    backup = json.loads((seed_db.BACKUP_DIR / f"{name}.json").read_text(encoding="utf-8-sig"))
    stored = seed_db.load(name)
    assert stored == backup
    assert json.dumps(stored, ensure_ascii=False) == json.dumps(backup, ensure_ascii=False)


def test_save_replaces_a_dataset_atomically_and_keeps_others(tmp_path):
    seed = tmp_path / "seed.sqlite3"
    seed_db.save("notices", [{"id": "A", "publisher_user_id": "U1"}, {"id": "B"}], seed)
    seed_db.save("doc", {"version": 1, "rows": [{"id": 1, "owner_user_id": "U1"}], "empty": [], "tags": ["x"]}, seed)
    seed_db.save("doc", {"version": 2, "rows": []}, seed)
    assert seed_db.load("notices", seed) == [{"id": "A", "publisher_user_id": "U1"}, {"id": "B"}]
    assert seed_db.load("doc", seed) == {"version": 2, "rows": []}
    assert seed_db.has("doc", seed) and not seed_db.has("missing", seed)


def test_missing_seed_reports_how_to_rebuild(tmp_path):
    with pytest.raises(seed_db.SeedDataMissing, match="--rebuild"):
        seed_db.load("demo", tmp_path / "none.sqlite3")
    seed = tmp_path / "seed.sqlite3"
    seed_db.save("other", {}, seed)
    with pytest.raises(seed_db.SeedDataMissing):
        seed_db.load("demo", seed)


def test_runtime_modules_do_not_read_json_backup():
    # seed_db는 복구 명령에서만 백업을 읽고, evaluate는 data/가 아닌 평가 결과 파일을 쓴다.
    allowed = {"seed_db.py", "evaluate.py"}
    for folder in ("app", "gyeongjosa_ai"):
        for source in (seed_db.ROOT / folder).glob("*.py"):
            text = source.read_text(encoding="utf-8")
            assert source.name in allowed or (".json\"" not in text and ".json'" not in text), source.name
