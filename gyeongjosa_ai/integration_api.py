"""Local demo API: explicit account selection and durable per-account conversations.

This is NOT production authentication. Do not expose this application publicly.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from .api import get_service

router = APIRouter(prefix="/api")
_DB = Path(os.environ.get("GYEONGJOSA_DEMO_DB", str(Path(__file__).resolve().parents[1] / "data" / "demo_conversations.sqlite3")))
_LOCK = threading.RLock()

def _connect():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(_DB, timeout=15)
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
    return db

def _now():
    return datetime.now(timezone.utc).isoformat()

def _user(x_demo_user_id: str = Header(default=""), service=Depends(get_service)):
    if not x_demo_user_id or x_demo_user_id not in service.data.users:
        raise HTTPException(401, "가상 계정을 먼저 선택하세요. 실제 인증 기능은 제공되지 않습니다.")
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

@router.get("/demo/users")
def demo_users(service=Depends(get_service)):
    return {"items": service.data.list_users(), "referenceDate": "2026-10-30", "demo": True}

@router.get("/workspace")
def workspace(user_id: str = Depends(_user), service=Depends(get_service)):
    return {
        "schemaVersion": 1,
        "people": service.data.people(user_id),
        "events": service.data.events(user_id),
        "dashboard": service.data.dashboard(user_id),
        "source": "rag-demo-json-read-only"
    }

@router.get("/notices")
def notices(user_id: str = Depends(_user), service=Depends(get_service)):
    return {"items": service.data.recommendations(user_id), "demo": True}

@router.get("/notices/{notice_id}")
def notice(notice_id: str, user_id: str = Depends(_user), service=Depends(get_service)):
    item = service.data.notice_for_user(user_id, notice_id)
    if item is None:
        raise HTTPException(404, "공유 허용된 부고가 아닙니다.")
    return {"notice": item, "identityCandidates": service.data.matching_people(user_id, item["notice"])}

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
            if field not in {"person_id","notice_id","person_confirmed","availability","event_type","budget_krw","budget_state"}:
                raise HTTPException(422, "허용되지 않은 선택입니다.")
            if field == "person_id" and value not in {p["id"] for p in service.data.people(user_id)}:
                raise HTTPException(403, "선택할 수 없는 지인입니다.")
            if field == "notice_id" and service.data.notice_for_user(user_id, value) is None:
                raise HTTPException(403, "접근할 수 없는 부고입니다.")
            if field != context.get("pending_field"):
                raise HTTPException(409, "현재 대화 단계의 선택이 아닙니다.")
            if field == "person_confirmed" and not context.get("notice_id"):
                raise HTTPException(409, "확인할 부고가 없습니다.")
            if field == "budget_krw":
                if type(value) is not int or value < 0 or value > 1000000000:
                    raise HTTPException(422, "예산을 확인해 주세요.")
            context[field] = value
        history = [{"role": m["role"], "content": m["body"]} for m in reversed(previous)]
        result = service.chat_auto({"user_id": user_id, "question": data.text, "context": context, "history": history})
        # Failed provider calls do not become fake successful conversation turns.
        if result.get("status") == "error":
            raise HTTPException(502, result.get("message") or "AI 서비스에 연결하지 못했습니다.")
        new_state = result.get("context") or context
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
