# RAG + React 통합 (개발 중)

현재 원격 **`develop`에는 PR #3이 병합되었으며**, v4 백엔드 이식과 자동 테스트까지 완료된 부분 통합 상태입니다. 최종 Windows 실브라우저 E2E와 전체 DB 일원화는 아직 완료되지 않았습니다. 발표 운영서는 [docs/PRESENTATION_DEMO.md](docs/PRESENTATION_DEMO.md)를 참고하세요.

## 로컬 실행

1. 저장소 루트에서 `develop` 최신 코드를 사용합니다. 가상환경은 저장소 밖에 만들고 의존성을 설치합니다. Windows/macOS 별 실행 명령은 [README.md](README.md)를 참조하세요.
2. 서버: `python -m uvicorn gyeongjosa_ai.api:app --host 127.0.0.1 --port 8000`.
3. `frontend/`에서 `pnpm install` 후 `pnpm dev` 실행.
4. 브라우저: http://127.0.0.1:5173 ; AI 메뉴에서 가상 계정 선택.
5. Codyssey 실모델 검증은 별도의 로컬 `.env` 키 설정이 필요합니다. 키를 커밋하지 마세요.

**주의:** 프론트의 기존 `dev:demo`는 별도 모의 FastAPI를 실행하도록 작성되어 있어 이 브랜치의 통합 실행에 사용하지 않습니다.

## 이번 작업

- `frontend/`에 기존 React 소스와 스타일을 원형 보존 이식
- 단일 FastAPI에 가상 계정 목록, 읽기 전용 공유 부고, 워크스페이스 API 추가
- SQLite 계정별 대화 생성·복원·삭제·추가 턴 저장 API
- AI 메뉴를 자연어 자유 입력/대화 복원 UI로 전환
- 공유 허용 부고는 상단 알림함의 공유 소식 카드로 제공 (일정 상단 패널에서 이동)
- 기본 API 회귀 테스트 추가

## 남은 필수 작업 (현재 미완료)

- **v4 핵심 모듈과 공식 근거/합성 데이터 이식 완료**. 다만 두 서비스의 데이터 계약 완전 일원화 미완료
- 브라우저 localStorage의 인맥·일정·장부 CRUD를 서버 단일 저장소로 동기화
- **v4 자기신고 직업·기관·담당 업무/상대 직업 이용 동의 시연은 구현**. React 회원가입 단계의 직업 필수 입력은 미완료
- v4 RAG 통계·개인화 금액, 법적 위험 시 보류는 구현됨. 실서비스 데이터 없는 신규 가입자에 대한 전체 UX는 미완료
- 다중 턴 선택지와 서버 상태 전이를 실제 모델·자동 테스트로 검증
- GitHub CI React 빌드·테스트, Python pytest **161 PASS**. 발표자 PC 브라우저 E2E 및 실제 모델 실호출 미실행

## 보안

가상 계정 선택 헤더는 실제 인증이 아닙니다. 로컬 시연에서만 사용하며 외부에 서버를 공개하지 마세요. 본 통합 브랜치에 실사용 개인정보를 적재하지 마세요.

## 2026-10-31 v4 이식 당시 기록 (단일화 이전)

- 원본: Windows 브리지 `Documents/Codex/proto_rag_llm`. GitHub `app/` 모듈 10개는 이 원본에서 이식됨
- 원본 데이터: `data/knowledge_base.json`, `legal_rules.json`, `original_demo.json`, `person_policy_profiles.json`
- 기존 v4 테스트 5개 파일을 `tests/`에 이식함
- 기존 서버 `gyeongjosa_ai.api:app`에서 `/v4`에 v4 FastAPI 앱을 마운트함
- React AI 페이지에서 **AI 자유 상담** / **v4 직무·법적 위험 분석** 전환 버튼 제공. 후자는 프레임에 `/v4/` 별도 화면을 표시하므로 React CSS와 독립적임
- Vite는 `/v4`와 `/api` 모두 127.0.0.1:8000에 프록시함
- v4 공개 화면/API: `/v4/`, `/v4/api/health`, `/v4/api/recommend`, `/v4/api/demo/onboarding`
- 실행: `python -m uvicorn gyeongjosa_ai.api:app --host 127.0.0.1 --port 8000`, 별도 터미널 `cd frontend && pnpm install && pnpm dev`

### 통합 시연 게이트

1. Python: `python -m unittest discover -s tests -v` 및 `python -m pytest -q`
2. React: `cd frontend && pnpm install && pnpm test && pnpm build`
3. 브라우저: 마음결 AI 자유 상담만 표시되고, 독립 `/v4/` 경로는 제공되지 않음
4. 합성 시나리오: 30,000원 예산 상한, 공직자/계약 심사 위험 보류, 비동의 직업 차단, 동명이인 확인, 공유 부고 권한 분리
5. 실모델 키 없는 실패 시 가짜 법적 판정 금지, 프라이버시 Opt-in 강제

**검증 갱신(2026-10-31):** [병합 전 최종 GitHub Actions](https://github.com/2026-hackaton-team/hackaton-ai-service/actions/runs/41158428848)에서 Python 161 PASS(경고 1개), React 테스트 및 빌드 PASS. Windows 브리지 Docker는 연결되었고 의존성 없는 이미지에서 소스 테스트 8 PASS. **Windows 기능 테스트/실브라우저 E2E/실제 모델 호출은 미검증**. 이식된 v4 원본에는 약 84개 테스트 메서드가 있었으나 통합 저장소의 155개 회귀 테스트 전체 통과와 구분한다.

**기술 부채:** 원본 데모 데이터와 채팅/React 워크스페이스의 합성 자료가 아직 단일 CRUD 원천으로 합쳐지지 않았다. 독립 v4 분석 화면은 제거했고 정책·추천 모듈만 재사용한다. 프로덕션 인증/법적 적법성 검증이 없다. 질문 원문 저장은 채팅 기능에 적용되며, 직무 관계 자유서술의 원문 비저장 정책과 별도로 개인정보 고지 및 서버 필터가 필요하다.

## 자유 상담 단일화 후 현재 상태

- React AI 화면은 하나이며, 20개 합성 시나리오를 대화 API에서 처리한다. `/v4/` 외부 마운트와 iframe을 제거했다.
- 친밀도·최근 수령액·관계 변화는 개인화 후보 순위에 반영하고 원래 기준액과 조정 사유를 표시한다.
- 인간관계 연구자료 6개는 RAG 설명용이며 통계적 적정 금액으로 환산하지 않는다.
- 일반 자유 대화의 실모델 응답 품질, 프론트 전체 CRUD의 서버 단일 원천화, 사용자 직업 설정 UX, 브라우저 E2E는 별도 검증·개발 대상이다.
- GitHub PR #15의 자동 회귀 검증과 실제 Windows 최종 시연을 구분해 보고한다.
