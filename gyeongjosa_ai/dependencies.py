"""통합 API가 공유하는 가상 상담 서비스를 준비한다."""

from functools import lru_cache

from .ai import ModelGateway
from .data import load_data
from .service import ChatService


@lru_cache(maxsize=1)
def get_service():
    """고정된 가상 데이터와 모델 연결을 준비한다."""
    return ChatService(load_data(), ModelGateway())
