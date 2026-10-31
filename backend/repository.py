"""Replace get_repository with a DB adapter after adding authenticated ownership."""
from datetime import date, timedelta
from typing import Protocol

from fastapi import Request

from .schemas import WorkspaceSnapshot


class WorkspaceRepository(Protocol):
    async def snapshot(self, today: date) -> WorkspaceSnapshot: ...


class MockWorkspaceRepository:
    """Read-only synthetic records; never reads the browser or writes a database."""
    async def snapshot(self, today: date) -> WorkspaceSnapshot:
        day = lambda offset: (today + timedelta(days=offset)).isoformat()
        return WorkspaceSnapshot.model_validate({
            'people': [
                {'id': 'p1', 'name': '김도윤', 'relation': '친구', 'group': '대학 동기', 'importance': '매우 중요', 'lastMet': day(-20)},
                {'id': 'p2', 'name': '윤서진', 'relation': '가족', 'group': '친척', 'importance': '중요', 'lastMet': day(-35)},
                {'id': 'p3', 'name': '이수현', 'relation': '거래처', 'group': '협력사', 'importance': '중요', 'lastMet': day(-60)},
                {'id': 'p4', 'name': '박서연', 'relation': '직장동료', 'group': '회사', 'importance': '중요', 'lastMet': day(-10)},
                {'id': 'p5', 'name': '한지우', 'relation': '동호회 선배', 'group': '독서 모임', 'importance': '보통', 'lastMet': ''},
            ],
            'events': [
                {'id': 'e1', 'personId': 'p1', 'title': '김도윤의 결혼식', 'type': '결혼식', 'date': day(7), 'attendance': '참석'},
                {'id': 'e2', 'personId': 'p2', 'title': '윤서진의 돌잔치', 'type': '돌잔치', 'date': day(14)},
                {'id': 'e3', 'personId': 'p3', 'title': '이수현의 결혼식', 'type': '결혼식', 'date': day(7), 'attendance': '불참'},
                {'id': 'e4', 'personId': 'p4', 'title': '박서연 부친상', 'type': '장례식', 'date': day(1), 'time': '18:00'},
                {'id': 'e5', 'personId': 'p5', 'title': '한지우의 생일', 'type': '생일', 'date': day(4)},
            ],
            'records': [
                {'id': 'r1', 'personId': 'p1', 'type': '장례식', 'date': day(-200), 'direction': '받은 마음', 'amount': 100000},
                {'id': 'r2', 'personId': 'p1', 'type': '결혼식', 'date': day(-300), 'direction': '보낸 마음', 'amount': 100000},
                {'id': 'r3', 'personId': 'p2', 'type': '결혼식', 'date': day(-100), 'direction': '받은 마음', 'amount': 200000},
                {'id': 'r4', 'personId': 'p3', 'type': '결혼식', 'date': day(-350), 'direction': '보낸 마음', 'amount': 100000},
                {'id': 'r5', 'personId': 'p4', 'type': '장례식', 'date': day(-150), 'direction': '받은 마음', 'amount': 100000},
            ],
        })


def get_repository(request: Request) -> WorkspaceRepository:
    # Future DB implementation must obtain a verified user ID from server auth.
    return request.app.state.repository
