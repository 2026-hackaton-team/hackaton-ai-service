from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    provider: str = 'mock'
    api_key: str = field(default='', repr=False)
    model: str = ''
    timeout_seconds: float = 25
    cors_origins: tuple[str, ...] = ('http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:5180', 'http://localhost:5180')

    def __post_init__(self):
        if self.provider not in ('mock', 'openai'):
            raise ValueError('AI_PROVIDER는 mock 또는 openai로 설정해 주세요.')
        if self.provider == 'openai' and (not self.api_key.strip() or not self.model.strip()):
            raise ValueError('openai 모드에는 서버의 OPENAI_API_KEY와 OPENAI_MODEL이 필요합니다.')
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError('AI_TIMEOUT_SECONDS는 0보다 크고 120 이하여야 합니다.')
        if '*' in self.cors_origins:
            raise ValueError('CORS_ORIGINS에는 허용할 출처를 직접 지정해 주세요.')

    @classmethod
    def from_env(cls):
        load_dotenv(Path(__file__).with_name('.env'), override=False)
        origins = tuple(value.strip() for value in os.getenv('CORS_ORIGINS', ','.join(cls().cors_origins)).split(',') if value.strip())
        return cls(provider=os.getenv('AI_PROVIDER', 'mock').strip(), api_key=os.getenv('OPENAI_API_KEY', ''), model=os.getenv('OPENAI_MODEL', '').strip(), timeout_seconds=float(os.getenv('AI_TIMEOUT_SECONDS', '25')), cors_origins=origins)
