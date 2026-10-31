"""가상 시연 화면과 팀 연동을 위한 최소 HTTP 인터페이스."""

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .data import REFERENCE_DATE, public_legacy_candidate
from .dependencies import get_service
from .service import ChatService
from .workspace_adapter import data_for_chat
from .workspace_store import load_workspace
from .account_api import bearer_token, get_account_store
from .account_store import WORKSPACE_PREFIX, workspace_owner
from .test_account_seed import TEST_USER_ID


ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="마음결 AI 가상 시연", version="0.1.0")


class ChatRequest(BaseModel):
    """가상 계정의 자연어 질문과 이전 대화 맥락."""

    user_id: str = Field(min_length=1, max_length=30)
    question: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


def require_user(service, user_id, token, accounts):
    """회원·테스트 계정은 자신의 세션으로만 조회하고 알 수 없는 계정은 거부한다."""
    if user_id == TEST_USER_ID or user_id.startswith(WORKSPACE_PREFIX):
        profile = accounts.authenticate(token)
        if profile is None or workspace_owner(profile["username"]) != user_id:
            raise HTTPException(401, "로그인한 계정의 기록만 사용할 수 있어요. 다시 로그인해 주세요.")
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
def people(user_id: str, service: ChatService = Depends(get_service),
           token: str = Depends(bearer_token), accounts=Depends(get_account_store)):
    """선택한 가상 계정의 지인만 반환한다."""
    require_user(service, user_id, token, accounts)
    data = data_for_chat(service.data, user_id) if load_workspace(user_id)["initialized"] else service.data
    return {"people": data.people(user_id)}


@app.get("/api/users/{user_id}/notices")
def notices(user_id: str, service: ChatService = Depends(get_service),
            token: str = Depends(bearer_token), accounts=Depends(get_account_store)):
    """선택한 계정에 허용된 부고와 점수를 반환한다."""
    require_user(service, user_id, token, accounts)
    return {"reference_date": REFERENCE_DATE.isoformat(), "notices": [
        public_legacy_candidate(item) for item in service.data.recommendations(user_id)
    ]}


@app.get("/api/users/{user_id}/dashboard")
def dashboard(user_id: str, service: ChatService = Depends(get_service),
              token: str = Depends(bearer_token), accounts=Depends(get_account_store)):
    """선택한 계정의 받은·낸 금액만 반환한다."""
    require_user(service, user_id, token, accounts)
    data = data_for_chat(service.data, user_id) if load_workspace(user_id)["initialized"] else service.data
    return data.dashboard(user_id)


@app.post("/api/chat")
def chat(request: ChatRequest, service: ChatService = Depends(get_service),
         token: str = Depends(bearer_token), accounts=Depends(get_account_store)):
    """기능 선택 없이 자연어 질문을 처리한다."""
    require_user(service, request.user_id, token, accounts)
    if load_workspace(request.user_id)["initialized"] and "가상 시나리오" not in request.question:
        service = ChatService(data_for_chat(service.data, request.user_id), service.gateway)
    return service.chat_auto(request.model_dump())

from .integration_api import router as integration_router
from .account_api import router as account_router
app.include_router(integration_router)
app.include_router(account_router)

from .demo_state import router as demo_state_router
app.include_router(demo_state_router)

