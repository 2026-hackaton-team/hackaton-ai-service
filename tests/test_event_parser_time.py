"""일정 입력의 자정·정오 변환과 잘못된 시간 거부를 확인한다."""
from datetime import date

import pytest

from gyeongjosa_ai.event_parser import rule_based


@pytest.mark.parametrize(("text", "expected"), [
    ("오전 12시", "00:00"),
    ("오전 12시 반", "00:30"),
    ("오전 12:30", "00:30"),
    ("오후 12시", "12:00"),
    ("오후 12시 30분", "12:30"),
    ("오후 12:30", "12:30"),
    ("오전 1시", "01:00"),
    ("오후 1시", "13:00"),
    ("오후 1:05", "13:05"),
    ("아침 12시", "00:00"),
    ("저녁 7시", "19:00"),
    ("밤 12시", "00:00"),
    ("낮 12시", "12:00"),
    ("정오", "12:00"),
    ("00:00", "00:00"),
    ("23:59", "23:59"),
    ("0시", "00:00"),
    ("23시 59분", "23:59"),
    ("2시", "14:00"),
    ("12시", "12:00"),
    ("1:05", "01:05"),
])
def test_valid_event_time(text, expected):
    result = rule_based(f"11월 7일 {text} 사촌 결혼식", date(2026, 10, 31))
    assert result["time"] == expected
    assert result["date"] == "2026-11-07"
    assert result["type"] == "결혼식"


@pytest.mark.parametrize("text", [
    "24시", "25시", "99시", "125시", "001시",
    "오전 0시", "오후 0시", "오전 13시", "오후 25시",
    "2시 60분", "2시 75분", "2시 125분",
    "24:00", "25:00", "99:00", "125:00", "001:00",
    "12:60", "12:345", "12:5", "오전 13:00", "오후 25:00",
    "시간 미정",
])
def test_invalid_event_time_is_left_unfilled(text):
    result = rule_based(f"11월 7일 {text} 사촌 결혼식", date(2026, 10, 31))
    assert result["time"] is None
