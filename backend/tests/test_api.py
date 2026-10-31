from datetime import date

from fastapi.testclient import TestClient
import pytest

from backend.app import create_app, get_today
from backend.providers import ProviderError
from backend.repository import MockWorkspaceRepository, get_repository
from backend.schemas import WorkspaceSnapshot
from backend.settings import Settings


@pytest.fixture
def app():
    application = create_app(Settings())
    application.dependency_overrides[get_today] = lambda: date(2026, 10, 31)
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def ask(client, **patch):
    return client.post('/api/ai/advice', json={'question': '금액을 참고하고 싶어요', 'mode': '금액 참고', 'personId': 'p1', **patch})


def test_health_and_context_expose_demo_metadata_and_no_secrets(client):
    assert client.get('/api/health').json() == {'status': 'ok', 'provider': 'mock', 'dataSource': 'mock'}
    context = client.get('/api/demo/context').json()
    assert context['today'] == '2026-10-31'
    assert len(context['people']) == 5
    assert context['people'][0]['importance'] == '매우 중요'
    assert 'api_key' not in str(context)


def test_mock_money_uses_server_records_and_never_calls_external_api(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Mock provider must not construct a network client')
    monkeypatch.setattr('backend.providers.httpx.AsyncClient', forbidden)
    result = ask(client).json()
    assert result['amount'] == 100000
    assert result['provider'] == 'mock'
    assert result['dataSource'] == 'mock' and result['demo'] is True
    assert any('100,000원' in item['value'] for item in result['evidence'])
    assert '유형이 다르다' in result['text']


@pytest.mark.parametrize(('mode', 'question', 'expected'), [
    ('금액 참고', '얼마를 준비하면 좋을까요?', '100,000원'),
    ('참석 대응', '가지 못하면 어떻게 하나요? 불참이에요', '참석이 어려운'),
    ('메시지 작성', '축하 문구를 작성해 주세요', '결혼을 진심으로 축하'),
    ('우선순위', '누구를 먼저 챙길까요?', '박서연 부친상'),
])
def test_four_modes(client, mode, question, expected):
    response = ask(client, mode=mode, question=question)
    assert response.status_code == 200
    assert expected in response.json()['text']


def test_explicit_intent_overrides_mode_and_absence_carries_to_message(client):
    result = ask(client, personId='p3', mode='금액 참고', question='불참할 때 보낼 메시지를 작성해 주세요').json()
    assert result['isMessage'] is True
    assert '함께하지 못해' in result['text']
    assert 'amount' not in result
    funeral = ask(client, personId='p4', question='위로 메시지를 작성해 주세요').json()
    assert funeral['isMessage'] is True and '애도' in funeral['text']
    assert '축하' not in funeral['text']
    wedding = ask(client, question='축하·위로 메시지 작성').json()
    assert '결혼을 진심으로 축하' in wedding['text']
    assert '애도' not in wedding['text']


def test_no_financial_history_does_not_invent_amount(client):
    result = ask(client, personId='p5').json()
    assert 'amount' not in result
    assert '충분하지 않아' in result['text']
    assert all('원' not in item['value'] for item in result['evidence'])


@pytest.mark.parametrize('patch', [
    {'question': ''}, {'question': '   '}, {'question': 'a' * 1001}, {'mode': '송금'},
    {'personId': ''}, {'userId': 'someone-else'}, {'records': []}, {'amount': 999999},
])
def test_input_validation_does_not_accept_client_supplied_facts(client, patch):
    response = ask(client, **patch)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_failed'
    assert 'fields' in response.json()['error']


def test_missing_person_or_unrelated_event_returns_404(client):
    assert ask(client, personId='missing').json()['error']['code'] == 'person_not_found'
    response = ask(client, eventId='e2')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'event_not_found'


def test_explicit_cors_allowlist(client):
    headers = {'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type'}
    response = client.options('/api/ai/advice', headers=headers)
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    blocked = client.options('/api/ai/advice', headers={**headers, 'Origin': 'https://untrusted.invalid'})
    assert blocked.status_code == 400
    assert 'access-control-allow-origin' not in blocked.headers


def test_repository_is_replaceable_without_changing_endpoint(app):
    class OtherRepository:
        async def snapshot(self, today):
            return WorkspaceSnapshot.model_validate({'people': [{'id': 'db-person', 'name': '테스트 사용자', 'relation': '이웃'}], 'events': [], 'records': []})
    app.dependency_overrides[get_repository] = lambda: OtherRepository()
    with TestClient(app) as client:
        assert client.get('/api/demo/context').json()['people'][0]['id'] == 'db-person'
        assert ask(client, personId='db-person').status_code == 200
        message = ask(client, personId='db-person', question='메시지 작성해 주세요').json()
        assert '어떤 행사인지' in message['text']
        assert '결혼' not in message['text']
        assert ask(client, personId='p1').status_code == 404


def test_priority_orders_funeral_then_date_then_three_importance_levels(app):
    class PriorityRepository:
        async def snapshot(self, today):
            original = await MockWorkspaceRepository().snapshot(today)
            original.events = [event for event in original.events if event.personId in ('p1', 'p3')]
            original.events.reverse()
            return original
    app.dependency_overrides[get_repository] = lambda: PriorityRepository()
    with TestClient(app) as client:
        result = ask(client, mode='우선순위', question='먼저 챙길 일정').json()
        assert result['text'].startswith('김도윤의 결혼식')
        assert result['evidence'][-1]['value'] == '매우 중요'


def test_provider_failure_returns_error_instead_of_mock_success():
    class FailedProvider:
        name = 'openai'
        async def render(self, request, baseline):
            raise ProviderError('AI 응답 시간이 초과됐어요.', 'ai_timeout', 504)
    with TestClient(create_app(Settings(), provider=FailedProvider())) as client:
        result = ask(client)
        assert result.status_code == 504
        assert result.json()['error']['code'] == 'ai_timeout'


def test_invalid_live_configuration_fails_before_serving():
    with pytest.raises(ValueError, match='AI_PROVIDER'):
        Settings(provider='something')
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        Settings(provider='openai')
    with pytest.raises(ValueError, match='CORS_ORIGINS'):
        Settings(cors_origins=('*',))
