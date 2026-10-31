"""관계 중요도 정렬 · 지정 공유 · 한 줄 일정 해석을 확인한다."""

from datetime import date

from gyeongjosa_ai.data import load_data
from gyeongjosa_ai.event_parser import parse_event_text, rule_based
from gyeongjosa_ai.relationship_priority import PriorityStore, priority_score


def test_priority_score_uses_only_user_recorded_values():
    assert priority_score(None, 30) == {"score": 0, "reasons": []}
    result = priority_score({"importance": "매우 중요", "special": True, "relation": "가족"}, 5)
    assert result["score"] == 60
    assert result["reasons"] == ["‘매우 중요’로 기록한 가족", "특별히 챙길 사람", "5일 남음"]
    assert priority_score({"importance": "중요"}, 10)["score"] == 15
    assert priority_score({"importance": "보통", "relation": "친척"}, None) == {"score": 0, "reasons": ["친척"]}


def test_designated_notice_reaches_only_chosen_recipients():
    data = load_data()
    ids = lambda user: {item["notice"]["id"] for item in data.recommendations(user)}
    assert {"D001", "D002"} <= ids("U002")
    assert not {"D001", "D002", "D003"} & ids("U001"), "지정되지 않은 사람에게는 친구 관계와 상관없이 보이지 않는다"
    assert "D003" in ids("U003")
    assert "D001" not in ids("U009"), "보낸 사람 본인에게는 추천하지 않는다"
    item = next(entry for entry in data.recommendations("U002") if entry["notice"]["id"] == "D001")
    assert item["relation_type"] == "designated" and item["recipient_group"] == "family"


def test_priorities_change_order_but_not_visibility():
    data = load_data()
    before = [item["notice"]["id"] for item in data.recommendations("U002")]
    boosted = data.recommendations("U002", {"U011": {"importance": "매우 중요", "special": True, "relation": "사촌"}})
    assert {item["notice"]["id"] for item in boosted} == set(before)
    assert boosted[0]["notice"]["id"] == "D002"
    assert boosted[0]["priority_reasons"][:2] == ["‘매우 중요’로 기록한 사촌", "특별히 챙길 사람"]
    # 보낸 사람이 숨겨진 소식은 내가 기록한 중요도를 반영하지 않는다.
    hidden = [item for item in data.recommendations("U001", {"U003": {"importance": "매우 중요", "special": True}})
              if item["publisher_name"] is None]
    assert all(item["priority_score"] <= 10 for item in hidden)


def test_priority_store_round_trip(tmp_path):
    store = PriorityStore(tmp_path / "p.sqlite3")
    store.set("U001", "U011", "매우 중요", True, "사촌")
    assert store.list("U001")["U011"]["special"] is True
    store.set("U001", "U011", "중요", False, None)
    assert store.list("U001")["U011"]["importance"] == "중요"
    assert store.list("U002") == {}
    assert store.delete("U001", "U011") and store.list("U001") == {}


def test_rule_based_event_parsing():
    today = date(2026, 10, 31)
    result = rule_based("다음 주 토요일에 사촌 결혼식이야", today)
    assert result["type"] == "결혼식" and result["date"] == "2026-11-07" and result["relation"] == "사촌"
    result = rule_based("11월 14일 오후 1시 라온웨딩홀 2층에서 김도윤의 결혼식", today)
    assert (result["date"], result["time"], result["location"], result["person_name"]) == ("2026-11-14", "13:00", "라온웨딩홀 2층", "김도윤")
    assert rule_based("내일 저녁 7시 마음빛 장례식장 부친상", today)["type"] == "장례식"
    assert rule_based("고모 칠순 11/22 12시", today)["type"] == "칠순"


class _FailingGateway:
    api_key = "test"

    def _request(self, *args):
        raise RuntimeError("network down")


class _FakeGateway:
    api_key = "test"

    def _request(self, context, prompt, model):
        return '{"type": "결혼식", "date": "2026-11-07", "time": "13:00", "location": "라온 웨딩홀", "person_name": null, "relation": "사촌", "title": "사촌 결혼식", "extra": "무시"}'


def test_ai_parsing_falls_back_to_rules_and_validates_output():
    today = date(2026, 10, 31)
    fallback = parse_event_text("다음 주 토요일 사촌 결혼식", today, gateway=_FailingGateway())
    assert fallback["source"] == "rules" and fallback["suggestion"]["date"] == "2026-11-07"
    ai = parse_event_text("다음 주 토요일 1시 라온 웨딩홀 사촌 결혼식", today, gateway=_FakeGateway())
    assert ai["source"] == "ai" and ai["suggestion"]["time"] == "13:00" and "extra" not in ai["suggestion"]


def test_priority_and_parse_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from gyeongjosa_ai.api import app
    monkeypatch.setenv("GYEONGJOSA_PRIORITY_DB", str(tmp_path / "priority.sqlite3"))
    monkeypatch.setenv("CODYSSEY_API_KEY", "")
    with TestClient(app) as client:
        headers = {"X-Demo-User-Id": "U002"}
        assert client.put("/api/relationship-priorities/U002", json={"importance": "중요"}, headers=headers).status_code == 404
        saved = client.put("/api/relationship-priorities/U011", json={"importance": "매우 중요", "special": True, "relation": "사촌"}, headers=headers)
        assert saved.status_code == 200 and saved.json()["special"] is True
        items = client.get("/api/notices", headers=headers).json()["items"]
        assert items[0]["notice"]["id"] == "D002" and items[0]["priority_score"] >= 50
        assert client.get("/api/relationship-priorities", headers={"X-Demo-User-Id": "U001"}).json()["items"] == []
        parsed = client.post("/api/events/parse", json={"text": "다음 주 토요일 사촌 결혼식", "today": "2026-10-31"})
        assert parsed.status_code == 200 and parsed.json()["suggestion"]["date"] == "2026-11-07"
