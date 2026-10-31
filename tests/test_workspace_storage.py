"""계정별 SQLite 작업 공간의 트랜잭션·이전·입력 경계를 검증한다."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from gyeongjosa_ai.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """각 테스트가 분리된 DB를 사용하도록 지정한다."""
    monkeypatch.setenv("GYEONGJOSA_WORKSPACE_DB", str(tmp_path / "workspace.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


def headers(user="U001"):
    """가상 계정 헤더를 구성한다."""
    return {"X-Demo-User-Id": user}


def snapshot(revision=0):
    """인물·행사·거래의 연결이 올바른 기본 요청이다."""
    return {
        "revision": revision,
        "people": [{"id": "p1", "name": "김도윤", "relation": "친구", "importance": "중요",
                    "group": "동기", "lastMet": "", "memo": "동료", "interactions": []}],
        "events": [{"id": "e1", "personId": "p1", "title": "결혼식",
                    "type": "결혼식", "date": "2026-11-07", "time": "14:00", "location": "",
                    "attendance": "참석", "reminderDays": 3, "memo": ""}],
        "records": [{"id": "r1", "personId": "p1", "eventId": "e1",
                     "type": "결혼식", "date": "2026-11-07", "direction": "보낸 마음",
                     "amount": 100000, "memo": "기록"}],
    }


def test_migration_preview_does_not_change_server(client):
    """이전 미리보기는 저장하지 않고 건수와 버전만 검사한다."""
    preview = client.post("/api/workspace/migrations/preview", headers=headers(), json=snapshot())
    assert preview.status_code == 200, preview.text
    assert preview.json()["recordCount"] == 1
    state = client.get("/api/workspace/personal", headers=headers()).json()
    assert state["initialized"] is False
    assert state["people"] == []
    assert state["revision"] == 0


def test_atomic_write_persists_and_increments_revision(client):
    """서버 재조회에서 자료가 유지되고 버전이 증가한다."""
    created = client.put("/api/workspace/personal", headers=headers(), json=snapshot())
    assert created.status_code == 200, created.text
    assert created.json()["revision"] == 1
    assert created.json()["events"][0]["personId"] == "p1"
    data = client.get("/api/workspace/personal", headers=headers()).json()
    assert data["initialized"] is True
    assert data["records"][0]["amount"] == 100000
    changed = snapshot(revision=1)
    changed["records"][0]["amount"] = 200000
    updated = client.put("/api/workspace/personal", headers=headers(), json=changed)
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == 2
    assert client.get("/api/workspace/personal", headers=headers()).json()["records"][0]["amount"] == 200000


def test_stale_version_cannot_overwrite(client):
    """이미 수정된 서버 자료는 오래된 요청으로 덮어쓸 수 없다."""
    assert client.put("/api/workspace/personal", headers=headers(), json=snapshot()).status_code == 200
    changed = snapshot(revision=0)
    changed["records"][0]["amount"] = 50000
    response = client.put("/api/workspace/personal", headers=headers(), json=changed)
    assert response.status_code == 409
    assert client.get("/api/workspace/personal", headers=headers()).json()["records"][0]["amount"] == 100000


def test_account_isolation(client):
    """인물 ID가 같아도 다른 가상 계정의 자료를 읽거나 덮어쓰지 않는다."""
    assert client.put("/api/workspace/personal", headers=headers("U001"), json=snapshot()).status_code == 200
    other = client.get("/api/workspace/personal", headers=headers("U002")).json()
    assert other["people"] == []
    assert other["initialized"] is False
    changed = snapshot()
    changed["records"][0]["amount"] = 50000
    assert client.put("/api/workspace/personal", headers=headers("U002"), json=changed).status_code == 200
    assert client.get("/api/workspace/personal", headers=headers("U001")).json()["records"][0]["amount"] == 100000
    assert client.get("/api/workspace/personal").status_code == 401


@pytest.mark.parametrize("change", [
    lambda data: data["people"].append(deepcopy(data["people"][0])),
    lambda data: data["records"][0].update(personId="unknown"),
    lambda data: data["records"][0].update(eventId="missing"),
    lambda data: data["events"][0].update(personId="missing"),
    lambda data: data["records"][0].update(amount=0),
    lambda data: data["records"][0].update(amount=-1),
    lambda data: data["records"][0].update(amount=1000000001),
    lambda data: data["records"][0].update(direction="other"),
    lambda data: data["records"][0].update(date="2026-13-01"),
])
def test_invalid_workspace_is_rejected_without_partial_writes(client, change):
    """경계값과 연결 오류가 발생해도 기존 작업 공간은 유지된다."""
    assert client.put("/api/workspace/personal", headers=headers(), json=snapshot()).status_code == 200
    bad = snapshot(revision=1)
    change(bad)
    response = client.put("/api/workspace/personal", headers=headers(), json=bad)
    assert response.status_code == 422, response.text
    current = client.get("/api/workspace/personal", headers=headers()).json()
    assert current["revision"] == 1
    assert current["records"][0]["amount"] == 100000


def test_empty_start_and_repeated_migration(client):
    """빈 계정 시작과 이전 중복 요청을 구분한다."""
    blank = {"revision": 0, "people": [], "events": [], "records": []}
    assert client.put("/api/workspace/personal", headers=headers(), json=blank).status_code == 200
    assert client.get("/api/workspace/personal", headers=headers()).json()["initialized"] is True
    assert client.post("/api/workspace/migrations/preview", headers=headers(), json=blank).status_code == 409


def test_delete_event_preserves_record_with_unlinked_event(client):
    """연결된 행사 삭제 전에 거래 연결을 해제하면 거래는 보존된다."""
    assert client.put("/api/workspace/personal", headers=headers(), json=snapshot()).status_code == 200
    modified = snapshot(revision=1)
    modified["events"] = []
    modified["records"][0]["eventId"] = ""
    response = client.put("/api/workspace/personal", headers=headers(), json=modified)
    assert response.status_code == 200
    assert response.json()["records"][0]["amount"] == 100000


def test_legacy_demo_workspace_contract_remains(client):
    """이전 읽기 전용 합성 데이터 API는 기존 계약을 유지한다."""
    legacy = client.get("/api/workspace", headers=headers())
    assert legacy.status_code == 200
    assert legacy.json()["source"] == "rag-demo-json-read-only"
