"""통합 API가 공유하는 가상 상담 서비스를 준비한다."""

from functools import lru_cache

from .ai import ModelGateway
from .data import load_data
from .service import ChatService
from .scenario_lab import ensure_scenario_workspace, with_scenario_user
from .demo_state import with_server_accounts_and_social


@lru_cache(maxsize=1)
def get_service():
    """고정된 가상 데이터와 모델 연결을 준비한다."""
    ensure_scenario_workspace()
    return ChatService(with_server_accounts_and_social(with_scenario_user(load_data())), ModelGateway())
