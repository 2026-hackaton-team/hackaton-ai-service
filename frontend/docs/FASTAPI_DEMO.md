# DB 없는 FastAPI AI 데모

기본 실행은 **React → FastAPI → 서버 가상 데이터 → 모의 응답 → React**입니다. DB와 AI 키 없이 동작합니다. 가상 인물 5명과 받은/보낸 금액, 오늘을 기준으로 한 일정을 서버에서 만들며, 브라우저에 저장한 실제 인맥·장부를 업로드하지 않습니다. 대화의 질문·도움 유형·선택한 서버 인맥 ID를 전송합니다.

## Windows에서 실행

Node.js와 Python 3.11 이상을 설치한 후 PowerShell에서 프로젝트 폴더로 이동합니다. 아래 `cd` 경로는 실제 clone한 폴더로 바꿉니다.

```powershell
cd "C:\프로젝트\hackaton-ai-service"
npm.cmd install
npm.cmd run setup:demo
npm.cmd run dev:demo
```

이미 의존성을 설치했다면 `npm.cmd run dev:demo`만 실행합니다. 가상환경 활성화 명령이나 PowerShell 실행 정책 변경은 필요하지 않습니다. 시작 스크립트는 `.venv`의 Python으로 서버를 실행합니다.

- 화면: http://127.0.0.1:5173/#ai
- API 문서(Swagger): http://127.0.0.1:8000/docs
- 상태 확인: http://127.0.0.1:8000/api/health
- 종료: 터미널에서 `Ctrl+C` (이 스크립트가 시작한 두 서버 종료)

포트가 이미 사용 중이면 기존 서버를 자동 종료하지 않습니다. 다른 포트로 실행할 수 있습니다.

```powershell
$env:MAEUM_WEB_PORT = "5180"
$env:MAEUM_API_PORT = "8001"
npm.cmd run dev:demo
```

`npm.cmd run dev`는 프론트만 실행합니다. FastAPI를 따로 켜려면 아래 명령을 별도 터미널에서 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

## 화면에서 확인

홈 하단 또는 마음 AI 화면에서 **서버 가상 데이터**를 선택합니다. 서버 연결 상태와 모의 응답 표시를 확인한 후 질문합니다. **브라우저 체험**으로 바꾸면 기존 브라우저 기록을 참고합니다. 두 데이터는 자동으로 합치거나 동기화하지 않습니다.

| 확인할 기능 | 선택 인맥·질문 예시 |
| --- | --- |
| 금액 참고 | 김도윤 → 이번 결혼식에 얼마를 참고하면 될까? |
| 불참 대응 | 이수현 → 결혼식에 참석하지 못하면? |
| 위로 문구 | 박서연 → 조문을 못 갈 때 보낼 위로 메시지 작성해줘 |
| 우선순위 | 가장 먼저 챙길 경조사를 알려줘 |
| 기록 부족 | 한지우 → 생일에 얼마를 참고하면 될까? |

서버에서 근거 기록을 고르고 금액을 정합니다. 기록이 없으면 임의의 금액을 만들어 내지 않습니다. 서버 오류는 오류로 표시하고 재시도·취소·브라우저 체험 전환을 지원합니다. 서버 모드가 실패했다고 브라우저 응답으로 자동 대체하지 않습니다.

## 실제 AI API로 전환(선택)

기본값은 `AI_PROVIDER=mock`입니다. 실제 외부 API는 호출하지 않습니다. OpenAI를 사용하려면 `backend/.env.example`을 `backend/.env`로 복사하고 아래 세 항목을 서버에서 설정합니다.

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=서버에서만_설정
OPENAI_MODEL=사용할_모델_ID
```

서버를 재시작하면 실제 AI 응답을 사용합니다. 실제 제공자에는 질문과 선택된 근거/참고 답변이 전송되고 사용 요금이 발생할 수 있습니다. 이번 검증은 가짜 HTTP 응답으로 수행했으며 실제 키의 유효성이나 모델 접근 권한을 확인하지 않았습니다. 모델 ID는 계정에서 사용 가능한 것으로 지정합니다. 키를 React 코드·루트 `.env`의 `VITE_*`에 넣지 않습니다.

실제 AI는 응답 문장을 작성하며 화면의 금액·근거 메타데이터는 서버 코드가 결정합니다. 금액과 근거가 있더라도 생성 문장 자체의 사실성을 완벽히 보장하는 기능은 아니므로, 운영 전 응답 품질 검증이 필요합니다. 실제 AI 오류를 모의 응답으로 숨기지 않습니다.

공식 참고: [OpenAI API Quickstart](https://developers.openai.com/api/docs/quickstart), [FastAPI 의존성 교체](https://fastapi.tiangolo.com/advanced/testing-dependencies/).

## DB를 연결할 위치

- `backend/repository.py`: `WorkspaceRepository.snapshot(today)`와 `get_repository()`를 실제 DB 조회로 교체합니다. 반환 모델은 `WorkspaceSnapshot`을 유지합니다.
- `backend/app.py`: 실제 서버 인증으로 사용자 식별을 추가하고, 해당 사용자의 인맥·일정·금액만 조회하도록 repository에 사용자 범위를 전달합니다.
- `backend/advice.py`: DB와 분리된 금액·근거·우선순위 로직입니다.
- `backend/providers.py`: 모의 응답 / 실제 AI 호출을 담당합니다.
- `src/services/aiChat.js`, `src/AIPage.jsx`: 응답 검증, 연결 상태, 비동기 대화 화면입니다.

이 서버는 **인증 없는 로컬 가상 데이터 데모**입니다. 일반 인맥·일정·금액 CRUD, 실제 계정과 DB 저장, 영구 대화 이력, 서버 예약 알림은 구현 범위에 포함하지 않았습니다. 서버에 가상 장례 일정이 있어도 브라우저 일정이나 조사 테마를 변경하지 않습니다.

## 배포와 기존 사이트

현재 Sites 주소는 정적 React 배포입니다. 해당 정적 호스팅에서는 Python FastAPI 프로세스를 실행하지 않으므로 기본 브라우저 체험을 유지합니다. FastAPI 전체 흐름은 위 PC 실행으로 확인합니다.

온라인에서 서버 데모를 사용하려면 FastAPI를 별도 서버에 배포하고 HTTPS 주소를 `VITE_AI_API_BASE_URL`에 지정해 프론트를 재빌드합니다. `VITE_AI_MODE=server`를 함께 설정하고 서버의 `CORS_ORIGINS`에 실제 프론트 출처를 지정합니다. 운영 공개 전 사용자 인증·권한·사용량 제한을 추가해야 합니다. 현재 로컬 실행은 `127.0.0.1`에만 연결합니다.

## 검증

```powershell
npm.cmd test
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm.cmd run build
```

백엔드 테스트는 가상 데이터와 모의 HTTP 전송만 사용합니다. 실제 DB나 유료 AI 호출이 필요하지 않습니다.
