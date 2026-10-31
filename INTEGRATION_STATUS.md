# RAG + React 통합 (개발 중)

현재 이 브랜치는 **v4 백엔드 이식과 자동 테스트까지 완료된 부분 통합** 상태입니다. 최종 Windows 실브라우저 E2E와 전체 DB 일원화는 아직 완료되지 않았습니다. 발표 운영서는 [docs/PRESENTATION_DEMO.md](docs/PRESENTATION_DEMO.md)를 참고하세요.

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

- **v4 핵심 모듈과 공식 근거/합성 데이터 이식 완료**. 다만 두 서비스의 데이터 계약 완전 일원화 미완료
- 브라우저 localStorage의 인맥·일정·장부 CRUD를 서버 단일 저장소로 동기화
- **v4 자기신고 직업·기관·담당 업무/상대 직업 이용 동의 시연은 구현**. React 회원가입 단계의 직업 필수 입력은 미완료
- v4 RAG 통계·개인화 금액, 법적 위험 시 보류는 구현됨. 실서비스 데이터 없는 신규 가입자에 대한 전체 UX는 미완료
- 다중 턴 선택지와 서버 상태 전이를 실제 모델·자동 테스트로 검증
- GitHub CI React 빌드·테스트, Python pytest **155 PASS**. 발표자 PC 브라우저 E2E 및 실제 모델 실호출 미실행

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

**검증 갱신(2026-10-31):** GitHub Actions에서 Python 155 PASS + subtest 7 PASS(경고 1개), React 테스트 및 빌드 PASS. Windows 브리지 Docker는 연결되었고 의존성 없는 이미지에서 소스 테스트 8 PASS. **Windows 기능 테스트/실브라우저 E2E/실제 모델 호출은 미검증**. 이식된 v4 원본에는 약 84개 테스트 메서드가 있었으나 통합 저장소의 155개 회귀 테스트 전체 통과와 구분한다.

**기술 부채:** /v4의 원본 데모 데이터와 채팅/React 워크스페이스의 합성 자료가 아직 단일 CRUD 원천으로 합쳐지지 않았다. v4 화면은 React 네이티브 컴포넌트가 아닌 별도 프레임이다. 프로덕션 인증/법적 적법성 검증이 없다. 질문 원문 저장은 채팅 기능에 적용되며, 직무 관계 자유서술의 원문 비저장 정책과 별도로 개인정보 고지 및 서버 필터가 필요하다.
