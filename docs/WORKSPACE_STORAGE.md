# 인맥·일정·장부 SQLite 단일 원천

> 해커톤 로컬 시연용 계약입니다. 로그인한 계정은 하나의 서버 사용자 ID(회원은 `ACC:아이디`, `test1234`는 `TEST1234`)를 쓰며, React의 인맥·일정·장부와 AI 자유 상담은 같은 SQLite 작업공간을 참조합니다. 로그아웃 상태에서는 어떤 개인 기록도 화면에 보이지 않습니다.

## 사용 방법

1. 서버와 프런트를 함께 실행하고 회원가입하거나 로그인합니다. `test1234`는 첫 로그인 때 서버가 계정을 만듭니다. 별도 AI 프로필 선택은 필요하지 않습니다.
2. `test1234`는 첫 사용 시 기존 22개 상담용 인맥·거래·일정을 한 번만 저장하고, 새 일반 계정은 빈 작업공간으로 시작합니다. 발표용 `python -m gyeongjosa_ai.demo_population` 명령을 별도로 실행하면 78명의 인맥을 추가하고 `test12345`·`testbridge` 시연 계정의 2촌 공유 관계를 구성합니다. 이미 수정한 기록은 덮어쓰지 않습니다.
3. 인맥·일정·장부 저장은 버전 조건에 따른 하나의 SQLite 트랜잭션으로 완료됩니다. 충돌 시 다른 사용자의 기록을 덮어쓰지 않습니다.
4. 초기화 이후 인맥·일정·장부 조회와 편집·CSV 가져오기·삭제는 서버를 기준으로 합니다. 서버 저장이 성공한 뒤에만 화면 상태가 갱신됩니다.
5. 같은 로그인 계정으로 다시 접속하면 서버에 저장된 데이터를 읽습니다. 서버 충돌(HTTP 409) 시 최신 상태를 다시 조회하고 실패한 저장은 자동 재적용하지 않습니다.

## API와 계산 경로

- `POST /api/auth/signup`·`/login`·`/logout`, `GET·PUT /api/auth/me`: 계정과 HttpOnly 세션 쿠키. 응답의 `userId`가 서버 사용자 ID
- `GET·PUT /api/account/social`, `GET·PATCH /api/account/preferences`, `POST /api/account/read`·`/delivered`: 친구·공유 일정·화면 설정·알림 기록 (로그인 필요)
- `GET /api/workspace/personal`: 로그인 계정의 현재 서버 인맥·일정·장부 및 버전 조회
- `POST /api/workspace/migrations/preview`: 이전 대상의 유효성·버전 확인, 저장하지 않음
- `PUT /api/workspace/personal`: 동일 버전의 전체 자료를 원자적으로 교체
- `POST /api/conversations/{conversation_id}/messages`: 실제 자유 상담은 위 작업공간을 변환한 개인화 데이터로 추천 엔진을 호출함
- 법률·관계 합성 시나리오(`가상 시나리오`)는 시연용 고정 데이터로 분리되어 있습니다.

친밀도(`closeness_score`, 1~5점 또는 미기록)와 중요도(`importance`)는 **서로 다른 속성**입니다. 중요도를 임의의 친밀도 점수로 변환하지 않습니다. '특별히 챙길 사람'(`special`)도 서버에 저장되어 개인화 참고 요인으로 전달됩니다. 지급·수령 거래는 인물 ID와 행사 ID를 명시적으로 연결하며, 추천 엔진은 관련 거래 내역과 예산·RAG·법률 정책을 별도로 적용합니다. 본인 행사에는 허구의 상대방을 보이지 않게 하는 내부 참조 ID를 사용합니다.

## 제약·안전

- 프런트는 로그인·인맥·일정·장부·친구·공유·화면 설정을 `localStorage`나 `sessionStorage`에 저장하지 않습니다. 로그인을 유지하는 브라우저 쿠키는 세션 식별자만 보관하고 서버가 SQLite에서 사용자 기록을 관리합니다.
- 로그인하지 않은 상태에서는 서버 개인 기록을 저장할 수 없습니다. 시연 중 서로 다른 로그인 계정으로 데이터를 이전하지 않도록 확인해야 합니다.
- 시연 로그인은 서버 세션 쿠키를 사용합니다. 레거시 `X-Demo-User-Id` API는 실제 서비스에 필요한 완전한 권한 검증이 아닙니다. 실제 개인정보·실제 금액을 입력하거나 외부에 서버를 공개하지 마세요.
- 가상 계정을 초기화하면 해당 계정의 개인 합성 데이터는 일반 자유 상담에서 서버 작업공간 데이터로 대체됩니다. 고정 시나리오는 별도 실행됩니다.
- 로그인·친구 요청·브라우저 수신 처리·테마·알림은 서버 사용자 상태 SQLite에 저장하고, 기존 개인 작업공간·대화 및 JSON에서 옮긴 정적 시드 DB는 유지합니다. SQLite 파일이 여러 개일 수 있으나 실행 중 브라우저 저장소를 개인 데이터의 원천으로 사용하지 않습니다.

## 검증

`python -m pytest -q tests/test_workspace_single_source.py tests/test_demo_login_identity.py tests/test_demo_server_state.py tests/test_accounts.py`와 `cd frontend && corepack pnpm test && corepack pnpm build`를 실행합니다. 409 충돌, 다른 계정 접근, 잘못된 행사 연결, 1~5점 범위, 본인 행사, 거래 누락을 검사합니다. 최종 Windows/macOS 브라우저 E2E 및 실제 Codyssey LLM 호출은 별도로 확인해야 합니다.
