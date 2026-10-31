"""Local demo API: explicit account selection and durable per-account conversations.

This is NOT production authentication. Do not expose this application publicly.
"""
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from .dependencies import get_service
from .data import public_legacy_candidate
from .shared_events_store import SharedEventsStore
from .relationship_priority import IMPORTANCE_OPTIONS, PriorityStore
from .event_parser import parse_event_text
from .workspace_store import WorkspaceInput, load_workspace, preview_workspace, save_workspace
from .service import ChatService
from .workspace_adapter import data_for_chat

router = APIRouter(prefix="/api")
_DB = Path(os.environ.get("GYEONGJOSA_DEMO_DB", str(Path(__file__).resolve().parents[1] / "data" / "demo_conversations.sqlite3")))
_LOCK = threading.RLock()

@contextmanager
def _connect():
    """대화 저장소의 트랜잭션을 마친 뒤 연결을 닫는다."""
    _DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(_DB, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            request_id TEXT, role TEXT NOT NULL, body TEXT NOT NULL,
            payload TEXT, created_at TEXT NOT NULL,
            UNIQUE(conversation_id, request_id)
        );
        CREATE INDEX IF NOT EXISTS ix_conversations_user ON conversations(user_id, updated_at);
        CREATE INDEX IF NOT EXISTS ix_messages_conversation ON messages(conversation_id, created_at);
        """)
        db.commit()
        with db:
            yield db
    finally:
        db.close()

def _now():
    return datetime.now(timezone.utc).isoformat()

def _user(x_demo_user_id: str = Header(default=""), service=Depends(get_service)):
    if x_demo_user_id not in service.data.users:
        if not re.fullmatch(r"LOCAL_[A-Z0-9_]{4,20}", x_demo_user_id):
            raise HTTPException(401, "로그인 계정의 서버 사용자 ID가 필요합니다.")
        # 시연용 신규 로그인은 고정 사용자 ID로 빈 개인 작업공간을 사용한다.
        username = x_demo_user_id.removeprefix("LOCAL_").lower()
        user = {
            "id": x_demo_user_id, "name": username, "login_id": username,
            "demo_account": True, "fictional_affiliation": "마음결 시연 계정",
            "preferred_region": "서울", "preferred_event_types": [],
        }
        service.data.users[x_demo_user_id] = user
        service.data.dataset["users"].append(user)
    return x_demo_user_id

def _conversation(db, cid, uid):
    result = db.execute("SELECT * FROM conversations WHERE id=? AND user_id=?", (cid, uid)).fetchone()
    if result is None:
        raise HTTPException(404, "대화를 찾을 수 없습니다.")
    return result

class MessageInput(BaseModel):
    requestId: str = Field(min_length=6, max_length=128)
    text: str = Field(min_length=1, max_length=2000)
    selection: dict | None = None


class SharedEventInput(BaseModel):
    """가상 공유 소식의 작성 항목을 검증한다."""

    model_config = ConfigDict(extra="forbid")
    category: Literal["결혼", "장례", "백일", "돌", "생일", "환갑", "칠순", "팔순"]
    title: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    region: str | None = Field(default=None, max_length=100)
    venue: str | None = Field(default=None, max_length=200)
    audience_scope: Literal["private", "friends_only", "friends_and_friends_of_friends", "designated"] = "private"
    recipient_user_ids: list[str] = Field(default_factory=list, max_length=30)
    recipient_group: Literal["family", "custom"] | None = None
    sharing_authorization: Literal["confirmed", "unknown"] = "unknown"
    direct_friend_attendance: Literal["allowed", "not_allowed", "unknown"] = "unknown"
    friend_of_friend_attendance: Literal["allowed", "not_allowed", "unknown"] = "unknown"
    publisher_name_visible: StrictBool = False
    related_role: Literal["subject", "mourner"] | None = None
    related_user_recommendation_allowed: StrictBool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        """공백만 입력한 제목은 허용하지 않는다."""
        value = value.strip()
        if not value:
            raise ValueError("제목을 입력해 주세요.")
        return value

    @field_validator("region", "venue")
    @classmethod
    def normalize_optional_text(cls, value):
        """빈 선택 항목은 미기록으로 저장한다."""
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_scope_and_role(self):
        """기간과 공유 확인 및 관련 인물의 역할을 검사한다."""
        if self.start_date > self.end_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        if self.audience_scope != "private" and self.sharing_authorization != "confirmed":
            raise ValueError("공유 권한을 확인해 주세요.")
        if self.audience_scope == "designated" and not self.recipient_user_ids:
            raise ValueError("소식을 받을 사람을 한 명 이상 지정해 주세요.")
        if self.audience_scope != "designated" and (self.recipient_user_ids or self.recipient_group):
            raise ValueError("받는 사람 지정은 '지정한 사람에게' 공유할 때만 사용할 수 있습니다.")
        if self.related_role == "subject" and self.category == "장례":
            raise ValueError("장례에서는 본인 상주 여부를 선택해 주세요.")
        if self.related_role == "mourner" and self.category != "장례":
            raise ValueError("상주 역할은 장례에만 선택할 수 있습니다.")
        if self.related_role is None and self.related_user_recommendation_allowed:
            raise ValueError("추천에 사용할 관련 인물의 역할을 선택해 주세요.")
        return self


class SharedEventRevoke(BaseModel):
    """작성자가 자신의 공유를 철회하는 입력이다."""

    model_config = ConfigDict(extra="forbid")
    audience_scope: Literal["private"]


def get_shared_store():
    """별도 가상 공유 소식 저장소를 반환한다."""
    default = Path(__file__).resolve().parents[1] / "data" / "demo_shared_events.sqlite3"
    store = SharedEventsStore(os.environ.get("GYEONGJOSA_SHARED_EVENTS_DB", str(default)))
    store.seed_test_events()
    return store


def shared_today():
    """서울 기준 현재 날짜를 반환한다."""
    return datetime.now(timezone(timedelta(hours=9))).date()


def public_shared_event(candidate, detail=False):
    """수신자에게 허용된 공유 소식 필드만 반환한다."""
    notice = candidate["notice"]
    fields = ("id", "category", "title", "start_date", "end_date", "region")
    result = {key: notice.get(key) for key in fields}
    result.update(publisher_name=candidate["publisher_name"], reason_code=candidate["reason_code"])
    if detail:
        for key in ("venue", "address", "room", "visiting_hours"):
            result[key] = notice.get(key)
        mourner = notice.get("mourner")
        result["mourner"] = ({key: mourner.get(key) for key in ("name", "affiliation", "deceased_relation")}
                              if isinstance(mourner, dict) else None)
    return result


def own_shared_event(notice):
    """작성자 화면에 필요한 소식과 공개 상태만 반환한다."""
    fields = ("id", "category", "title", "start_date", "end_date", "region", "venue", "status",
              "audience_scope", "sharing_authorization", "direct_friend_attendance", "friend_of_friend_attendance",
              "publisher_name_visible", "related_role", "related_user_recommendation_allowed", "recipient_user_ids",
              "recipient_group", "created_at", "updated_at")
    return {key: notice.get(key) for key in fields}

class LoginIdentityInput(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9_]{4,20}$")


@router.post("/demo/accounts/resolve")
def resolve_login_identity(account: LoginIdentityInput, service=Depends(get_service)):
    """일반 로그인 아이디를 서버의 합성 사용자 ID에 연결한다."""
    for user in service.data.users.values():
        if user.get("login_id", "").lower() == account.username:
            return {"user_id": user["id"]}
    return {"user_id": "LOCAL_" + account.username.upper()}


@router.get("/demo/users")
def demo_users(service=Depends(get_service)):
    return {"items": service.data.list_users(), "referenceDate": "2026-10-30", "demo": True}

@router.get("/demo/v4-scenarios")
def chat_scenarios(user_id: str = Depends(_user)):
    """현재 가상 계정에서 접근할 수 있는 합성 시연 질문만 제공한다."""
    if user_id != "U001":
        return {"items": []}
    from .v4_chat import SCENARIOS
    return {"items": [
        {"id": identifier, "title": scenario["name"], "question": scenario["example_question"],
         "category": scenario.get("category", "safety")}
        for identifier, scenario in SCENARIOS.items()
    ]}


@router.get("/demo/kim-scenarios")
def kim_scenarios(user_id: str = Depends(_user)):
    """전용 합성 계정에서만 20개 실제 상담 검증 질문을 공개한다."""
    from .scenario_lab import USER_ID, catalog
    if user_id != USER_ID:
        raise HTTPException(403, "김시나리오 계정에서만 사용할 수 있습니다.")
    return catalog()


@router.get("/workspace")
def workspace(user_id: str = Depends(_user), service=Depends(get_service)):
    return {
        "schemaVersion": 1,
        "people": service.data.people(user_id),
        "events": service.data.events(user_id),
        "dashboard": service.data.dashboard(user_id),
        "source": "rag-demo-json-read-only"
    }

@router.get("/workspace/personal")
def personal_workspace(user_id: str = Depends(_user)):
    """현재 가상 계정이 서버에 저장한 인맥·일정·장부를 반환한다."""
    return load_workspace(user_id)


@router.post("/workspace/migrations/preview")
def workspace_migration_preview(data: WorkspaceInput, user_id: str = Depends(_user)):
    """로컬 기록 이전 전 참조 관계와 서버 변경 버전을 검증한다."""
    return preview_workspace(user_id, data)


@router.put("/workspace/personal")
def save_personal_workspace(data: WorkspaceInput, user_id: str = Depends(_user)):
    """현재 계정의 저장 데이터만 버전 검증 후 원자적으로 교체한다."""
    return save_workspace(user_id, data)


class RelationshipPriorityInput(BaseModel):
    """다른 계정에 대해 내가 기록하는 중요도. 상대에게는 공개되지 않는다."""

    model_config = ConfigDict(extra="forbid")
    importance: Literal[IMPORTANCE_OPTIONS] = "보통"
    special: StrictBool = False
    relation: str | None = Field(default=None, max_length=20)


class EventParseInput(BaseModel):
    """한 줄로 적은 경조사 문장."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=300)
    today: date | None = None


def get_priority_store():
    """관계 중요도 저장소를 반환한다."""
    default = Path(__file__).resolve().parents[1] / "data" / "demo_relationship_priorities.sqlite3"
    return PriorityStore(os.environ.get("GYEONGJOSA_PRIORITY_DB", str(default)))


@router.get("/notices")
def notices(user_id: str = Depends(_user), service=Depends(get_service), priorities=Depends(get_priority_store)):
    items = service.data.recommendations(user_id, priorities.list(user_id))
    return {"items": [public_legacy_candidate(item) for item in items], "demo": True}


@router.get("/relationship-priorities")
def list_relationship_priorities(user_id: str = Depends(_user), service=Depends(get_service), store=Depends(get_priority_store)):
    """현재 프로필이 다른 계정에 대해 기록한 중요도를 반환한다."""
    items = store.list(user_id)
    return {"items": [{"target_user_id": target, "target_name": service.data.users.get(target, {}).get("name"), **value}
                      for target, value in items.items()]}


@router.put("/relationship-priorities/{target_user_id}")
def set_relationship_priority(target_user_id: str, data: RelationshipPriorityInput, user_id: str = Depends(_user),
                              service=Depends(get_service), store=Depends(get_priority_store)):
    """다른 계정에 대한 중요도를 기록한다. 순서에만 쓰이고 공유 범위는 바꾸지 않는다."""
    if target_user_id == user_id or target_user_id not in service.data.users:
        raise HTTPException(404, "중요도를 기록할 수 없는 계정입니다.")
    return {"target_user_id": target_user_id, **store.set(user_id, target_user_id, data.importance, data.special, data.relation)}


@router.delete("/relationship-priorities/{target_user_id}", status_code=204)
def delete_relationship_priority(target_user_id: str, user_id: str = Depends(_user), store=Depends(get_priority_store)):
    """기록한 중요도를 지운다."""
    store.delete(user_id, target_user_id)


@router.post("/events/parse")
def parse_event(data: EventParseInput):
    """한 줄 문장을 일정 입력값으로 제안한다. 저장하지 않으며 사용자가 확인한 뒤 저장한다."""
    return parse_event_text(data.text, data.today or shared_today())

@router.get("/notices/{notice_id}")
def notice(notice_id: str, user_id: str = Depends(_user), service=Depends(get_service)):
    item = service.data.notice_for_user(user_id, notice_id)
    if item is None:
        raise HTTPException(404, "공유 허용된 부고가 아닙니다.")
    matches = service.data.matching_people(user_id, item["notice"])
    for match in matches:
        match["person"] = {key: match["person"][key] for key in ("id", "name", "relationship", "fictional_affiliation")}
    return {"notice": public_legacy_candidate(item), "identityCandidates": matches}


@router.get("/shared-events/recommendations")
def shared_event_recommendations(user_id: str = Depends(_user), service=Depends(get_service),
                                 store=Depends(get_shared_store), today=Depends(shared_today)):
    """허용된 가상 공유 경조사를 현재 날짜 기준으로 추천한다."""
    items = service.data.shared_event_recommendations(user_id, store.list_all(), today)
    return {"demo": True, "reference_date": today.isoformat(),
            "items": [public_shared_event(item) for item in items]}


@router.get("/shared-events/mine")
def my_shared_events(user_id: str = Depends(_user), store=Depends(get_shared_store)):
    """현재 가상 계정이 새로 등록한 공유 소식을 반환한다."""
    return {"demo": True, "items": [own_shared_event(item) for item in store.list_all()
                                     if item["publisher_user_id"] == user_id]}


@router.get("/shared-events/{event_id}")
def shared_event_detail(event_id: str, user_id: str = Depends(_user), service=Depends(get_service),
                        store=Depends(get_shared_store), today=Depends(shared_today)):
    """소식의 소유자 또는 허용된 수신자에게 상세를 반환한다."""
    item = store.get(event_id)
    if item is not None and item["publisher_user_id"] == user_id:
        return {"demo": True, "item": own_shared_event(item)}
    if item is None:
        item = next((entry for entry in service.data.dataset["shared_notices"] if entry["id"] == event_id), None)
    candidate = service.data.shared_event_for_user(user_id, item, today) if item else None
    if candidate is None:
        raise HTTPException(404, "조회할 수 없는 소식입니다.")
    return {"demo": True, "item": public_shared_event(candidate, detail=True)}


@router.post("/shared-events", status_code=201)
def create_shared_event(data: SharedEventInput, user_id: str = Depends(_user), store=Depends(get_shared_store),
                        service=Depends(get_service)):
    """현재 가상 계정의 공유 소식을 저장한다."""
    if any(uid == user_id or uid not in service.data.users for uid in data.recipient_user_ids):
        raise HTTPException(422, "받는 사람을 다시 확인해 주세요.")
    item = store.create(user_id, data.model_dump(mode="json"))
    return {"demo": True, **own_shared_event(item)}


@router.patch("/shared-events/{event_id}")
def revoke_shared_event(event_id: str, data: SharedEventRevoke, user_id: str = Depends(_user),
                        store=Depends(get_shared_store)):
    """작성자가 등록한 소식의 공유를 철회한다."""
    item = store.revoke(event_id, user_id)
    if item is None:
        raise HTTPException(404, "수정할 수 없는 소식입니다.")
    return {"demo": True, "item": own_shared_event(item)}

@router.get("/conversations")
def conversations(user_id: str = Depends(_user)):
    with _LOCK, _connect() as db:
        rows = db.execute("SELECT id, created_at, updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
        return {"items": [dict(row) for row in rows]}

@router.post("/conversations", status_code=201)
def create_conversation(user_id: str = Depends(_user)):
    cid = str(uuid.uuid4())
    now = _now()
    with _LOCK, _connect() as db:
        db.execute("INSERT INTO conversations VALUES (?,?,?,?,?)", (cid, user_id, "{}", now, now))
        db.commit()
    return {"id": cid, "createdAt": now}

@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: str = Depends(_user)):
    with _LOCK, _connect() as db:
        row = _conversation(db, conversation_id, user_id)
        messages = db.execute("SELECT role,body,payload,created_at FROM messages WHERE conversation_id=? ORDER BY created_at, rowid", (conversation_id,)).fetchall()
        return {"id": row["id"], "state": json.loads(row["state"]), "messages": [
            {"role": m["role"], "body": m["body"], "result": json.loads(m["payload"]) if m["payload"] else None, "createdAt": m["created_at"]}
            for m in messages
        ]}

@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user_id: str = Depends(_user)):
    with _LOCK, _connect() as db:
        _conversation(db, conversation_id, user_id)
        db.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))
        db.commit()

@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, data: MessageInput, user_id: str = Depends(_user), service=Depends(get_service)):
    # 가상 시연을 제외한 실제 자유 상담만 계정별 SQLite 데이터 스냅샷을 사용한다.
    if load_workspace(user_id)["initialized"] and not (
        data.selection and data.selection.get("field", "").startswith("v4_")
        or "가상 시나리오" in data.text
    ):
        service = ChatService(data_for_chat(service.data, user_id), service.gateway)
    # Guard the read -> AI -> write sequence against concurrent turns.
    with _LOCK, _connect() as db:
        row = _conversation(db, conversation_id, user_id)
        old = db.execute("SELECT payload FROM messages WHERE conversation_id=? AND request_id=?", (conversation_id, data.requestId)).fetchone()
        if old is not None:
            return json.loads(old["payload"])
        previous = db.execute("SELECT role,body FROM messages WHERE conversation_id=? ORDER BY created_at,rowid DESC LIMIT 8", (conversation_id,)).fetchall()
        context = json.loads(row["state"])
        if data.selection:
            field, value = data.selection.get("field"), data.selection.get("value")
            if field not in {"person_id","notice_id","person_confirmed","availability","event_type","attendance_with_meal","budget_krw","budget_state","v4_scenario","v4_attendance","v4_person"}:
                raise HTTPException(422, "허용되지 않은 선택입니다.")
            if field == "person_id" and value not in {p["id"] for p in service.data.people(user_id)}:
                raise HTTPException(403, "선택할 수 없는 지인입니다.")
            if field == "notice_id" and service.data.notice_for_user(user_id, value) is None:
                raise HTTPException(403, "접근할 수 없는 부고입니다.")
            if field != context.get("pending_field"):
                raise HTTPException(409, "현재 대화 단계의 선택이 아닙니다.")
            if field == "person_confirmed" and not context.get("notice_id"):
                raise HTTPException(409, "확인할 부고가 없습니다.")
            if field == "attendance_with_meal" and type(value) is not bool:
                raise HTTPException(422, "식사 여부를 확인해 주세요.")
            if field == "budget_krw":
                if type(value) is not int or value < 0 or value > 1000000000:
                    raise HTTPException(422, "예산을 확인해 주세요.")
            if field == "v4_scenario":
                from .v4_chat import SCENARIOS
                if user_id != "U001" or value not in SCENARIOS:
                    raise HTTPException(403, "선택할 수 없는 가상 시나리오입니다.")
            if field == "v4_attendance" and value not in {"yes", "no"}:
                raise HTTPException(422, "참석·식사 여부를 확인해 주세요.")
            if field == "v4_person" and (
                user_id != "U001" or context.get("v4_scenario") != "duplicate_mourner"
                or value not in {"P001", "P002"}
            ):
                raise HTTPException(403, "이 시연에서 선택할 수 없는 인물입니다.")
            context[field] = value
        history = [{"role": m["role"], "content": m["body"]} for m in reversed(previous)]
        result = service.chat_auto({"user_id": user_id, "question": data.text, "context": context, "history": history})
        # Failed provider calls do not become fake successful conversation turns.
        if result.get("status") == "error":
            raise HTTPException(502, result.get("message") or "AI 서비스에 연결하지 못했습니다.")
        new_state = result.get("context", context)
        now = _now()
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), conversation_id, data.requestId, "user", data.text, json.dumps(result, ensure_ascii=False), now))
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), conversation_id, None, "assistant", result.get("message", ""), json.dumps(result, ensure_ascii=False), now))
            db.execute("UPDATE conversations SET state=?,updated_at=? WHERE id=? AND user_id=?", (json.dumps(new_state, ensure_ascii=False), now, conversation_id, user_id))
            db.commit()
        except Exception:
            db.rollback()
            raise
        return result
