"""회원 계정과 로그인 세션을 SQLite에 보관한다.

로컬 시연용이다. HTTPS·비밀번호 재설정·잠금 정책 같은 운영 기능은 없다.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "demo_accounts.sqlite3"
PBKDF2_ITERATIONS = 210000
SESSION_DAYS = 30
# 작업공간 소유자 ID. 가상 AI 프로필 ID(U001 등)와 겹치지 않는다.
WORKSPACE_PREFIX = "ACC:"
TEST_USERNAME = "test1234"
DEMO_IDENTITIES = {TEST_USERNAME: "TEST1234", "kim_scenario": "SCENARIO_KIM"}
SESSION_COOKIE = "maeum_session"
WORK_TYPES = ("일반 회사원", "공무원", "공공기관 직원", "교직원", "언론인", "자영업·프리랜서", "학생", "기타")
VISIBILITY_OPTIONS = ("전체 공개", "친구에게만 공개", "비공개")
PUBLIC_FIELDS = ("username", "name", "phone", "email", "workplace", "organization", "workType", "visibility")
TEST_PROFILE = {"name": "테스트 사용자", "phone": "", "email": "test1234@example.invalid",
                "workplace": "마음결 시연팀", "organization": "해커톤 시연",
                "workType": "일반 회사원", "visibility": "전체 공개"}


def normalize_username(value):
    return str(value or "").strip().lower()


def normalize_phone(value):
    return re.sub(r"[\s()\-]", "", str(value or "").strip())


def normalize_email(value):
    return str(value or "").strip().lower()


def workspace_owner(username):
    """계정의 서버 사용자 ID. 인맥·일정·장부·AI 상담·알림이 모두 이 ID를 쓴다.

    test1234처럼 합성 데이터에 이미 있는 시연 계정은 그 ID에, 나머지 회원은 ACC:아이디에 연결한다.
    """
    username = normalize_username(username)
    return DEMO_IDENTITIES.get(username, WORKSPACE_PREFIX + username)


class ContactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str = Field(max_length=24)
    email: str = Field(max_length=254)
    workplace: str = Field(default="", max_length=60)
    organization: str = Field(default="", max_length=60)
    workType: str
    visibility: str


class SignupInput(ContactInput):
    username: str = Field(max_length=20)
    name: str = Field(max_length=40)
    password: str = Field(max_length=128)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


class ProfileUpdateInput(ContactInput):
    password: str = Field(default="", max_length=128)
    currentPassword: str = Field(default="", max_length=128)


def _contact_error(data):
    """프런트 accountRules.js와 같은 규칙으로 연락처·직무 값을 검사한다."""
    if not re.fullmatch(r"\+?\d{9,15}", normalize_phone(data.phone)):
        return "전화번호를 확인해 주세요. 예: 010-1234-5678"
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalize_email(data.email)):
        return "이메일 주소를 확인해 주세요."
    if data.workType not in WORK_TYPES:
        return "직무형태를 선택해 주세요."
    if data.visibility not in VISIBILITY_OPTIONS:
        return "정보공개여부를 선택해 주세요."
    return ""


def _hash(password, salt, iterations=PBKDF2_ITERATIONS):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc)


class AccountStore:
    """계정 정보와 세션 토큰(해시)만 저장한다. 비밀번호 원문과 토큰 원문은 저장하지 않는다."""

    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("GYEONGJOSA_ACCOUNTS_DB", str(DEFAULT_DB)))

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        self._set_aside_legacy_tables(db)
        db.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                workplace TEXT NOT NULL DEFAULT '',
                organization TEXT NOT NULL DEFAULT '',
                work_type TEXT NOT NULL,
                visibility TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_iterations INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL REFERENCES accounts(username) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_username ON sessions (username);
        """)
        return db

    @staticmethod
    def _set_aside_legacy_tables(db):
        """예전 develop 시연 DB(프로필을 JSON 한 칸에 저장하던 계정 표)가 같은 파일에 있으면 지우지 않고 이름만 바꿔 둔다."""
        for table, required in (("accounts", "work_type"), ("sessions", "created_at")):
            columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            if columns and required not in columns:
                db.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy_{secrets.token_hex(3)}")
        db.commit()

    def members(self):
        """친구 찾기용 공개 정보만 돌려준다. 연락처·비밀번호는 내보내지 않는다."""
        with closing(self._connect()) as db:
            return [{"username": row["username"], "name": row["name"], "workplace": row["workplace"],
                     "organization": row["organization"], "workType": row["work_type"], "visibility": row["visibility"]}
                    for row in db.execute("SELECT * FROM accounts ORDER BY created_at, username")]

    @staticmethod
    def _profile(row):
        return {"username": row["username"], "name": row["name"], "phone": row["phone"], "email": row["email"],
                "workplace": row["workplace"], "organization": row["organization"],
                "workType": row["work_type"], "visibility": row["visibility"]}

    def _session(self, db, username):
        token = secrets.token_urlsafe(32)
        now = _now()
        db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)",
                   (_token_hash(token), username, now.isoformat(), (now + timedelta(days=SESSION_DAYS)).isoformat()))
        return token

    def _insert(self, db, username, name, contact, password):
        salt = secrets.token_bytes(16)
        now = _now().isoformat()
        try:
            db.execute("INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                username, name, normalize_phone(contact["phone"]), normalize_email(contact["email"]),
                contact["workplace"].strip(), contact["organization"].strip(), contact["workType"], contact["visibility"],
                salt.hex(), _hash(password, salt), PBKDF2_ITERATIONS, now, now))
        except sqlite3.IntegrityError as error:
            message = "이미 사용 중인 이메일이에요." if "email" in str(error) else "이미 사용 중인 아이디예요."
            raise HTTPException(409, message) from error

    def signup(self, data: SignupInput):
        """새 계정을 만들고 바로 로그인한다."""
        username = normalize_username(data.username)
        if username == TEST_USERNAME:
            raise HTTPException(400, "test1234는 시연 전용 계정입니다. 로그인 화면을 이용해 주세요.")
        if not re.fullmatch(r"[a-z0-9_]{4,20}", username):
            raise HTTPException(400, "아이디는 영문·숫자·밑줄로 4~20자 입력해 주세요.")
        if not data.name.strip():
            raise HTTPException(400, "이름을 입력해 주세요.")
        if len(data.password) < 8:
            raise HTTPException(400, "비밀번호는 8자 이상으로 입력해 주세요.")
        error = _contact_error(data)
        if error:
            raise HTTPException(400, error)
        with closing(self._connect()) as db, db:
            self._insert(db, username, data.name.strip(), data.model_dump(), data.password)
            token = self._session(db, username)
            row = db.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
        return {"profile": self._profile(row), "token": token}

    def login(self, data: LoginInput):
        """아이디·비밀번호를 확인하고 새 세션을 발급한다. test1234는 처음 로그인할 때 만든다."""
        username = normalize_username(data.username)
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
            if row is None and username == TEST_USERNAME and data.password == TEST_USERNAME:
                self._insert(db, username, TEST_PROFILE["name"], TEST_PROFILE, data.password)
                row = db.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
            if row is None or not hmac.compare_digest(
                    _hash(data.password, bytes.fromhex(row["password_salt"]), row["password_iterations"]),
                    row["password_hash"]):
                raise HTTPException(401, "아이디와 비밀번호를 확인해 주세요.")
            token = self._session(db, username)
        return {"profile": self._profile(row), "token": token}

    def authenticate(self, token):
        """유효한 세션의 계정 정보를 반환한다. 없거나 만료되면 None."""
        if not token:
            return None
        with closing(self._connect()) as db, db:
            row = db.execute("""SELECT accounts.* , sessions.expires_at FROM sessions
                                JOIN accounts USING (username) WHERE token_hash = ?""",
                             (_token_hash(token),)).fetchone()
            if row is None:
                return None
            if datetime.fromisoformat(row["expires_at"]) <= _now():
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
                return None
            return self._profile(row)

    def update(self, username, data: ProfileUpdateInput):
        """연락처·직무·공개 범위를 바꾸고, 요청하면 현재 비밀번호 확인 후 비밀번호도 바꾼다."""
        error = _contact_error(data)
        if error:
            raise HTTPException(400, error)
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
            if row is None:
                raise HTTPException(401, "다시 로그인해 주세요.")
            values = [normalize_phone(data.phone), normalize_email(data.email), data.workplace.strip(),
                      data.organization.strip(), data.workType, data.visibility]
            password_sql = ""
            if data.password:
                if len(data.password) < 8:
                    raise HTTPException(400, "새 비밀번호는 8자 이상으로 입력해 주세요.")
                current = _hash(data.currentPassword, bytes.fromhex(row["password_salt"]), row["password_iterations"])
                if not hmac.compare_digest(current, row["password_hash"]):
                    raise HTTPException(400, "현재 비밀번호가 맞지 않아요.")
                salt = secrets.token_bytes(16)
                password_sql = ", password_salt = ?, password_hash = ?, password_iterations = ?"
                values += [salt.hex(), _hash(data.password, salt), PBKDF2_ITERATIONS]
            try:
                db.execute(f"""UPDATE accounts SET phone = ?, email = ?, workplace = ?, organization = ?,
                               work_type = ?, visibility = ?{password_sql}, updated_at = ? WHERE username = ?""",
                           (*values, _now().isoformat(), username))
            except sqlite3.IntegrityError as error:
                raise HTTPException(409, "다른 계정에서 사용 중인 이메일이에요.") from error
            row = db.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
        return self._profile(row)

    def logout(self, token):
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token or ""),))
