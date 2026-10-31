"""시연·근거 자료의 단일 SQLite 원천을 읽고 쓴다.

예전 JSON 파일은 data/json_backup/에 보관만 하고 실행 중에는 읽지 않는다.
각 자료(dataset)는 최상위 필드 순서를 그대로 보존한다.
객체 목록 필드는 행 단위(dataset_records)로, 나머지 값은 필드 단위(dataset_fields)로 저장한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_DB = Path(os.environ.get("GYEONGJOSA_SEED_DB", str(ROOT / "data" / "gyeongjosa_seed.sqlite3")))
BACKUP_DIR = ROOT / "data" / "json_backup"
# 자료 이름 = 예전 JSON 파일 이름(확장자 제외)
DATASETS = (
    "original_demo", "demo", "scenario_fixtures", "designated_notices",
    "v4_special_fixtures", "v4_chat_scenarios", "kim_scenario_cases", "scenario_cases",
    "knowledge_base", "legal_rules", "person_policy_profiles", "consumer_price_index",
)
ROOT_LIST = "$"

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    name TEXT PRIMARY KEY,
    root_type TEXT NOT NULL CHECK (root_type IN ('object', 'array'))
);
CREATE TABLE IF NOT EXISTS dataset_fields (
    dataset TEXT NOT NULL REFERENCES datasets(name) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    field TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('value', 'records')),
    value_json TEXT,
    PRIMARY KEY (dataset, field)
);
CREATE TABLE IF NOT EXISTS dataset_records (
    dataset TEXT NOT NULL REFERENCES datasets(name) ON DELETE CASCADE,
    collection TEXT NOT NULL,
    position INTEGER NOT NULL,
    record_id TEXT,
    owner_user_id TEXT,
    record_json TEXT NOT NULL,
    PRIMARY KEY (dataset, collection, position)
);
CREATE INDEX IF NOT EXISTS dataset_records_id ON dataset_records (dataset, collection, record_id);
CREATE INDEX IF NOT EXISTS dataset_records_owner ON dataset_records (dataset, collection, owner_user_id);
"""


class SeedDataMissing(RuntimeError):
    """시드 DB나 자료가 없을 때 발생한다."""


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _is_records(value):
    return isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value)


def _connect(path, readonly):
    path = Path(path)
    if readonly:
        if not path.exists():
            raise SeedDataMissing(f"시드 DB가 없습니다: {path} (python -m gyeongjosa_ai.seed_db --rebuild)")
        db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=15)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=15)
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
    return db


def has(name, path=None):
    """자료가 시드 DB에 있는지 확인한다."""
    path = Path(path or SEED_DB)
    if not path.exists():
        return False
    with closing(_connect(path, readonly=True)) as db:
        return db.execute("SELECT 1 FROM datasets WHERE name = ?", (name,)).fetchone() is not None


def load(name, path=None):
    """저장된 자료를 예전 JSON과 같은 구조(필드 순서 포함)로 복원한다."""
    with closing(_connect(path or SEED_DB, readonly=True)) as db:
        root = db.execute("SELECT root_type FROM datasets WHERE name = ?", (name,)).fetchone()
        if root is None:
            raise SeedDataMissing(f"시드 DB에 '{name}' 자료가 없습니다.")
        records = {}
        for collection, record_json in db.execute(
            "SELECT collection, record_json FROM dataset_records WHERE dataset = ? ORDER BY collection, position", (name,)
        ):
            records.setdefault(collection, []).append(json.loads(record_json))
        if root[0] == "array":
            return records.get(ROOT_LIST, [])
        result = {}
        for field, kind, value_json in db.execute(
            "SELECT field, kind, value_json FROM dataset_fields WHERE dataset = ? ORDER BY position", (name,)
        ):
            result[field] = records.get(field, []) if kind == "records" else json.loads(value_json)
        return result


def save(name, document, path=None):
    """자료 하나를 하나의 트랜잭션으로 통째로 교체한다."""
    if not isinstance(document, (dict, list)):
        raise TypeError("자료는 객체 또는 목록이어야 합니다.")
    with closing(_connect(path or SEED_DB, readonly=False)) as db, db:
        db.execute("DELETE FROM datasets WHERE name = ?", (name,))
        db.execute("INSERT INTO datasets VALUES (?, ?)", (name, "array" if isinstance(document, list) else "object"))
        fields = {ROOT_LIST: document} if isinstance(document, list) else document
        for position, (field, value) in enumerate(fields.items()):
            records = _is_records(value)
            if isinstance(document, dict):
                db.execute("INSERT INTO dataset_fields VALUES (?, ?, ?, ?, ?)",
                           (name, position, field, "records" if records else "value", None if records else _encode(value)))
            if not records:
                continue
            db.executemany("INSERT INTO dataset_records VALUES (?, ?, ?, ?, ?, ?)", [
                (name, field, index, None if row.get("id") is None else str(row["id"]),
                 row.get("owner_user_id") or row.get("publisher_user_id"), _encode(row))
                for index, row in enumerate(value)
            ])


def rebuild_from_backup(path=None, backup_dir=None):
    """보관된 JSON으로 시드 DB를 다시 만든다. (최초 이전·복구용)"""
    target = Path(path or SEED_DB)
    source = Path(backup_dir or BACKUP_DIR)
    if target.exists():
        target.unlink()
    for name in DATASETS:
        save(name, json.loads((source / f"{name}.json").read_text(encoding="utf-8-sig")), target)
    with closing(sqlite3.connect(target)) as db:
        db.execute("VACUUM")
    return target


def main():
    parser = argparse.ArgumentParser(description="시연 시드 SQLite 관리")
    parser.add_argument("--rebuild", action="store_true", help="data/json_backup의 JSON으로 시드 DB를 다시 만든다")
    args = parser.parse_args()
    if not args.rebuild:
        parser.error("--rebuild를 명시하세요. 기존 시드 DB를 덮어씁니다.")
    print(f"시드 DB 생성 완료: {rebuild_from_backup()}")


if __name__ == "__main__":
    main()
