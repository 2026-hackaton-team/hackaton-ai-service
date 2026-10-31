# RAG + React 통합 (개발 중)

현재 이 브랜치는 **부분 통합** 상태입니다. 완전한 E2E 또는 최종 v3 직무 관련성 적용을 완료했다고 간주하지 마세요.

## 로컬 실행

1. 저장소 최상위에서 Python 가상환경을 만들고 `pip install -r requirements.txt`.
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
- 일정에 공유 허용 부고 추천 패널 추가
- 기본 API 회귀 테스트 추가

## 남은 필수 작업 (현재 미완료)

- Google Drive 동기화 목록에 별도로 검색되지 않는 로컬 `proto_rag_llm` 최신 직무 관련성·통계 RAG 소스 대조 및 이식
- 브라우저 localStorage의 인맥·일정·장부 CRUD를 서버 단일 저장소로 동기화
- 직업 필수 입력 및 상대방 직업 공개 동의 정책
- 공개 통계 참고 금액(개인 거래 없음)과 법적 위험 시 중단
- 다중 턴 선택지와 서버 상태 전이를 실제 모델·자동 테스트로 검증
- 통합 React 빌드, Python pytest, 브라우저 E2E, 모델 실호출 모두 미실행

## 보안

가상 계정 선택 헤더는 실제 인증이 아닙니다. 로컬 시연에서만 사용하며 외부에 서버를 공개하지 마세요. 본 통합 브랜치에 실사용 개인정보를 적재하지 마세요.

## 2026-10-31 v4 실소스 추가 반영

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
3. 브라우저: AI 자유 상담과 v4 정책 화면 모두 열림, `/v4/api/health.policy_engine=v4`
4. 합성 시나리오: 30,000원 예산 상한, 공직자/계약 심사 위험 보류, 비동의 직업 차단, 동명이인 확인, 공유 부고 권한 분리
5. 실모델 키 없는 실패 시 가짜 법적 판정 금지, 프라이버시 Opt-in 강제

**미검증:** 원격 GitHub write 및 코드 소스 비교는 확인했으나, 이 실행 환경에서는 실제 Windows 브라우저·Python/Node 프로젝트 실행 검증을 수행하지 못했다. Windows 브리지 테스트는 `PINNED_DOCKER_IMAGE_MISSING`으로 실패했다. `80/80`은 과거 보고이며 현재 소스는 테스트 메서드 84개가 정의되어 있다. 본 PR을 검증 완료로 간주하지 말 것.

**기술 부채:** /v4의 원본 데모 데이터와 채팅/React 워크스페이스의 합성 자료가 아직 단일 CRUD 원천으로 합쳐지지 않았다. v4 화면은 React 네이티브 컴포넌트가 아닌 별도 프레임이다. 프로덕션 인증/법적 적법성 검증이 없다. 질문 원문 저장은 채팅 기능에 적용되며, 직무 관계 자유서술의 원문 비저장 정책과 별도로 개인정보 고지 및 서버 필터가 필요하다.
