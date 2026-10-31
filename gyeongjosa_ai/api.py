"""가상 시연 화면과 팀 연동을 위한 최소 HTTP 인터페이스."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .ai import ModelGateway
from .data import REFERENCE_DATE, load_data
from .service import ChatService


ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="마음결 AI 가상 시연", version="0.1.0")


class ChatRequest(BaseModel):
    """가상 계정의 자연어 질문과 이전 대화 맥락."""

    user_id: str = Field(min_length=1, max_length=30)
    question: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


@lru_cache(maxsize=1)
def get_service():
    """고정된 가상 데이터와 모델 연결을 준비한다."""
    return ChatService(load_data(), ModelGateway())


def require_user(service, user_id):
    """알 수 없는 가상 계정은 조회하지 않는다."""
    if user_id not in service.data.users:
        raise HTTPException(status_code=404, detail="가상 계정을 찾을 수 없습니다.")


@app.get("/", include_in_schema=False)
def index():
    """로컬 확인용 단일 화면을 반환한다."""
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/health")
def health(service: ChatService = Depends(get_service)):
    """서버와 가상 데이터 상태만 확인한다."""
    return {"status": "ok", "users": len(service.data.users), "reference_date": REFERENCE_DATE.isoformat()}


@app.get("/api/users")
def users(service: ChatService = Depends(get_service)):
    """선택할 수 있는 가상 계정 목록을 반환한다."""
    return {"users": service.data.list_users()}


@app.get("/api/users/{user_id}/people")
def people(user_id: str, service: ChatService = Depends(get_service)):
    """선택한 가상 계정의 지인만 반환한다."""
    require_user(service, user_id)
    return {"people": service.data.people(user_id)}


@app.get("/api/users/{user_id}/notices")
def notices(user_id: str, service: ChatService = Depends(get_service)):
    """선택한 계정에 허용된 부고와 점수를 반환한다."""
    require_user(service, user_id)
    return {"reference_date": REFERENCE_DATE.isoformat(), "notices": service.data.recommendations(user_id)}


@app.get("/api/users/{user_id}/dashboard")
def dashboard(user_id: str, service: ChatService = Depends(get_service)):
    """선택한 계정의 받은·낸 금액만 반환한다."""
    require_user(service, user_id)
    return service.data.dashboard(user_id)


@app.post("/api/chat")
def chat(request: ChatRequest, service: ChatService = Depends(get_service)):
    """기능 선택 없이 자연어 질문을 처리한다."""
    return service.chat_auto(request.model_dump())

from .integration_api import router as integration_router
app.include_router(integration_router)

