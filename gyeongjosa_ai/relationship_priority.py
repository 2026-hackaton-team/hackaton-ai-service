"""사용자가 직접 기록한 관계 중요도로 '이미 볼 수 있는' 소식의 순서만 정한다.

- 누가 어떤 소식을 볼 수 있는지(공유 권한)는 이 모듈이 바꾸지 않는다.
- 중요도·특별 표시는 기록한 사람만의 개인 정보이며, 상대방에게 전달하지 않는다.
- 점수는 효과가 검증된 기준이 아니라 시연과 조정을 위한 출발값이다.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

WEIGHTS = {"매우 중요": 30, "중요": 15, "special": 20, "within_7_days": 10}
IMPORTANCE_OPTIONS = ("매우 중요", "중요", "보통")


def normalize_importance(value) -> str:
    text = str(value or "").replace(" ", "")
    if text == "매우중요":
        return "매우 중요"
    return "중요" if text == "중요" else "보통"


def priority_score(priority: dict | None, days_until: int | None) -> dict:
    """중요도·특별 표시·남은 날짜로 점수와 사람이 읽을 수 있는 추천 이유를 만든다."""
    score, reasons = 0, []
    if priority:
        relation = str(priority.get("relation") or "").strip()
        importance = normalize_importance(priority.get("importance"))
        if importance in ("매우 중요", "중요"):
            score += WEIGHTS[importance]
            reasons.append(f"‘{importance}’로 기록한 {relation or '사람'}")
        elif relation:
            reasons.append(relation)
        if priority.get("special") is True:
            score += WEIGHTS["special"]
            reasons.append("특별히 챙길 사람")
    if days_until is not None and 0 <= days_until <= 7:
        score += WEIGHTS["within_7_days"]
        reasons.append("오늘" if days_until == 0 else f"{days_until}일 남음")
    return {"score": score, "reasons": reasons}


class PriorityStore:
    """프로필별로 다른 계정에 대해 기록한 중요도를 보관한다."""

    def __init__(self, path):
        self.path = Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("""
            CREATE TABLE IF NOT EXISTS relationship_priorities (
                owner_user_id TEXT NOT NULL,
                target_user_id TEXT NOT NULL,
                importance TEXT NOT NULL,
                special INTEGER NOT NULL DEFAULT 0,
                relation TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (owner_user_id, target_user_id)
            )
        """)
        db.commit()
        return db

    def list(self, owner_user_id) -> dict:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT target_user_id, importance, special, relation, updated_at FROM relationship_priorities WHERE owner_user_id = ?",
                (owner_user_id,),
            ).fetchall()
        return {row[0]: {"importance": row[1], "special": bool(row[2]), "relation": row[3], "updated_at": row[4]} for row in rows}

    def set(self, owner_user_id, target_user_id, importance, special=False, relation=None) -> dict:
        item = {"importance": normalize_importance(importance), "special": bool(special),
                "relation": (relation or "").strip()[:20] or None,
                "updated_at": datetime.now(timezone.utc).isoformat()}
        with closing(self._connect()) as db:
            db.execute(
                """INSERT INTO relationship_priorities VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(owner_user_id, target_user_id) DO UPDATE SET
                   importance = excluded.importance, special = excluded.special,
                   relation = excluded.relation, updated_at = excluded.updated_at""",
                (owner_user_id, target_user_id, item["importance"], int(item["special"]), item["relation"], item["updated_at"]),
            )
            db.commit()
        return item

    def delete(self, owner_user_id, target_user_id) -> bool:
        with closing(self._connect()) as db:
            cursor = db.execute("DELETE FROM relationship_priorities WHERE owner_user_id = ? AND target_user_id = ?",
                                (owner_user_id, target_user_id))
            db.commit()
            return cursor.rowcount > 0
