# PowerShell 창 하나로 실행

저장소 루트에서 다음 명령을 실행합니다.

```powershell
cd "C:\Users\CHAE\Desktop\hackaton-ai-service"
.\start.cmd
```

- Python과 Node.js가 설치되어 있어야 합니다. PowerShell 가상환경 활성화나 실행 정책 변경은 필요 없습니다.
- 최초 실행은 루트 `.venv`를 생성하고 Python 의존성 및 `frontend/node_modules`를 설치합니다. 인터넷 연결이 필요하며 몇 분 걸릴 수 있습니다.
- 이후에는 기존 환경을 재사용합니다. `requirements.txt` 변경 시 Python 의존성을 다시 설치합니다. 프런트 의존성을 바꿨다면 `frontend`에서 `npm.cmd install --no-package-lock`을 실행해 갱신합니다.
- 통합 서버 `gyeongjosa_ai.api:app`과 React를 같은 창에서 실행합니다. 준비가 끝나면 표시된 앱 주소를 엽니다.
- 기본 앱 주소: http://127.0.0.1:5173 / v4 직접 접속: http://127.0.0.1:8000/v4/
- **Ctrl+C**를 누르면 함께 종료합니다. 한쪽 서버가 실패하면 다른 쪽도 종료합니다.
- 이미 포트를 사용하는 프로그램이 있으면 안내 후 중단합니다. 기존 프로그램을 강제로 종료하지 않습니다.
- `frontend`에서는 `npm.cmd run dev:all`로도 같은 실행기를 사용할 수 있습니다.

설치·서버 실행 없이 포트와 환경 존재 여부만 확인할 때:

```powershell
.\start.cmd --check
```

포트를 바꿀 때는 같은 PowerShell 창에서 실행 전에 지정합니다. 화면의 API 프록시도 함께 맞춰집니다.

```powershell
$env:MAEUM_API_PORT = "8001"
$env:MAEUM_WEB_PORT = "5174"
.\start.cmd
```

다른 Python 설치로 가상환경을 처음 만들려면 `$env:MAEUM_PYTHON`에 실행 파일의 전체 경로를 지정합니다. 이미 만들어진 `.venv`는 그대로 사용합니다.

## 화면 확인

1. 앱의 **마음결 AI → v4 직무·법적 위험 분석**을 엽니다.
2. **AI 설명 방식 → 오프라인 설명만**, 외부 LLM 분석 동의 해제로 설정합니다.
3. 프리셋 선택 후 예산을 수정하고 추천을 다시 계산해 봅니다.

v4 오프라인 추천에는 API 키가 필요 없습니다. AI 자유 상담은 기존 설정에 따라 루트 `.env`의 `CODYSSEY_API_KEY`가 필요합니다. 이 실행기는 키를 생성하거나 출력하지 않습니다.

기존 `dev:demo`는 별도 모의 서버용입니다. 통합 실행은 `start.cmd` 또는 `dev:all`을 사용합니다.
