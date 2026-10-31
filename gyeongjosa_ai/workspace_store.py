"""로컬 가상 계정의 인맥·행사·장부를 SQLite에 원자적으로 보관한다."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


SELF_PERSON_ID = "__workspace_self__"


class PersonInput(BaseModel):
    """프런트 인맥 필드와 기존 메모·교류 정보를 보존한다."""

    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    relation: str = Field(default="기타", max_length=80)
    group: str = Field(default="", max_length=100)
    importance: str = Field(default="보통", max_length=30)
    closeness_score: StrictInt | None = Field(default=None, ge=1, le=5)
    lastMet: str = ""
    memo: str = Field(default="", max_length=2000)
    interactions: list[dict] = Field(default_factory=list, max_length=300)


class EventInput(BaseModel):
    """장부 거래에서 참조하는 행사 정보를 검증한다."""

    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=128)
    personId: str = Field(default="", max_length=128)
    title: str = Field(min_length=1, max_length=150)
    type: str = Field(min_length=1, max_length=60)
    date: date
    time: str = ""
    location: str = Field(default="", max_length=300)
    attendance: str = ""
    reminderDays: int = Field(default=3, ge=0, le=365)
    memo: str = Field(default="", max_length=2000)


class RecordInput(BaseModel):
    """거래의 금액·방향·소유 인물 연결을 검증한다."""

    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=128)
    personId: str = Field(min_length=1, max_length=128)
    eventId: str = Field(default="", max_length=128)
    type: str = Field(min_length=1, max_length=60)
    date: date
    direction: Literal["보낸 마음", "받은 마음"]
    amount: int = Field(ge=1, le=1000000000)
    memo: str = Field(default="", max_length=2000)


class WorkspaceInput(BaseModel):
    """전체 작업 공간을 버전 조건과 함께 교체하는 단일 요청이다."""

    revision: int = Field(ge=0)
    people: list[PersonInput] = Field(default_factory=list, max_length=3000)
    events: list[EventInput] = Field(default_factory=list, max_length=6000)
    records: list[RecordInput] = Field(default_factory=list, max_length=20000)

    @model_validator(mode="after")
    def check_links(self):
        """ID 중복, 잘못된 인물 연결, 다른 인물 행사의 거래 연결을 거부한다."""
        for rows in (self.people, self.events, self.records):
            ids = [item.id for item in rows]
            if len(set(ids)) != len(ids):
                raise ValueError("중복된 ID가 있습니다.")
        people = {item.id for item in self.people}
        if SELF_PERSON_ID in people:
            raise ValueError("예약된 인물 ID입니다.")
        events = {item.id: item.personId for item in self.events}
        if any(item.personId not in people and not (
            item.personId == "" and (item.model_extra or {}).get("owner") == "me"
        ) for item in self.events):
            raise ValueError("연결된 인맥이 없는 일정이 있습니다.")
        for item in self.records:
            if item.personId not in people:
                raise ValueError("연결된 인맥이 없는 금액 기록이 있습니다.")
            if item.eventId and events.get(item.eventId) != item.personId:
                raise ValueError("금액 기록의 행사와 인물 연결이 일치하지 않습니다.")
        return self


def _db_path():
    """테스트와 로컬 개발에서 환경변수로 저장소를 분리한다."""
    default = Path(__file__).resolve().parents[1] / "data" / "demo_workspace.sqlite3"
    return Path(os.getenv("GYEONGJOSA_WORKSPACE_DB", str(default)))


@contextmanager
def _connect():
    """외래 키 검사를 활성화하고 모든 연결을 사용 후 닫는다."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS workspace_versions (
                user_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspace_people (
                user_id TEXT NOT NULL,
                id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (user_id, id)
            );
            CREATE TABLE IF NOT EXISTS workspace_events (
                user_id TEXT NOT NULL,
                id TEXT NOT NULL,
                person_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (user_id, id),
                FOREIGN KEY (user_id, person_id)
                    REFERENCES workspace_people(user_id, id)
            );
            CREATE TABLE IF NOT EXISTS workspace_records (
                user_id TEXT NOT NULL,
                id TEXT NOT NULL,
                person_id TEXT NOT NULL,
                event_id TEXT,
                direction TEXT NOT NULL,
                amount_krw INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (user_id, id),
                FOREIGN KEY (user_id, person_id)
                    REFERENCES workspace_people(user_id, id),
                FOREIGN KEY (user_id, event_id)
                    REFERENCES workspace_events(user_id, id),
                CHECK (amount_krw > 0)
            );
            CREATE INDEX IF NOT EXISTS ix_workspace_record_person
                ON workspace_records(user_id, person_id);
        """)
        db.commit()
        yield db
    finally:
        db.close()


def load_workspace(user_id: str):
    """현재 계정의 저장 데이터와 버전을 함께 반환한다."""
    with _connect() as db:
        version = db.execute(
            "SELECT revision FROM workspace_versions WHERE user_id=?", (user_id,)
        ).fetchone()
        result = {"schemaVersion": 2, "revision": version["revision"] if version else 0,
                  "initialized": version is not None}
        for table, key in (("workspace_people", "people"), ("workspace_events", "events"),
                           ("workspace_records", "records")):
            rows = db.execute(
                f"SELECT payload FROM {table} WHERE user_id=? ORDER BY rowid", (user_id,)
            ).fetchall()
            result[key] = [json.loads(row["payload"]) for row in rows
                           if key != "people" or json.loads(row["payload"])["id"] != SELF_PERSON_ID]
    return result


def preview_workspace(user_id: str, snapshot: WorkspaceInput):
    """기존 서버 데이터가 있으면 덮어쓰기 전에 충돌을 알린다."""
    current = load_workspace(user_id)
    if current["revision"] != snapshot.revision:
        raise HTTPException(409, "서버 데이터가 변경됐습니다. 다시 불러오세요.")
    return {"revision": current["revision"], "initialized": current["initialized"],
            "peopleCount": len(snapshot.people), "eventCount": len(snapshot.events),
            "recordCount": len(snapshot.records)}


def save_workspace(user_id: str, snapshot: WorkspaceInput):
    """외래 키 순서를 지켜 단일 트랜잭션으로 전체 데이터를 교체한다."""
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute(
            "SELECT revision FROM workspace_versions WHERE user_id=?", (user_id,)
        ).fetchone()
        current_revision = version["revision"] if version else 0
        if current_revision != snapshot.revision:
            raise HTTPException(409, "서버 데이터가 변경됐습니다. 다시 불러오세요.")
        for table in ("workspace_records", "workspace_events", "workspace_people"):
            db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        for person in snapshot.people:
            db.execute("INSERT INTO workspace_people VALUES (?,?,?)",
                       (user_id, person.id, person.model_dump_json()))
        if any(event.personId == "" for event in snapshot.events):
            db.execute("INSERT INTO workspace_people VALUES (?,?,?)",
                       (user_id, SELF_PERSON_ID, json.dumps({"id": SELF_PERSON_ID, "name": "본인 행사"}, ensure_ascii=False)))
        for event in snapshot.events:
            db.execute("INSERT INTO workspace_events VALUES (?,?,?,?)",
                       (user_id, event.id, event.personId or SELF_PERSON_ID, event.model_dump_json()))
        for record in snapshot.records:
            db.execute("INSERT INTO workspace_records VALUES (?,?,?,?,?,?,?)",
                       (user_id, record.id, record.personId, record.eventId or None,
                        record.direction, record.amount, record.model_dump_json()))
        next_revision = current_revision + 1
        db.execute("INSERT INTO workspace_versions(user_id,revision) VALUES (?,?) "
                   "ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision",
                   (user_id, next_revision))
        db.commit()
    return {"schemaVersion": 2, "revision": next_revision, "initialized": True,
            "people": [person.model_dump(mode="json") for person in snapshot.people],
            "events": [event.model_dump(mode="json") for event in snapshot.events],
            "records": [record.model_dump(mode="json") for record in snapshot.records]}
