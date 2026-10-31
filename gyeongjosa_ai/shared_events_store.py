"""가상 공유 경조사를 별도 SQLite 저장소에 보관한다."""

import json
import sqlite3
import uuid
from contextlib import closing

from .test_account_seed import own_shared_events
from datetime import datetime, timezone
from pathlib import Path


class SharedEventsStore:
    """가상 소식과 공유 철회 상태를 저장한다."""

    def __init__(self, path):
        self.path = Path(path)

    def _connect(self):
        """공유 소식 테이블을 준비하고 연결을 반환한다."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("""
            CREATE TABLE IF NOT EXISTS shared_events (
                id TEXT PRIMARY KEY,
                publisher_user_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        db.commit()
        return db

    def list_all(self):
        """저장된 가상 소식을 반환한다."""
        with closing(self._connect()) as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM shared_events ORDER BY id")]

    def get(self, event_id):
        """저장된 가상 소식 한 건을 반환한다."""
        with closing(self._connect()) as db:
            row = db.execute("SELECT payload FROM shared_events WHERE id = ?", (event_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def create(self, publisher_user_id, values):
        """공유자와 소식 식별자를 서버에서 정해 저장한다."""
        now = datetime.now(timezone.utc).isoformat()
        item = {
            **values,
            "id": "DSE-" + str(uuid.uuid4()),
            "publisher_user_id": publisher_user_id,
            "related_user_id": publisher_user_id if values.get("related_role") else None,
            "shared_occurrence_id": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        with closing(self._connect()) as db:
            db.execute("INSERT INTO shared_events VALUES (?, ?, ?)",
                       (item["id"], publisher_user_id, json.dumps(item, ensure_ascii=False)))
            db.commit()
        return item

    def seed_test_events(self):
        """기존 소식을 보존하며 테스트 계정의 최초 공유 소식만 추가한다."""
        with closing(self._connect()) as db:
            for item in own_shared_events():
                db.execute("INSERT OR IGNORE INTO shared_events VALUES (?, ?, ?)",
                           (item["id"], item["publisher_user_id"], json.dumps(item, ensure_ascii=False)))
            db.commit()

    def revoke(self, event_id, publisher_user_id):
        """작성자의 소식만 비공개로 바꾼다."""
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM shared_events WHERE id = ? AND publisher_user_id = ?",
                             (event_id, publisher_user_id)).fetchone()
            if row is None:
                db.rollback()
                return None
            item = json.loads(row[0])
            item["audience_scope"] = "private"
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE shared_events SET payload = ? WHERE id = ? AND publisher_user_id = ?",
                       (json.dumps(item, ensure_ascii=False), event_id, publisher_user_id))
            db.commit()
            return item
