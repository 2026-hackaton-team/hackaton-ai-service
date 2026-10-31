import asyncio
import json

import httpx
import pytest

from backend.providers import OpenAIProvider, ProviderError
from backend.schemas import AdviceRequest, AdviceResponse
from backend.settings import Settings


REQUEST = AdviceRequest(question='금액을 참고하고 싶어요', personId='p1')
BASELINE = AdviceResponse(title='참고 기록', text='과거 받은 100,000원을 참고해 주세요.', amount=100000, evidence=[{'label': '최근 받은 마음', 'value': '100,000원'}], suggestions=[])


def provider(handler):
    return OpenAIProvider(Settings(provider='openai', api_key='test-secret-never-log', model='configured-test-model'), transport=httpx.MockTransport(handler))


def test_openai_request_contract_and_text_extraction_without_live_network():
    def handler(request):
        assert str(request.url) == 'https://api.openai.com/v1/responses'
        body = json.loads(request.content)
        assert body['store'] is False
        assert body['model'] == 'configured-test-model'
        assert json.loads(body['input'])['reference']['amount'] == 100000
        return httpx.Response(200, json={'status': 'completed', 'output': [{'type': 'reasoning', 'summary': []}, {'type': 'message', 'content': [{'type': 'output_text', 'text': '기록을 참고하되 예산에 맞게 결정해 주세요.'}]}]})
    text = asyncio.run(provider(handler).render(REQUEST, BASELINE))
    assert text == '기록을 참고하되 예산에 맞게 결정해 주세요.'
    assert BASELINE.amount == 100000


@pytest.mark.parametrize(('status', 'code', 'expected_status'), [(429, 'ai_rate_limited', 429), (401, 'ai_auth_failed', 502), (403, 'ai_auth_failed', 502), (500, 'ai_upstream_error', 502)])
def test_upstream_failures_are_redacted(status, code, expected_status):
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider(lambda _: httpx.Response(status, text='test-secret-never-log PRIVATE RESPONSE')).render(REQUEST, BASELINE))
    assert caught.value.code == code and caught.value.status == expected_status
    assert 'test-secret' not in str(caught.value) and 'PRIVATE' not in str(caught.value)


def test_timeouts_are_distinct_and_redacted():
    def handler(request):
        raise httpx.ReadTimeout('secret provider details', request=request)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider(handler).render(REQUEST, BASELINE))
    assert caught.value.code == 'ai_timeout' and caught.value.status == 504
    assert 'secret' not in str(caught.value)


@pytest.mark.parametrize('body', [
    {'status': 'incomplete', 'output': []},
    {'status': 'completed', 'output': []},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'cannot answer'}]}]},
])
def test_incomplete_or_empty_model_answer_is_not_silent_mock_fallback(body):
    with pytest.raises(ProviderError):
        asyncio.run(provider(lambda _: httpx.Response(200, json=body)).render(REQUEST, BASELINE))
