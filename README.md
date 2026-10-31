# 마음 잇기 AI — 가상 경조사 시제품

가상 사용자와 지인의 경조사 기록, 공유된 부고를 바탕으로 이력 조회·금액 선택지·참석 조언·인사말 초안을 확인하는 로컬 시제품입니다. 자연어 질문은 모델이 분류하며, 직접 친구와 친구의 친구 중 공유와 참석이 명시적으로 허용된 부고만 추천합니다.

**현재 상태:** 가상 데이터, Python AI 모듈, FastAPI 연결과 최소 웹 화면이 있습니다. 계정 전환은 시연용이며 실제 로그인·운영 보안·팀 DB 통합은 구현하거나 검증하지 않았습니다. 시연 기준일은 **2026-10-30**으로 고정돼 있습니다.

**모델과 데이터:** 사용자의 질문, 선택한 가상 계정의 지인 목록과 조회 가능한 소식, 답변에 필요한 개인 이력이 코디세이 API로 전송됩니다. 모든 제공 데이터는 허구입니다. 기본 모델은 `claude-opus-4-8`, 실패 시 `gpt-5.4`입니다. 모델 호출은 사용량이나 비용이 발생할 수 있으며 코디세이의 실제 이용 조건은 확인이 필요합니다.

## 시작하기

Windows PowerShell에서 현재 작업 폴더의 `gyeongjosa-ai-prototype`으로 이동합니다. Python 3.12 환경에서 확인했습니다. 가상환경은 프로젝트 밖의 사용자 지정 공용 위치에 만듭니다.

```powershell
Set-Location .\gyeongjosa-ai-prototype
$venv = Join-Path $env:USERPROFILE 'Documents\Codex\venvs\gyeongjosa-ai-prototype'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { python -m venv $venv }
& $python -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
```

프로젝트의 `.env`를 직접 열어 `CODYSSEY_API_KEY`에 발급받은 키를 설정합니다. 기존 `.env`는 위 명령으로 덮어쓰지 않습니다. 키를 채팅, 코드, 스크린샷이나 공개 저장소에 넣지 마세요. `.env`는 `.gitignore`에 포함돼 있습니다.

```powershell
& $python -m uvicorn gyeongjosa_ai.api:app --host 127.0.0.1 --port 8765
```

브라우저에서 `http://127.0.0.1:8765/`를 엽니다. `윤서진 (U001)`을 선택하면 `N001`·`N002` 부고가 보입니다. 예를 들어 “해든기획팀 김도윤과 주고받은 기록을 알려줘”라고 입력하면 받은 100,000원과 낸 50,000원의 기록 및 근거를 확인하는 흐름입니다. 실제 모델 응답은 매번 달라질 수 있습니다.

`U012`에서는 허용된 직접 친구 부고와 친구의 친구 부고를 함께 확인할 수 있습니다. 화면에서 부고를 선택하고 관련 질문을 한 뒤, 상주와 지인이 같은 사람인지 사용자가 직접 확인합니다.

부고를 선택하면 모델을 호출하지 않고 상주·공유자 관계·가상 장소·조문 시간과 미기록 항목을 먼저 볼 수 있습니다. `N001`의 상주 이름은 지인 두 명과 같으므로 소속을 비교한 뒤 직접 확인합니다. `N002`는 소속과 장소가 없는 사례입니다. 상주와 같은 지인을 알 수 없다면 **모르겠어요** 또는 **해당 지인이 없어요**를 선택하면 개인 거래를 연결하지 않고 금액 제안을 보류합니다.

최대 예산을 묻는 질문에 `없어`라고 답하면 예산 미정인지 지출이 어려운 상황인지 선택할 수 있습니다. 미정을 선택하면 확인된 거래 이력만 보여주고 구체적인 금액 제안은 보류합니다. 지출이 어렵거나 예산이 0원인 경우 지출을 권하지 않습니다. 이후 실제 예산을 입력하면 기존 금액 제안 흐름을 사용할 수 있습니다.

서버 상태만 별도 터미널에서 확인하려면 다음을 실행합니다. 이 응답은 실제 모델 연결의 성공을 뜻하지 않습니다.

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

기대 결과는 `status`가 `ok`, 사용자 수가 111, 기준일이 `2026-10-30`인 JSON입니다.

## 팀 연동 인터페이스

시제품 서버의 요청·응답 명세는 서버 실행 후 `http://127.0.0.1:8765/docs`에서 확인할 수 있습니다. 현재 팀의 DB 스키마와 최종 API 경로는 아직 공유되지 않아 이 인터페이스는 인계용 초안입니다.

| 기능 | 경로 | 설명 |
|---|---|---|
| 가상 계정 | `GET /api/users` | 시연에서 선택할 수 있는 111개 계정 |
| 개인 지인 | `GET /api/users/{user_id}/people` | 해당 가상 계정의 지인 |
| 부고 추천 | `GET /api/users/{user_id}/notices` | 허용된 부고, 관계 유형, 공통 친구 수와 점수 |
| 개인 합계 | `GET /api/users/{user_id}/dashboard` | 해당 가상 계정의 받은·낸 금액과 건수 |
| 자연어 대화 | `POST /api/chat` | 질문 분류, 추가 질문, 답변·근거·사용 모델 |

대화 요청 예시:

```powershell
$body = @{ user_id = 'U001'; question = '해든기획팀 김도윤과 주고받은 기록을 알려줘'; context = @{} } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/chat' -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

대화 결과의 `status`는 `answer`, `need_more_info`, `out_of_scope`, `error`로 구분합니다. `context`와 `pending_field`는 추가 질문을 이어갈 때 사용합니다. 근거는 `evidence`, 모델이 인용한 ID는 `cited_ids`, 질문 분류와 답변에 실제 사용한 모델은 `classification_model`과 `model`로 반환합니다.

팀 백엔드에 붙일 때는 `gyeongjosa_ai.service.ChatService`의 처리 흐름과 `gyeongjosa_ai.ai.ModelGateway`를 참고할 수 있습니다. 실제 서비스에서는 브라우저에서 받은 `user_id`를 신뢰하지 말고, 백엔드가 인증된 사용자와 DB의 소유·공유 권한을 확인해야 합니다. 현재는 JSON 전체를 서버 측 시드로 사용하며 데이터베이스와 연결하지 않았습니다.

## 데이터와 추천

- [원본 사본](data/original_demo.json)은 기존 데이터의 복사본이고, [시연 데이터](data/demo.json)는 여기에 가상 가입자 100명과 독립적인 관계망·기록을 추가한 파일입니다.
- 추가 사용자별로 지인 3~8명과 행사 2~10건을 생성했습니다. 직접 친구 참석 허용값이 없는 기존 소식은 허용으로 추정하지 않습니다.
- 추천은 수락·추천 활용이 허용된 관계, 공유 범위·공유 승인·해당 관계의 참석 허용, 행사 상태를 확인한 뒤 공통 친구·지역·관심 종류·날짜를 `40:30:20:10`으로 계산합니다.
- [생성기](gyeongjosa_ai/generate_data.py)는 고정 시드와 직접 작성한 가상 표현을 사용하며 외부 API를 호출하지 않습니다. 작업용 부고의 장소·주소·빈소·조문 시간은 실제 위치가 아닌 가상 값이며, 일부는 미기록으로 남겼습니다. 공유자 이름은 시연용 공개 설정이 명시된 소식에만 표시합니다. 기존 `data/demo.json`이 있으면 기본 실행으로 덮어쓰지 않습니다. `--force`는 작업용 데이터를 명시적으로 덮어쓰므로 필요한 경우 기존 파일을 먼저 보관하세요.
- `data/demo.json`에는 여러 가상 계정과 비공개 소식도 들어 있습니다. 화면에는 조건을 통과한 결과만 반환하지만, 이 구조는 실제 개인정보를 넣는 운영 저장소가 아닙니다.

## 검증과 한계

별도 PowerShell에서 테스트하려면 다음을 실행합니다.

```powershell
$python = Join-Path $env:USERPROFILE 'Documents\Codex\venvs\gyeongjosa-ai-prototype\Scripts\python.exe'
$testBase = Join-Path (Get-Location) ('.pytest-tmp-' + [guid]::NewGuid().ToString('N'))
& $python -m pytest tests -q -p no:cacheprovider --basetemp $testBase
```

테스트가 만든 `.pytest-tmp-*` 폴더는 Git 제외 대상이며 확인 후 직접 정리할 수 있습니다. 2026-10-31 부고와 예산 답변 흐름을 보완한 뒤 데이터 참조·권한·점수·추가 질문·모델 대체·API 자동 테스트 **66개가 통과**했습니다. 실제 서버의 시작·상태·부고 조회를 확인했고, 보완 후 Chromium 대화 화면은 **모델 대역을 사용해** 확인했습니다. 실제 모델 비교와 발견된 오류, 보완 후 미검증 항목은 [검토 기록](evaluation/review.md)에 있습니다.

실제 검증 요청은 중단된 시도까지 보수적으로 포함해 처음 허용된 50회와 추가 승인 12회, **총 62회 한도에 도달**했습니다. `evaluation/budget.json`에 검증 횟수를 보관하며 `python -m gyeongjosa_ai.evaluate`는 한도에 도달하면 추가 요청을 막습니다. 일반 웹 대화는 이 평가 기록과 별개로 실제 API를 호출하므로, 사용자가 직접 질문하면 추가 사용량이 발생할 수 있습니다.

Opus와 GPT의 비교에서 거래 인용과 행사 주체에 관한 오류를 발견해 프롬프트와 전달 정보를 보완했습니다. 금액 기능의 기록 요약은 확인된 데이터로 만들고 AI 제안 금액을 별도로 표시합니다. **마지막 보완 후 실제 모델 재호출은 한도 때문에 수행하지 않았습니다.** 모델 응답의 모든 의미적 오류를 자동 검사할 수 없으며, 실제 서비스 적용 전 추가 검토가 필요합니다.

## 외부 자원과 인계 자료

| 구분 | 명칭 | 용도 | 라이선스·이용 조건 |
|---|---|---|---|
| 오픈소스 | FastAPI | 시연 HTTP API | MIT |
| 오픈소스 | Pydantic | HTTP 요청 검증 | MIT |
| 오픈소스 | Uvicorn | 로컬 ASGI 서버 | BSD-3-Clause |
| 오픈소스 | HTTPX | 코디세이 API 호출 | BSD-3-Clause |
| 오픈소스 | python-dotenv | 로컬 환경설정 읽기 | BSD-3-Clause |
| 오픈소스 | pytest | 자동 검증 | MIT |
| 외부 API | 코디세이 게이트웨이의 Claude Opus 4.8, GPT-5.4 | 질문 분류와 답변 생성 | 코디세이 이용 조건 확인 필요 |

위 오픈소스 라이선스는 현재 환경의 패키지 메타데이터에서 확인했습니다. 대회 제출 전 실제 사용한 버전과 이용 조건을 팀이 다시 확인해야 합니다. 프로젝트 자체의 라이선스는 아직 정해지지 않았습니다.

구체적인 설계와 작업 순서는 [구현계획](implementation_plan.md)을 참고하세요.
