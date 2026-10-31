# 마음결 백엔드 연결 준비

현재 일반 인맥·일정·금액 저장은 브라우저 내부 저장 방식입니다. **AI에 한해 FastAPI와 서버 가상 데이터의 HTTP 연결을 구현했습니다.** [FastAPI 데모 안내](FASTAPI_DEMO.md)를 먼저 참고하세요. 기본 응답은 모의이며 서버 설정으로 OpenAI를 선택할 수 있습니다. 실제 키 호출은 검증하지 않았습니다. DB·실제 사용자 인증·앱 종료 후 알림은 남아 있습니다. 아래 일반 CRUD API는 백엔드 개발자와 맞출 **제안 계약**이며, 현재 실행 가능한 AI 경로는 `/api/ai/advice`와 `/api/demo/context`, `/api/health`입니다.

## 이번에 준비한 코드

| 파일 | 역할 | 현재 사용 여부 |
| --- | --- | --- |
| `src/services/workspaceStorage.js` | 기존 저장 키를 유지한 읽기·쓰기, CSV 인맥/금액 일괄 저장 실패 시 되돌리기 | `App.jsx`의 저장 로직에 연결 |
| `src/services/apiClient.js` | JSON 요청·오류, 204 응답, 취소·시간 제한, 쿠키 세션·CSRF 토큰·멱등 키 전달 | 준비 완료, UI 요청 없음 |
| `src/services/backend.js` | 아래 API별 호출 함수 | 준비 완료, UI 요청 없음 |
| `.env.example` | 서버 주소와 명시적인 활성화 설정 예시 | 기본 비활성화 |
| `src/services/*.test.js` | 네트워크 없는 모의 요청 및 저장 실패·복구 테스트 | 실행 가능 |
| `backend/`, `src/services/aiChat.js`, `src/AIPage.jsx` | FastAPI AI 모의 서버, 가상 기록 조회, 비동기 대화 | PC 데모에서 실제 HTTP 연결 |

`VITE_API_ENABLED=true`만 설정해도 현재 UI가 서버로 바뀌지는 않습니다. 실제 연결 때 화면의 비동기 로딩·저장 중·실패·로그인 만료 처리를 붙인 후 이 호출 함수를 사용해야 합니다. API 실패를 브라우저 저장 성공으로 바꾸는 자동 대체 동작은 없습니다. `AuthModal`의 체험 계정 저장과 브라우저 알림 전송 이력은 아직 별도 로컬 저장 코드이며 실제 인증·알림 코드로 교체할 대상입니다.

## 백엔드가 필요한 부분

| 영역 | 현재 동작 | 연결해야 할 작업 |
| --- | --- | --- |
| 회원가입·로그인 | 브라우저에 체험 계정의 해시와 세션 표시 저장 | 서버 계정 생성·비밀번호 검증·로그아웃·세션 만료, 계정별 데이터 분리 |
| 인맥·관계·교류 | 로컬 사람 배열 변경 | DB CRUD, 사용자 소유권 확인, 교류 추가 시 마지막 만남 날짜의 원자적 갱신 |
| 일정·참석·알림일 | 로컬 일정 배열 변경 | DB CRUD, 인맥과 일정 소유권 및 연결 유효성 검증, 수정·삭제 시 예약 알림 재계산 |
| 금액 기록·수정·삭제 | 로컬 장부 변경 후 통계·사람별 이력 재계산 | DB CRUD, 금액·날짜·인맥·일정 연결 서버 검증 |
| CSV 가져오기 | 프론트에서 검사·미리보기 후 로컬 일괄 저장 | 동일 검사를 서버에서 다시 수행, 새 인맥/금액을 DB 트랜잭션으로 일괄 저장, 중복·재시도 처리 |
| 알림함·읽음·설정 | 현재 일정으로 알림함 생성, 읽음과 설정 로컬 저장 | 계정별 알림 DB, 여러 기기 읽음 동기화, 발송 설정 저장 |
| 앱 종료 후 알림 | 미지원; 현재 브라우저 알림은 페이지가 열려 있을 때만 작동 | 서버 스케줄러·작업 큐·중복 방지, Web Push 발송과 서비스 워커 또는 별도 선택한 발송 채널 |
| AI 제안·대화 | `domain.js`의 기록 기반 규칙으로 응답 | 서버에서 소유 기록 조회 후 AI 제공자 호출, 근거 기록 반환, 실패·사용량 제한 처리 |
| 다른 PC/모바일 동기화 | 미지원; 브라우저마다 다른 저장소 | 로그인 이후 서버 초기 조회, 변경 성공 후 공유 상태 반영, 기존 로컬 데이터의 명시적 이전 |

CSV **파일 다운로드와 프론트 미리보기**, 달력 파일 다운로드, 테마 전환, 필터·검색은 계속 프론트에서 처리할 수 있습니다. 현재 전체 기록을 메모리에 조회해 만드는 통계도 작은 데이터에서는 프론트에 유지할 수 있습니다. 서버 조회가 페이지 단위로 바뀐다면 전체 합계·통계를 별도 집계 API로 받는 것이 필요합니다.

## 데이터 계약

날짜는 `YYYY-MM-DD`, 행사 시간은 `HH:mm`과 `Asia/Seoul` 기준을 사용합니다. `id`는 불투명한 문자열이며 프론트에서 형식을 추측하지 않습니다. 서버는 모든 데이터에 현재 세션에서 결정한 `userId`를 부여하고, 요청 본문이 지정한 소유자는 신뢰하지 않습니다.

```js
// Person: 화면과 호환되는 기본 필드
{
  id, name, relation, group, importance, lastMet, memo,
  interactions: [{ id, date, note }]
}
// Event
{
  id, personId, title, type, date, time, location,
  attendance, reminderDays, memo
}
// FinancialRecord
{
  id, personId, eventId, type, date, direction, amount, memo
}
```

- `relation`: 공백을 정리한 1~40자 문자열. 가족·친구·직장동료·거래처 외 직접 입력한 관계도 허용하고, 빈 값은 `기타`로 저장합니다. 고정된 5개 값만 허용하는 DB enum으로 제한하지 않습니다.
- `importance`: `매우 중요`, `중요`, `보통`. 기존 `매우중요` 표기는 `매우 중요`로 정규화합니다. 중요도 비교 순서도 이 순서를 따릅니다.
- `name`, `group`: 각각 최대 40자. 메모는 최대 1,000자. 교류의 `note`는 화면의 저장 필드입니다. 기존 시연 데이터의 `memo`·`type`은 이전 시 `note`로 정리합니다.
- `type`: 결혼식·돌잔치·장례식·생일·기타. 현재 새 일정 폼은 앞의 4종, 금액 폼은 기타도 허용합니다.
- `attendance`: `참석`, `불참`, 아직 선택하지 않은 경우 `''`. 기존 `참석 예정`은 `참석`으로 이전합니다.
- `direction`: `보낸 마음` 또는 `받은 마음`. `amount`는 원 단위 1~1,000,000,000의 정수입니다. 송금 기능을 뜻하지 않습니다.
- `eventId`: 연결 없음은 `''` 또는 서버 합의한 `null`을 어댑터에서 통일합니다. 연결한 행사와 인맥·행사유형은 일치해야 합니다.
- 서버의 `createdAt`, `updatedAt`, `revision` 추가를 권장합니다. 동시 수정 충돌은 `409`로 반환하고 최신 내용을 다시 확인하게 해야 합니다.

## 제안 API와 준비된 함수

기본 주소는 `.env.example`의 `/api`입니다. 서버가 다른 포트를 사용한다면 개발용 주소를 지정할 수 있습니다. 운영은 같은 출처의 `/api` 또는 HTTPS 주소를 사용합니다. 모든 함수의 마지막 인자로 `{signal, idempotencyKey}`를 넘길 수 있습니다.

| 메서드·경로 | `createBackendServices()`의 함수 | 성공 응답 |
| --- | --- | --- |
| `GET /auth/session` | `auth.session()` | `{user: null}` 또는 `{user: {id,name,email}, csrfToken?}` |
| `POST /auth/signup`, `/auth/login` | `auth.signup(values)`, `auth.login(values)` | 위 사용자·세션 정보, 서버의 HttpOnly 세션 쿠키 |
| `POST /auth/logout` | `auth.logout()` | `204`, 세션 폐기 |
| `GET /workspace` | `workspace.load()` | `{schemaVersion:1, people, events, records, readIds, notificationSettings}` |
| `GET /people`, `/events`, `/records` | `people.list(filters)` 등 | `{items:[], nextCursor:null}` |
| `POST /people`, `/events`, `/records` | 각 `create(values)` | 생성된 전체 객체, `201` |
| `PATCH /people/:id`, `/events/:id`, `/records/:id` | 각 `update(id, patch)` | 저장된 전체 객체 |
| `POST /people/:id/interactions` | `people.addInteraction(id, values)` | 교류와 마지막 만남이 함께 갱신된 Person |
| `DELETE /events/:id`, `/records/:id` | `events.remove(id)`, `records.remove(id)` | `204` |
| `POST /records/import/preview` | `records.previewImport(csv)` | `{previewId, totalCount, duplicateCount, newPeople, rows, errors, warnings, expiresAt}` |
| `POST /records/import/commit` | `records.commitImport(previewId, {idempotencyKey})` | `{people, records, duplicateCount}`; 이번에 생성된 전체 객체 |
| `POST /workspace/migrations/preview` | `workspace.previewMigration(snapshot)` | `{previewId, counts, conflicts, idMapping, expiresAt}` |
| `POST /workspace/migrations/commit` | `workspace.commitMigration(previewId, {idempotencyKey})` | 서버의 전체 workspace와 최종 `idMapping` |
| `GET /notifications` | `notifications.list(filters)` | `{items:[], nextCursor:null}` |
| `PATCH /notifications/:id` | `notifications.markRead(id)` | `{id, read:true}` |
| `POST /notifications/read-all` | `notifications.markAllRead()` | `204` |
| `GET /notification-preferences` | `notifications.preferences()` | `{browser:boolean, timezone:'Asia/Seoul'}` |
| `PATCH /notification-preferences` | `notifications.updatePreferences(patch)` | 저장된 설정 |
| `POST /push-subscriptions` | `notifications.subscribePush(subscription)` | `{id}` |
| `DELETE /push-subscriptions/:id` | `notifications.unsubscribePush(id)` | `204` |
| `POST /ai/advice` | `ai.advice(values)` | 아래 화면 호환 응답 |

목록의 필터 키는 백엔드와 합의해야 합니다. 예: `query`, `personId`, `year`, `month`, `type`, `direction`, `cursor`, `limit`. API 호출 함수는 쿼리를 URL 인코딩하고 인맥/기록 ID를 경로용으로 인코딩합니다.

AI 요청은 `{question, mode, personId, eventId?}`를 보내고, 전체 로컬 연락처·장부를 매번 보내지 않습니다. 서버가 세션 소유권을 확인한 후 필요한 근거만 조회합니다. 성공 응답은 현재 `AdviceMessage`가 사용하는 형식입니다.

```js
{
  title: '기록을 참고한 제안', text: '응답 본문', amount: 100000, // amount는 선택
  isMessage: false,
  evidence: [{label: '최근 받은 마음', value: '2025.05.17 · 장례식 · 100,000원'}],
  suggestions: ['참석하지 못한다면?']
}
```

기록이 없는 금액을 받은 사실로 만들어내지 않아야 합니다. 서버는 근거 없는 금액을 단정하지 않고 금액의 최종 결정은 사용자에게 맡깁니다. AI API 키·모델 제공자 인증정보·시스템 프롬프트·사용량 제한은 서버에 둡니다. 대화를 저장할지와 보관 기간도 별도로 결정해야 합니다.

오류는 아래 공통 형식을 사용합니다. `ApiError`는 `status`, `code`, `fields`를 제공하며 `204`는 `null`로 반환합니다. HTML 오류 본문을 화면에 그대로 표시하지 않습니다.

```json
{"error":{"code":"validation_failed","message":"입력값을 확인해 주세요.","fields":{"relation":"40자 이내로 입력해 주세요."}}}
```

`401`: 로그인 필요, `403`: 접근 불가, `409`: 중복·수정 충돌, `422`: 입력 오류, `429`: 요청 제한, `5xx`: 서버 오류를 구분합니다. 전송 취소는 `aborted`, 시간 초과는 `timeout`, 연결 실패는 `network_error`입니다. 저장 요청은 자동 재시도하지 않습니다. 가져오기·데이터 이전의 재시도는 같은 `Idempotency-Key`로 서버가 동일 결과를 반환하도록 구현합니다.

## 실제 연결 순서

1. **인증과 소유권부터 연결**: 브라우저 체험 계정을 실제 서버 계정으로 간주하지 않습니다. 서버 세션의 `user.id`를 기준으로 조회·수정·삭제하고 로그아웃 시 공유 상태와 진행 중 요청을 비웁니다. HttpOnly·Secure·적절한 SameSite 쿠키, Origin/CSRF 검증이 필요합니다. `credentials:'include'`만으로 인증·CSRF 방어가 완성되는 것은 아닙니다. 별도 출처를 쓴다면 정확한 허용 Origin과 쿠키 정책을 함께 설정합니다.
2. **서버 초기 조회와 저장 수명주기 연결**: `workspace.load()` 완료 후 화면을 열고, 저장 중 중복 제출을 막으며, 서버 성공 응답을 React 상태에 반영합니다. 실패한 요청을 로컬에 성공 저장한 것처럼 표시하지 않습니다. 로그인 만료에는 재로그인 안내, 취소/실패에는 명확한 복구 경로를 둡니다.
3. **CRUD 연결**: `App.jsx`의 `savePerson/updatePerson`, `saveEvent/updateEvent/일정삭제`, `saveRecord/deleteRecord/importRecords`와 `PeoplePage.jsx` 교류 추가를 위 서비스로 교체합니다. ID는 서버 응답을 사용하고, 금액 변경 후 장부·통계·사람별 이력을 같은 상태에서 갱신합니다. 일정 삭제 시 금액 기록은 보존하되 연결만 해제하도록 서버에서도 맞춥니다.
4. **기존 브라우저 데이터 이전**: 사용자에게 이전할 사람·일정·금액 건수와 중복/충돌을 보여준 후 명시적으로 업로드합니다. 체험용 기본 샘플을 무조건 계정에 복사하지 않습니다. 로컬 ID와 서버 ID의 매핑으로 인맥/일정/기록 연결을 유지하고, 하나의 트랜잭션으로 반영합니다. 성공 전 로컬 원본을 지우지 않으며, 서버가 미리보기 ID의 사용자·만료·동일 입력을 검증해야 합니다.
5. **CSV 서버 저장 연결**: 로컬 미리보기는 유지할 수 있지만 서버가 원본 CSV를 재검사하고 서버 소유 레코드와 비교해야 합니다. 현재 동일 기록ID는 건너뛰고 ID 없는 동일 내용은 중복 제외하는 정책을 맞춥니다. 미리보기 ID와 멱등 키로 커밋하고 인맥·금액 중 하나만 저장되는 부분 성공을 막습니다. 로컬 어댑터의 되돌리기는 DB 트랜잭션을 대신하지 않습니다.
6. **알림과 AI 연결**: 일정 예약 작업의 생성·수정·취소, 타임존, 당일/행사 전 알림, 중복 발송 방지를 먼저 구현합니다. 웹 푸시는 서비스 워커와 사용자 권한·구독 연결이 추가로 필요합니다. 서버만 붙이면 앱 종료 후 현재 `new Notification()`이 자동 실행되는 것은 아닙니다. AI 연결은 위 계약에 맞춰 비동기 응답·오류·요청 취소를 대화창에 반영합니다.

## 연결 코드 사용 예시

아래는 향후 연결 위치의 예시이며 지금 UI에 삽입된 코드가 아닙니다.

```js
import { backendOptionsFromEnv, createBackendServices } from './services/backend.js';

const api = createBackendServices({
  ...backendOptionsFromEnv(),
  getCsrfToken: () => currentSession?.csrfToken || '',
});
const controller = new AbortController();
const saved = await api.people.update(personId, patch, { signal: controller.signal });
// 성공한 saved 객체로 공유 상태 갱신. catch에서 저장 실패/인증 만료 처리.
```

`.env`의 `VITE_*`는 빌드 결과에 포함되는 **공개 설정**입니다. 서버 주소만 넣고 비밀번호·AI 키·DB 접속정보를 넣지 않습니다. 환경변수를 바꾼 후 개발 서버 재시작 또는 운영 재빌드가 필요합니다. 실제 백엔드 구축·배포·DB 연결·서비스 워커·SMS/이메일 공급자 연동은 이번 준비 작업에 포함되지 않았습니다.
