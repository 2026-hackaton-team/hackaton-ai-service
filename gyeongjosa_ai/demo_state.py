"""로그인한 회원의 친구·공유 일정·화면 설정·알림 기록을 서버 SQLite에서 관리한다.

계정과 세션은 account_store가 맡고, 여기서는 같은 DB 파일에 사회관계·설정 표만 둔다.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .account_api import current_account, get_account_store
from .account_store import AccountStore, workspace_owner

router = APIRouter(prefix="/api/account")
_LOCK = threading.RLock()
_DEFAULT_PREFS = {"theme": "auto", "readIds": [], "notifications": {"browser": False}, "sidebarCollapsed": False}


@contextmanager
def _db(store: AccountStore):
    """계정 DB와 같은 파일에서 직렬화된 트랜잭션으로 사용자 상태를 처리한다."""
    with _LOCK:
        store._connect().close()  # 계정 표를 먼저 준비한다.
        db = sqlite3.connect(store.path, timeout=15)
        try:
            db.row_factory = sqlite3.Row
            db.executescript("""
                CREATE TABLE IF NOT EXISTS social_state (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    revision INTEGER NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    username TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS delivered (
                    username TEXT NOT NULL, notice_key TEXT NOT NULL,
                    PRIMARY KEY(username, notice_key)
                );
            """)
            db.execute("INSERT OR IGNORE INTO social_state VALUES (1, 0, ?)",
                       (json.dumps({"friendships": [], "shares": [], "receipts": {}}),))
            with db:
                yield db
        finally:
            db.close()


def _invalidate_recommendation_cache():
    """관계·회원 변경 뒤 다음 AI 요청이 최신 SQLite 자료를 읽게 한다."""
    from .dependencies import get_service
    get_service.cache_clear()


class SocialUpdate(BaseModel):
    revision: int = Field(ge=0)
    friendships: list[dict]
    shares: list[dict]
    receipts: dict


class PreferencePatch(BaseModel):
    theme: str | None = None
    readIds: list[str] | None = None
    notifications: dict | None = None
    sidebarCollapsed: bool | None = None


class NoticeKeys(BaseModel):
    keys: list[str] = Field(max_length=500)


class DeliveredNotice(BaseModel):
    key: str = Field(min_length=1, max_length=200)


@router.get("/social")
def social(profile=Depends(current_account), store=Depends(get_account_store)):
    """서버에 저장된 공유 관계와 회원 공개 정보를 조회한다."""
    with _db(store) as db:
        row = db.execute("SELECT * FROM social_state WHERE id=1").fetchone()
        return {"revision": row["revision"], "social": json.loads(row["payload"]), "members": store.members()}


@router.put("/social")
def update_social(values: SocialUpdate, profile=Depends(current_account), store=Depends(get_account_store)):
    """버전이 일치할 때만 친구 요청·공유 자료를 원자적으로 저장한다."""
    with _db(store) as db:
        current = db.execute("SELECT revision FROM social_state WHERE id=1").fetchone()["revision"]
        if current != values.revision:
            raise HTTPException(409, "사회관계 서버 데이터가 변경됐습니다. 다시 불러와 주세요.")
        payload = values.model_dump(exclude={"revision"})
        db.execute("UPDATE social_state SET revision=?, payload=? WHERE id=1",
                   (current + 1, json.dumps(payload, ensure_ascii=False)))
    _invalidate_recommendation_cache()
    return {"revision": current + 1, "social": payload, "members": store.members()}


def _prefs(db, username):
    row = db.execute("SELECT payload FROM preferences WHERE username=?", (username,)).fetchone()
    return {**_DEFAULT_PREFS, **(json.loads(row["payload"]) if row else {})}


def _save_prefs(db, username, data):
    db.execute("INSERT INTO preferences VALUES (?,?) ON CONFLICT(username) DO UPDATE SET payload=excluded.payload",
               (username, json.dumps(data, ensure_ascii=False)))


@router.get("/preferences")
def preferences(profile=Depends(current_account), store=Depends(get_account_store)):
    """로그인 사용자 개인 설정과 읽음 상태를 조회한다."""
    with _db(store) as db:
        return _prefs(db, profile["username"])


@router.patch("/preferences")
def update_preferences(values: PreferencePatch, profile=Depends(current_account), store=Depends(get_account_store)):
    """서버 설정을 변경하고 현재 값을 반환한다."""
    changes = values.model_dump(exclude_none=True)
    if "theme" in changes and changes["theme"] not in ("auto", "light", "dark"):
        raise HTTPException(422, "화면 모드를 확인해 주세요.")
    if "readIds" in changes and len(changes["readIds"]) > 1000:
        raise HTTPException(422, "읽음 기록이 너무 많습니다.")
    with _db(store) as db:
        current = {**_prefs(db, profile["username"]), **changes}
        _save_prefs(db, profile["username"], current)
        return current


@router.post("/read")
def read_notices(values: NoticeKeys, profile=Depends(current_account), store=Depends(get_account_store)):
    """동시 알림 처리에서도 읽음 상태가 유실되지 않도록 병합한다."""
    with _db(store) as db:
        current = _prefs(db, profile["username"])
        current["readIds"] = list(dict.fromkeys([*current["readIds"], *values.keys]))[-1000:]
        _save_prefs(db, profile["username"], current)
        return current


@router.post("/delivered")
def mark_delivered(values: DeliveredNotice, profile=Depends(current_account), store=Depends(get_account_store)):
    """한 알림의 브라우저 전송 여부를 서버에서 원자적으로 기록한다."""
    with _db(store) as db:
        cursor = db.execute("INSERT OR IGNORE INTO delivered VALUES (?,?)", (profile["username"], values.key))
        return {"send": cursor.rowcount == 1}


def with_server_accounts_and_social(base, store=None):
    """서버 회원과 친구 수락 내역을 AI 추천 관계 그래프에 반영한다."""
    store = store or AccountStore()
    if not store.path.exists():
        return base
    from .data import DemoData
    members = {member["username"]: member for member in store.members()}
    if not members:
        return base
    with _db(store) as db:
        friendships = json.loads(db.execute("SELECT payload FROM social_state WHERE id=1").fetchone()["payload"])["friendships"]
    source = dict(base.dataset)
    users = list(source["users"])
    existing = {user["id"] for user in users}
    for username, member in members.items():
        user_id = workspace_owner(username)
        if user_id in existing:
            continue
        users.append({
            "id": user_id, "name": member["name"], "login_id": username,
            "demo_account": True, "fictional_affiliation": member.get("organization") or "",
            "preferred_region": "서울", "preferred_event_types": [],
        })
        existing.add(user_id)
    graph = list(source["friendships"])
    known = {frozenset((link["user_a_id"], link["user_b_id"])) for link in graph if link.get("status") == "accepted"}
    for link in friendships:
        left, right = link.get("from"), link.get("to")
        if link.get("status") != "accepted" or left not in members or right not in members:
            continue
        pair = frozenset((workspace_owner(left), workspace_owner(right)))
        if len(pair) != 2 or pair in known:
            continue
        graph.append({
            "id": "ACCOUNT-" + link["id"],
            "user_a_id": workspace_owner(left), "user_b_id": workspace_owner(right),
            "status": "accepted", "allow_connection_for_recommendation": True,
        })
        known.add(pair)
    return DemoData({**source, "users": users, "friendships": graph})
