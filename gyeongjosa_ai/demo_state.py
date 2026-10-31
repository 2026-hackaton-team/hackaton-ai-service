"""시연용 로그인·사회관계·화면 상태를 서버 SQLite에서 관리한다."""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/account")
_LOCK = threading.RLock()
_COOKIE = "maeum_session"
_ITERATIONS = 210000
_USERNAME = re.compile(r"^[a-z0-9_]{4,20}$")
_WORK_TYPES = {"일반 회사원", "공무원", "공공기관 직원", "교직원", "언론인", "자영업·프리랜서", "학생", "기타"}
_VISIBILITIES = {"전체 공개", "친구에게만 공개", "비공개"}
_DEFAULT_PREFS = {"theme": "auto", "readIds": [], "notifications": {"browser": False}, "sidebarCollapsed": False}


def _path():
    """실행 중에는 기존 SQLite 시드와 별도의 사용자 상태 DB를 사용한다."""
    return Path(os.getenv("GYEONGJOSA_ACCOUNT_DB", "data/demo_accounts.sqlite3"))


@contextmanager
def _db():
    """직렬화된 SQLite 트랜잭션에서 시연 사용자 상태를 처리한다."""
    with _LOCK:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=15) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY, profile TEXT NOT NULL,
                    salt TEXT, password_hash TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(username) REFERENCES accounts(username)
                );
                CREATE TABLE IF NOT EXISTS social_state (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    revision INTEGER NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    username TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    FOREIGN KEY(username) REFERENCES accounts(username)
                );
                CREATE TABLE IF NOT EXISTS delivered (
                    username TEXT NOT NULL, notice_key TEXT NOT NULL,
                    PRIMARY KEY(username, notice_key)
                );
            """)
            db.execute("INSERT OR IGNORE INTO social_state VALUES (1, 0, ?)",
                       (json.dumps({"friendships": [], "shares": [], "receipts": {}}),))
            yield db
            db.commit()


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()


def _validate(username, profile):
    if not _USERNAME.fullmatch(username):
        raise HTTPException(422, "아이디는 영문·숫자·밑줄로 4~20자 입력해 주세요.")
    if not (1 <= len(profile.get("name", "").strip()) <= 40):
        raise HTTPException(422, "이름을 확인해 주세요.")
    if not re.fullmatch(r"\+?\d{9,15}", re.sub(r"[\s()\-]", "", profile.get("phone", ""))):
        raise HTTPException(422, "전화번호를 확인해 주세요.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", profile.get("email", "").lower()):
        raise HTTPException(422, "이메일 주소를 확인해 주세요.")
    if profile.get("workType") not in _WORK_TYPES or profile.get("visibility") not in _VISIBILITIES:
        raise HTTPException(422, "직무형태와 정보공개 범위를 확인해 주세요.")


def _public(row):
    return json.loads(row["profile"]) if row else None


def _identity(username):
    """합성 사용자 계정의 고정 서버 식별자를 결정한다."""
    if username == "test1234":
        return "TEST1234"
    if username == "kim_scenario":
        return "SCENARIO_KIM"
    legacy = {"demo_seojin": "U001", "demo_doyoon": "U002", "demo_subin": "U003", "demo_haeun": "U004"}
    return legacy.get(username, "LOCAL_" + username.upper())


def _session(db, session):
    if not session:
        return None
    key = hashlib.sha256(session.encode()).hexdigest()
    row = db.execute("""SELECT accounts.* FROM sessions JOIN accounts
                        ON accounts.username=sessions.username
                        WHERE sessions.token_hash=? AND sessions.expires_at>?""",
                     (key, datetime.now(timezone.utc).isoformat())).fetchone()
    return row


def _required(db, session):
    account = _session(db, session)
    if not account:
        raise HTTPException(401, "로그인이 필요합니다.")
    return account


def _create_session(db, response, username):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=2)
    db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
               (hashlib.sha256(token.encode()).hexdigest(), username, expires.isoformat()))
    response.set_cookie(_COOKIE, token, max_age=172800, httponly=True, samesite="lax",
                        secure=False, path="/")


def _test_seed(db):
    """기존 test1234 합성 관계를 최초 한 번만 생성하고 사용자가 고친 값은 보존한다."""
    if not db.execute("SELECT 1 FROM accounts WHERE username='test1234'").fetchone():
        profile = {
            "username": "test1234", "name": "테스트 사용자", "phone": "01000000000",
            "email": "test1234@example.invalid", "workplace": "마음결 시연팀",
            "organization": "해커톤 시연", "workType": "일반 회사원", "visibility": "전체 공개",
        }
        salt = os.urandom(16).hex()
        db.execute("INSERT INTO accounts VALUES (?,?,?,?)",
                   ("test1234", json.dumps(profile, ensure_ascii=False), salt, _hash("test1234", salt)))
    names = ("윤서진", "김도윤", "이수빈", "박하은", "정유림", "한소민",
             "최유정", "오지훈", "서예린", "강민혁", "윤지아", "송재현")
    for index, name in enumerate(names, 1):
        username = f"test_friend{index:02d}"
        profile = {
            "username": username, "name": name, "phone": "", "email": username+"@example.invalid",
            "workplace": "가상 마음결 모임", "organization": "시연팀",
            "workType": "일반 회사원", "visibility": "전체 공개",
        }
        db.execute("INSERT OR IGNORE INTO accounts(username,profile) VALUES (?,?)",
                   (username, json.dumps(profile, ensure_ascii=False)))
    row = db.execute("SELECT revision,payload FROM social_state WHERE id=1").fetchone()
    social = json.loads(row["payload"])
    pairs = {tuple(sorted((f["from"], f["to"]))) for f in social["friendships"]}
    links = [("test1234", f"test_friend{i:02d}") for i in range(1, 10)]
    links += [("test_friend01", "test_friend10"), ("test_friend02", "test_friend11"),
              ("test_friend03", "test_friend12")]
    for left, right in links:
        key = tuple(sorted((left, right)))
        if key not in pairs:
            social["friendships"].append({
                "id": "test-link-" + ":".join(key), "from": left, "to": right,
                "status": "accepted", "createdAt": "2026-10-31T00:00:00Z",
            })
            pairs.add(key)
    examples = [
        ("test-share-01", "test_friend01", "윤서진", "윤서진 결혼식", "결혼식", "friends", ["test1234"], 10),
        ("test-share-02", "test_friend02", "김도윤", "김도윤 가족 환갑잔치", "환갑", "friends", ["test1234"], 24),
        ("test-share-03", "test_friend10", "강민혁", "강민혁 돌잔치", "돌잔치", "friends_of_friends", [], 31),
    ]
    for eid, owner, name, title, kind, scope, recipients, offset in examples:
        if any(s["id"] == eid for s in social["shares"]):
            continue
        when = (datetime.now(timezone(timedelta(hours=9))).date() + timedelta(days=offset)).isoformat()
        social["shares"].append({
            "id": eid, "owner": owner, "ownerName": name, "eventId": eid+"-event",
            "scope": scope, "recipients": recipients,
            "event": {"title": title, "type": kind, "date": when, "time": "12:00",
                      "location": "가상 서울 행사장", "memo": "합성 테스트 소식"},
            "message": "마음결 시연용 일정입니다.", "group": None,
            "createdAt": "2026-10-31T00:00:00Z", "updatedAt": "2026-10-31T00:00:00Z",
        })
    changed = json.dumps(social, ensure_ascii=False)
    if changed != row["payload"]:
        db.execute("UPDATE social_state SET revision=?,payload=? WHERE id=1",
                   (row["revision"] + 1, changed))


class Credentials(BaseModel):
    username: str
    password: str


class Signup(BaseModel):
    username: str
    name: str
    password: str = Field(min_length=8, max_length=128)
    phone: str
    email: str
    workplace: str = ""
    organization: str = ""
    workType: str
    visibility: str


class ProfileUpdate(BaseModel):
    phone: str
    email: str
    workplace: str = ""
    organization: str = ""
    workType: str
    visibility: str
    currentPassword: str = ""
    password: str = ""


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


@router.get("/session")
def session(maeum_session: str | None = Cookie(default=None)):
    """HttpOnly 세션으로 현재 로그인 사용자를 복원한다."""
    with _db() as db:
        account = _session(db, maeum_session)
        if not account:
            return {"profile": None, "userId": ""}
        username = account["username"]
        return {"profile": _public(account), "userId": _identity(username)}


@router.post("/signup")
def signup(values: Signup, response: Response):
    """사용자를 서버 SQLite에 등록하고 세션을 발급한다."""
    username = values.username.strip().lower()
    profile = values.model_dump(exclude={"password"})
    profile["username"] = username
    profile["email"] = profile["email"].lower()
    _validate(username, profile)
    if len(profile["workplace"]) > 60 or len(profile["organization"]) > 60:
        raise HTTPException(422, "직장·소속기관을 확인해 주세요.")
    with _db() as db:
        if db.execute("SELECT 1 FROM accounts WHERE username=?", (username,)).fetchone():
            raise HTTPException(409, "이미 사용 중인 아이디입니다.")
        if any(_public(row).get("email", "").lower() == profile["email"] for row in db.execute("SELECT profile FROM accounts")):
            raise HTTPException(409, "이미 사용 중인 이메일입니다.")
        salt = os.urandom(16).hex()
        db.execute("INSERT INTO accounts VALUES (?,?,?,?)",
                   (username, json.dumps(profile, ensure_ascii=False), salt, _hash(values.password, salt)))
        _create_session(db, response, username)
        return {"profile": profile, "userId": _identity(username)}


@router.post("/login")
def login(values: Credentials, response: Response):
    """테스트 계정을 포함한 서버 계정의 비밀번호를 검사한다."""
    username = values.username.strip().lower()
    with _db() as db:
        if username == "test1234":
            _test_seed(db)
        account = db.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
        if not account or not account["salt"] or not hmac.compare_digest(
            account["password_hash"], _hash(values.password, account["salt"])
        ):
            raise HTTPException(401, "아이디와 비밀번호를 확인해 주세요.")
        _create_session(db, response, username)
        return {"profile": _public(account), "userId": _identity(username)}


@router.post("/logout")
def logout(response: Response, maeum_session: str | None = Cookie(default=None)):
    """현재 세션을 폐기한다."""
    with _db() as db:
        if maeum_session:
            db.execute("DELETE FROM sessions WHERE token_hash=?",
                       (hashlib.sha256(maeum_session.encode()).hexdigest(),))
    response.delete_cookie(_COOKIE, path="/")
    return {"ok": True}


@router.put("/profile")
def update_profile(values: ProfileUpdate, maeum_session: str | None = Cookie(default=None)):
    """비밀번호 검사를 거쳐 개인 프로필을 서버에서 변경한다."""
    with _db() as db:
        account = _required(db, maeum_session)
        profile = {**_public(account), **values.model_dump(exclude={"password", "currentPassword"})}
        _validate(account["username"], profile)
        if values.password:
            if len(values.password) < 8 or not values.currentPassword or not hmac.compare_digest(
                account["password_hash"], _hash(values.currentPassword, account["salt"])
            ):
                raise HTTPException(422, "현재 비밀번호 또는 새 비밀번호를 확인해 주세요.")
            salt = os.urandom(16).hex()
            db.execute("UPDATE accounts SET salt=?,password_hash=? WHERE username=?",
                       (salt, _hash(values.password, salt), account["username"]))
        if any(_public(row).get("email", "").lower() == profile["email"].lower()
               and row["username"] != account["username"] for row in db.execute("SELECT username,profile FROM accounts")):
            raise HTTPException(409, "다른 계정이 사용하는 이메일입니다.")
        db.execute("UPDATE accounts SET profile=? WHERE username=?",
                   (json.dumps(profile, ensure_ascii=False), account["username"]))
        return {"profile": profile}


@router.get("/social")
def social(maeum_session: str | None = Cookie(default=None)):
    """서버에 저장된 공유 관계와 회원 디렉터리를 조회한다."""
    with _db() as db:
        _required(db, maeum_session)
        row = db.execute("SELECT * FROM social_state WHERE id=1").fetchone()
        members = [_public(account) for account in db.execute("SELECT profile FROM accounts")]
        return {"revision": row["revision"], "social": json.loads(row["payload"]), "members": members}


@router.put("/social")
def update_social(values: SocialUpdate, maeum_session: str | None = Cookie(default=None)):
    """버전이 일치할 때만 친구 요청·공유 자료를 원자적으로 저장한다."""
    with _db() as db:
        _required(db, maeum_session)
        current = db.execute("SELECT revision FROM social_state WHERE id=1").fetchone()["revision"]
        if current != values.revision:
            raise HTTPException(409, "사회관계 서버 데이터가 변경됐습니다. 다시 불러와 주세요.")
        payload = values.model_dump(exclude={"revision"})
        db.execute("UPDATE social_state SET revision=?, payload=? WHERE id=1",
                   (current+1, json.dumps(payload, ensure_ascii=False)))
        members = [_public(account) for account in db.execute("SELECT profile FROM accounts")]
        return {"revision": current+1, "social": payload, "members": members}


@router.get("/preferences")
def preferences(maeum_session: str | None = Cookie(default=None)):
    """로그인 사용자 개인 설정과 읽음 상태를 조회한다."""
    with _db() as db:
        account = _required(db, maeum_session)
        row = db.execute("SELECT payload FROM preferences WHERE username=?", (account["username"],)).fetchone()
        return {**_DEFAULT_PREFS, **(json.loads(row["payload"]) if row else {})}


def _save_prefs(db, username, data):
    db.execute("INSERT INTO preferences VALUES (?,?) ON CONFLICT(username) DO UPDATE SET payload=excluded.payload",
               (username, json.dumps(data, ensure_ascii=False)))


@router.patch("/preferences")
def update_preferences(values: PreferencePatch, maeum_session: str | None = Cookie(default=None)):
    """서버 설정을 변경하고 현재 값을 반환한다."""
    with _db() as db:
        account = _required(db, maeum_session)
        row = db.execute("SELECT payload FROM preferences WHERE username=?", (account["username"],)).fetchone()
        current = {**_DEFAULT_PREFS, **(json.loads(row["payload"]) if row else {})}
        changes = values.model_dump(exclude_none=True)
        if "theme" in changes and changes["theme"] not in ("auto", "light", "dark"):
            raise HTTPException(422, "화면 모드를 확인해 주세요.")
        if "readIds" in changes and len(changes["readIds"]) > 1000:
            raise HTTPException(422, "읽음 기록이 너무 많습니다.")
        current.update(changes)
        _save_prefs(db, account["username"], current)
        return current


@router.post("/read")
def read_notices(values: NoticeKeys, maeum_session: str | None = Cookie(default=None)):
    """동시 알림 처리에서도 읽음 상태가 유실되지 않도록 병합한다."""
    with _db() as db:
        account = _required(db, maeum_session)
        row = db.execute("SELECT payload FROM preferences WHERE username=?", (account["username"],)).fetchone()
        current = {**_DEFAULT_PREFS, **(json.loads(row["payload"]) if row else {})}
        current["readIds"] = list(dict.fromkeys([*current["readIds"], *values.keys]))[-1000:]
        _save_prefs(db, account["username"], current)
        return current


@router.post("/delivered")
def mark_delivered(values: DeliveredNotice, maeum_session: str | None = Cookie(default=None)):
    """한 알림의 브라우저 전송 여부를 서버에서 원자적으로 기록한다."""
    with _db() as db:
        account = _required(db, maeum_session)
        cursor = db.execute("INSERT OR IGNORE INTO delivered VALUES (?,?)",
                            (account["username"], values.key))
        return {"send": cursor.rowcount == 1}


def with_server_accounts_and_social(base):
    """서버 사용자 계정과 친구 수락 내역을 AI 추천 관계 그래프에 반영한다."""
    if not _path().exists():
        return base
    from .data import DemoData
    with _db() as db:
        rows = db.execute("SELECT username,profile FROM accounts").fetchall()
        account_profiles = {row["username"]: json.loads(row["profile"]) for row in rows}
        if not account_profiles:
            return base
        raw = db.execute("SELECT payload FROM social_state WHERE id=1").fetchone()
        friendships = json.loads(raw["payload"])["friendships"]
    source = dict(base.dataset)
    users = list(source["users"])
    existing = {user["id"] for user in users}
    for username, profile in account_profiles.items():
        user_id = _identity(username)
        if user_id in existing:
            continue
        users.append({
            "id": user_id, "name": profile["name"], "login_id": username,
            "demo_account": True, "fictional_affiliation": profile.get("organization") or "",
            "preferred_region": "서울", "preferred_event_types": [],
        })
        existing.add(user_id)
    graph = list(source["friendships"])
    known = {frozenset((link["user_a_id"], link["user_b_id"])) for link in graph
             if link.get("status") == "accepted"}
    for link in friendships:
        if link.get("status") != "accepted":
            continue
        left, right = link.get("from"), link.get("to")
        if left not in account_profiles or right not in account_profiles:
            continue
        pair = frozenset((_identity(left), _identity(right)))
        if len(pair) != 2 or pair in known:
            continue
        graph.append({
            "id": "ACCOUNT-" + link["id"],
            "user_a_id": _identity(left), "user_b_id": _identity(right),
            "status": "accepted", "allow_connection_for_recommendation": True,
        })
        known.add(pair)
    return DemoData({**source, "users": users, "friendships": graph})
