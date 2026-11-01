# 마음결 문서 안내

> 기준: 2026-11-01, GitHub `develop`의 통합 React + FastAPI 시연 앱. 이 목록은 **현재 사용 문서**와 **작성 당시 기록**을 구분합니다. 구현의 실제 동작은 코드와 테스트, 실행 중 API 응답으로 최종 확인합니다.

## 현재 실행·시연 문서

| 문서 | 사용 목적 |
|---|---|
| [README](../README.md) | 설치·실행·API·테스트 시작점 |
| [WORKSPACE_STORAGE](WORKSPACE_STORAGE.md) | 서버 SQLite 인맥·일정·장부의 단일 원천 계약 |
| [DEMO_POPULATION](DEMO_POPULATION.md) | `test1234`, `test12345`, `testbridge` 시연 자료 준비 및 확인 |
| [TEST1234_DEMO_SCENARIOS](TEST1234_DEMO_SCENARIOS.md) | 로그인 계정의 일반 채팅 시나리오 20개 |
| [PRE_DEMO_CHAT_AI_CHECKLIST](PRE_DEMO_CHAT_AI_CHECKLIST.md) | AI 응답 상태·오류·예산·모델 검증 점검 |
| [PRESENTATION_DEMO](PRESENTATION_DEMO.md) | 발표 시연 순서와 발표 직전 확인 항목 |
| [KIM_SCENARIO_LAB](KIM_SCENARIO_LAB.md) | 개인화 추천 사례 평가 설계 |
| [SCENARIO_CATALOG](SCENARIO_CATALOG.md) | SQLite 시드에 보존된 80개 시나리오의 **테스트 계약** (실제 모델 검증 결과 아님) |
| [모델 평가 기록](../evaluation/review.md) | 당시 실제 모델 호출 기록과 평가 한계 |
| [CONTRIBUTING](../CONTRIBUTING.md) | 협업·PR·커밋 관례 |

## 과거 자료

[archive/README](archive/README.md)에 초기 통합 현황, JSON 기반 구현계획, 서버 연동 준비 문서, 초기 FastAPI 모의 데모, 실서비스 전환 검토 등 보관 문서 7개를 분리했습니다. **이 자료에 적힌 실행 명령이나 `현재` 상태를 최신 안내로 사용하지 마세요.**

## 보존하지만 일반 실행에서 사용하지 않는 구성

- `data/json_backup/`: SQLite 시드 재생성과 테스트를 위한 원본 보관. 현재 앱은 `data/gyeongjosa_seed.sqlite3`을 읽습니다. 백업을 임의로 삭제하지 않습니다.
- `web/index.html`: FastAPI의 `/` 경로에서 제공하는 독립 확인 화면. React의 기본 진입점과 다릅니다.
- `v4_demo_frontend/`: `app/main.py`의 독립 정책 데모에서 사용합니다. React의 `IntegratedAIPage.jsx`와 구분하며, 함부로 삭제하지 않습니다.
- `frontend/scripts/setup-demo.mjs`, `frontend/scripts/dev-demo.mjs`, `frontend/package.json`의 `test:backend`: 초기 `backend/` 경로를 참조해 현재 구조에 맞지 않는 **구버전 실행 항목**입니다. 이번 문서 정리에서 실행 코드는 변경하지 않았으며, [README](../README.md)의 현재 실행·테스트 명령을 사용합니다.
- `frontend/src/AIPage.jsx`: 예전 AI 화면 코드가 남아 있으나 현재 `App.jsx`의 AI 진입점은 `IntegratedAIPage.jsx`입니다. 참조·테스트 확인 전 임의 삭제하지 않습니다.

## 변경 시 주의 사항

- 문서를 이동할 때 기존 문서 링크와 테스트의 경로 참조를 함께 확인합니다. 특히 `SCENARIO_CATALOG.md`는 테스트에서 직접 읽습니다.
- 문서에 기록된 테스트 통과 수·LLM 검증·브라우저 시연 결과는 **해당 날짜의 이력**입니다. 최신 실행으로 간주하지 않습니다.
- 보관 문서와 현재 안내가 충돌하면 `README.md`, `WORKSPACE_STORAGE.md`와 실제 코드·테스트를 우선 확인합니다.
