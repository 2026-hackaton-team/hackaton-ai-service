# 마음결 FastAPI 모의 서버

DB와 AI API 키 없이 `React → FastAPI → 모의 AI 응답 → React`를 확인하는 로컬 개발 서버입니다. 가상 인맥 5명과 경조사·금액 기록을 서버 메모리에서 읽습니다. 날짜는 실행 시점의 서울 날짜를 기준으로 만들어집니다. 기존 브라우저의 인맥·금액·로그인 데이터를 읽거나 업로드하지 않습니다.

기본 `AI_PROVIDER=mock`는 외부 AI 호출과 비용이 없습니다. 실제 생성형 AI를 흉내 내는 규칙 응답이며, 사용자가 추가한 로컬 기록과 별개입니다. 실사용자 인증·DB 저장·영구 대화 이력·앱 종료 후 푸시는 이번 서버의 범위에 포함되지 않습니다.

## 설치와 실행

프로젝트 루트 `maeum`에서 PowerShell로 실행합니다. Python 3.11 이상을 사용하며 이 작업은 Python 3.14에서 확인했습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

실행 후 API 문서는 `http://127.0.0.1:8000/docs`, 상태 확인은 `http://127.0.0.1:8000/api/health`입니다. 종료는 실행 중인 터미널에서 `Ctrl+C`를 누릅니다. DB가 없어도 전체 모의 흐름을 실행할 수 있습니다.

## API 계약

| 경로 | 역할 |
| --- | --- |
| `GET /api/health` | `{status, provider, dataSource}` 서버 상태 |
| `GET /api/demo/context` | 서버의 가상 인맥 목록과 오늘 날짜·응답 제공자 |
| `POST /api/ai/advice` | 선택한 인맥의 기록을 바탕으로 응답 |

```json
{"question":"김도윤 결혼식에 얼마를 준비할까요?","mode":"금액 참고","personId":"p1"}
```

`mode`는 `금액 참고`, `참석 대응`, `메시지 작성`, `우선순위` 중 하나입니다. 질문은 공백 제외 1~1,000자이며, 질문에 명시된 도움 의도가 선택 모드보다 우선합니다. `eventId`는 선택한 인맥에 연결된 특정 행사를 참고할 때만 선택적으로 보냅니다. 인맥과 일정 ID는 `/api/demo/context` 및 서버 저장소의 ID 기준입니다. 임의의 `records`, `amount`, `userId` 등은 요청에 넣을 수 없습니다.

응답은 기존 대화창과 호환되는 `title`, `text`, `evidence`, `suggestions`, `isMessage`와 `provider`, `dataSource:'mock'`, `demo:true`를 포함합니다. 근거가 있을 때만 `amount`가 포함됩니다. 인맥을 찾지 못하면 404, 입력이 잘못되면 422이며 `{error:{code,message,fields?}}`로 안내합니다.

가상 데이터:

- `p1` 김도윤: 친구·매우 중요, 결혼식, 과거 받은 10만 원
- `p2` 윤서진: 가족·중요, 돌잔치, 과거 받은 20만 원
- `p3` 이수현: 거래처·중요, 결혼식 불참, 같은 유형에 보낸 10만 원
- `p4` 박서연: 직장동료·중요, 다음 날 부친상, 과거 받은 10만 원
- `p5` 한지우: 동호회 선배·보통, 생일, 금액 이력 없음

우선순위는 조사 → 가까운 날짜 → 같은 날에는 중요도 순으로 정합니다. 중요도만으로 금액을 올리지 않습니다. 다른 행사 유형에서 받은 금액은 유형 차이를 함께 안내합니다.

## 선택: 실제 OpenAI 응답

모의 구현 검증에는 필요하지 않습니다. 실제 AI를 사용할 때만 `backend/.env.example`을 `backend/.env`로 복사하고 다음 서버 설정을 입력한 뒤 서버를 다시 실행합니다.

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=서버에서만_관리할_API_키
OPENAI_MODEL=사용할_수_있는_모델_ID
AI_TIMEOUT_SECONDS=25
```

모델 ID는 사용하는 API 프로젝트에서 사용할 수 있는 값을 지정합니다. 키와 모델이 없으면 서버가 설정 오류로 중지되며, 자동으로 모의 응답으로 바뀌지 않습니다. `backend/.env`는 Git에 포함하지 않습니다. AI 키를 프론트의 `VITE_*`에 넣지 않습니다.

`OpenAIProvider`는 [공식 Responses API 흐름](https://developers.openai.com/api/docs/quickstart)에 맞춰 서버에서 요청합니다. 질문과 해당 인맥의 선택된 가상 근거·참고 답변을 보내고 `store:false`를 지정합니다. 금액·근거·제목은 서버에서 결정하고 모델은 설명 또는 메시지 본문을 작성합니다. 실제 AI 문장은 검토가 필요하며, 기록 없는 사실을 만들어 내지 않도록 지시합니다. 인증 실패·시간 초과·사용량 제한은 오류로 반환하고 성공한 모의 응답으로 숨기지 않습니다.

실제 AI API 호출은 API 키 없이 수행할 수 없으므로 이번 검증은 모의 전송으로 요청 구조와 오류 처리를 확인했습니다.

## 나중에 DB 연결할 위치

`backend/repository.py`의 `WorkspaceRepository.snapshot(today)`가 데이터 조회 경계이며 `get_repository` 의존성을 통해 사용합니다. `MockWorkspaceRepository`를 DB 구현으로 교체하면 경로와 프론트 응답 형식을 유지할 수 있습니다. 현재 `dataSource:'mock'` 표시는 실제 저장소 연결 후 서버·프론트 양쪽에서 갱신해야 합니다.

실제 DB 전환 때는 먼저 서버 인증을 추가하고, 검증된 세션의 사용자 ID를 repository에 전달해 본인 기록만 조회해야 합니다. 현재 데모에는 인증이 없으므로 실사용자의 기록을 넣거나 공개 서비스로 노출하는 용도로 사용하지 않습니다. CORS는 인증을 대신하지 않으며, 기본 실행 주소는 로컬 PC의 `127.0.0.1`입니다. 샘플 데이터를 실제 계정으로 자동 이전하지 않습니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

테스트는 네트워크 없이 가상 데이터·가짜 AI 전송으로 실행합니다. 4가지 도움 유형, 실제 근거 금액, 기록 부재, 입력 오류, ID 검증, CORS 허용 출처, 저장소 교체, AI 인증/사용량/시간 초과와 불완전 응답을 확인합니다.

`backend/app.py`는 `create_app(settings, repository, provider)`를 제공하며 테스트에서는 [FastAPI 의존성 교체](https://fastapi.tiangolo.com/advanced/testing-dependencies/)로 저장소와 오늘 날짜를 바꿀 수 있습니다. CORS는 `CORS_ORIGINS`에 명시한 개발 출처만 허용합니다.

기존 Sites 주소는 정적 React 배포입니다. 이 Python 프로세스가 그 주소에서 실행되는 것은 아닙니다. 실제 서버를 배포할 때는 Python 실행 환경에 FastAPI를 별도로 배포하고 프론트의 서버 주소와 허용 출처를 맞춰야 합니다.
