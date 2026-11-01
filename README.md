# 마음결 — 경조사 기록·상담·공유 추천

마음결은 경조사 일정과 금액 기록을 관리하고, 기록·예산·관계 맥락을 참고해 상담과 공유 소식 추천을 제공하는 해커톤 시연 앱입니다. 프런트엔드는 React/Vite, 백엔드는 FastAPI이며 데이터는 합성 시연 자료를 사용합니다.

> **상태:** 로컬 시연용 프로토타입입니다. 로그인은 시연용이며 실제 개인정보나 직무 민감정보를 입력하거나 서버를 외부에 공개하지 마세요. AI의 법률·금액 안내는 참고 정보이며 법률 자문이나 적법성 확인을 대신하지 않습니다.

## 주요 기능

- 인맥, 경조사 일정, 보낸·받은 금액을 계정별로 저장하고 조회합니다.
- 자연어 상담에서 관련 기록과 예산을 함께 보여 주며, 정보가 부족하거나 직무 위험 단서가 있으면 추가 확인 또는 추천 보류를 반환할 수 있습니다.
- 공유 소식은 작성자가 정한 범위와 확인 조건에 따라 추천합니다. 관계 유형만으로 공개 권한을 넓히지 않습니다.
- 사용자 중요도와 특별 관리 표시는 이미 접근할 수 있는 소식의 추천 순서에 반영합니다.

## 실행 환경

저장소 CI에 지정된 기준은 다음과 같습니다. 패키지 설치에는 네트워크가 필요합니다.

| 구성 | 기준 |
|---|---|
| Python | 3.12 |
| Node.js | 22 |
| 프런트 패키지 관리자 | Corepack 및 pnpm 11.25.0 |
| 로컬 셸 | Windows PowerShell 또는 macOS 터미널 |

### 모델 키 설정

모델 기반 자유 상담에는 Codyssey API 키와 네트워크 연결이 필요합니다. 저장소 루트의 `.env.example`을 복사해 `.env`를 만든 뒤 `CODYSSEY_API_KEY`를 설정하세요. 기존 `.env`가 있으면 덮어쓰지 않습니다.

**Windows PowerShell — 저장소 루트에서**

~~~powershell
if (-not (Test-Path -LiteralPath '.env')) {
  Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
~~~

**macOS 터미널 — 저장소 루트에서**

~~~sh
if [ ! -f .env ]; then
  cp .env.example .env
fi
~~~

`CODYSSEY_BASE_URL` 기본값은 `.env.example`에 있으며, 코드의 기본 주소는 `https://copa.codyssey.kr/v1`입니다. 질문과 답변에 필요한 계정 맥락이 모델 제공자에게 전송될 수 있으므로 실제 개인정보를 입력하지 마세요. API 키를 Git에 올리거나 화면·로그에 노출하지 마세요.

### 백엔드 실행

아래 명령은 저장소 루트에서 실행합니다. 가상환경은 사용자 문서 폴더 아래 `Documents/Codex/venvs`에 둡니다.

**Windows PowerShell — 터미널 1**

~~~powershell
$venv = Join-Path $env:USERPROFILE 'Documents\Codex\venvs\maeum-gyeol'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
  py -3.12 -m venv $venv
}
& $python -m pip install -r requirements.txt 'openai>=1.75,<3'
& $python -m uvicorn gyeongjosa_ai.api:app --host 127.0.0.1 --port 8000
~~~

**macOS — 터미널 1**

~~~sh
venv="$HOME/Documents/Codex/venvs/maeum-gyeol"
python3.12 -m venv "$venv"
"$venv/bin/python" -m pip install -r requirements.txt 'openai>=1.75,<3'
"$venv/bin/python" -m uvicorn gyeongjosa_ai.api:app --host 127.0.0.1 --port 8000
~~~

백엔드 터미널은 켜 둡니다. 서버 상태는 `http://127.0.0.1:8000/api/health`에서 확인합니다. 정상 응답에는 `status: ok`가 포함됩니다.

### 프런트엔드 실행

새 터미널을 열고 저장소 루트에서 실행합니다.

~~~sh
cd frontend
corepack pnpm install --frozen-lockfile
corepack pnpm dev
~~~

브라우저에서 `http://127.0.0.1:5173`을 엽니다. 종료하려면 각 서버 터미널에서 `Ctrl+C`를 누릅니다.

저장소에는 `window_start.cmd`와 `mac_start.cmd` 통합 실행 스크립트도 있습니다. 이 스크립트는 저장소 안에 `.venv`를 자동 생성하는 방식입니다. 공용 가상환경을 사용할 때는 위의 두 터미널 절차를 따르세요.

## API

실행 후 FastAPI의 실제 요청·응답 스키마는 [Swagger UI](http://127.0.0.1:8000/docs)에서 확인할 수 있습니다.

| 경로 | 용도 |
|---|---|
| `GET /api/health` | 서버 및 시연 데이터 상태 |
| `/api/auth/signup`, `/api/auth/login`, `/api/auth/logout` | 로컬 시연 계정과 세션 |
| `GET`·`PUT /api/workspace/personal` | 로그인 계정의 인맥·일정·금액 작업공간 |
| `/api/conversations` 및 `/api/conversations/{id}/messages` | 계정별 상담 대화 |
| `GET /api/shared-events/recommendations` | 계정에 허용된 공유 소식 추천 |

일부 경로는 로그인 세션이 필요합니다. 세부 입력 형식과 오류 응답은 실행 중인 `/docs`를 기준으로 확인하세요.

## 구성과 데이터

~~~text
frontend/                    React 화면과 Vite 개발 서버
gyeongjosa_ai/               통합 FastAPI, 계정·작업공간·상담·공유 API
app/                         추천 정책과 근거 검색 모듈
data/gyeongjosa_seed.sqlite3 합성 시연 데이터베이스
~~~

프런트엔드는 `/api` 요청을 FastAPI로 전달합니다. 백엔드는 추천·근거 계산에 로컬 모듈과 합성 데이터를 사용하며, 계정·작업공간·대화·공유 기록은 별도 SQLite 파일에 저장합니다. 기본 저장 범위와 데이터 계약은 [작업 공간 저장 안내](docs/WORKSPACE_STORAGE.md)를 참고하세요.

## 테스트와 빌드

저장소 CI와 같은 명령입니다. 아래 명령은 해당 검증을 실행할 때 사용합니다.

**Windows PowerShell — 저장소 루트**

~~~powershell
& (Join-Path $env:USERPROFILE 'Documents\Codex\venvs\maeum-gyeol\Scripts\python.exe') -m pytest -q tests
~~~

**macOS — 저장소 루트**

~~~sh
"$HOME/Documents/Codex/venvs/maeum-gyeol/bin/python" -m pytest -q tests
~~~

**React — `frontend/`에서**

~~~sh
corepack pnpm test
corepack pnpm build
~~~

CI는 Python 테스트와 React 단위 테스트·빌드를 실행합니다. 실제 Codyssey 모델 호출과 최종 브라우저 E2E는 이 CI 절차에 포함되지 않습니다. 워크플로 세부 사항은 [integration-checks.yml](.github/workflows/integration-checks.yml)을 참고하세요.

## 문서와 제한사항

- [현재 문서·구버전 보관 안내](docs/DOCUMENT_INDEX.md)
- [발표 시연 운영서](docs/PRESENTATION_DEMO.md)
- [작업 공간 SQLite 데이터 계약](docs/WORKSPACE_STORAGE.md)
- [기여 안내](CONTRIBUTING.md)
- **인증·배포:** 로컬 시연용 세션이며 운영 서비스 인증이나 배포 검증은 완료된 상태가 아닙니다. 외부 공개에 사용하지 마세요.
- **데이터:** `data/`의 시연용 합성 자료와 로컬 SQLite를 사용합니다. 저장된 대화에는 질문 본문이 포함될 수 있습니다.
- **라이선스:** 저장소 루트에 별도 라이선스 파일이 없습니다.
