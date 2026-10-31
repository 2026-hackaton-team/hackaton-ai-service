from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .advice import build_advice
from .providers import AdviceProvider, ProviderError, make_provider
from .repository import MockWorkspaceRepository, WorkspaceRepository, get_repository
from .schemas import AdviceRequest, AdviceResponse
from .settings import Settings


def get_today() -> date:
    return datetime.now(timezone(timedelta(hours=9))).date()


def get_provider(request: Request) -> AdviceProvider:
    return request.app.state.provider


def create_app(settings: Settings | None = None, repository: WorkspaceRepository | None = None, provider: AdviceProvider | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title='마음결 AI 모의 API', version='1.0.0', description='가상 데이터 전용 로컬 개발 서버입니다. 실제 인증·DB·영구 대화 저장은 제공하지 않습니다.')
    app.state.repository = repository or MockWorkspaceRepository()
    app.state.provider = provider or make_provider(settings)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True, allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'Accept'])

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = {'.'.join(str(value) for value in error['loc'][1:]): '입력 형식과 길이를 확인해 주세요.' for error in exc.errors()}
        return JSONResponse(status_code=422, content={'error': {'code': 'validation_failed', 'message': '질문·도움 유형·인맥 정보를 확인해 주세요.', 'fields': fields}})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {'code': 'http_error', 'message': '요청을 처리하지 못했어요.'}
        return JSONResponse(status_code=exc.status_code, content={'error': detail})

    @app.exception_handler(ProviderError)
    async def provider_error(_: Request, exc: ProviderError):
        return JSONResponse(status_code=exc.status, content={'error': {'code': exc.code, 'message': str(exc)}})

    @app.get('/api/health')
    async def health(provider: AdviceProvider = Depends(get_provider)):
        return {'status': 'ok', 'provider': provider.name, 'dataSource': 'mock'}

    @app.get('/api/demo/context')
    async def context(repository: WorkspaceRepository = Depends(get_repository), provider: AdviceProvider = Depends(get_provider), today: date = Depends(get_today)):
        snapshot = await repository.snapshot(today)
        return {'people': [person.model_dump() for person in snapshot.people], 'provider': provider.name, 'dataSource': 'mock', 'today': today.isoformat()}

    @app.post('/api/ai/advice', response_model=AdviceResponse, response_model_exclude_none=True)
    async def advice(body: AdviceRequest, repository: WorkspaceRepository = Depends(get_repository), provider: AdviceProvider = Depends(get_provider), today: date = Depends(get_today)):
        snapshot = await repository.snapshot(today)
        if not any(person.id == body.personId for person in snapshot.people):
            raise HTTPException(404, detail={'code': 'person_not_found', 'message': '서버 가상 데이터에서 해당 인맥을 찾을 수 없어요.'})
        if body.eventId and not any(event.id == body.eventId and event.personId == body.personId for event in snapshot.events):
            raise HTTPException(404, detail={'code': 'event_not_found', 'message': '선택한 인맥과 연결된 일정을 찾을 수 없어요.'})
        baseline = build_advice(body, snapshot, today)
        text = await provider.render(body, baseline)
        return baseline.model_copy(update={'text': text, 'provider': provider.name})

    return app


app = create_app()
