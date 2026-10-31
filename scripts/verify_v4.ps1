# 마음결 v4 Windows 기능 회귀 검증
# 반드시 본인 소유 합성 데이터 프로젝트에서만 실행
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (!(Test-Path $py)) {
    throw "Python 가상환경이 없습니다: $py (환경 설치가 필요합니다.)"
}
Write-Host "CHECK: FastAPI / HTTPX / OpenAI imports"
& $py -c "import fastapi, httpx, openai, pydantic; print('DEPENDENCIES_OK')"
if ($LASTEXITCODE -ne 0) { throw '필수 Python 의존성을 설치해야 합니다.' }
Write-Host "CHECK: 84 v4 and legacy regression definitions"
& $py -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw '전체 Python 회귀 테스트 실패' }
Write-Host "CHECK: offline source contract"
& $py -m unittest -v test_source_contracts
if ($LASTEXITCODE -ne 0) { throw '소스 무결성 테스트 실패' }
Write-Host 'RESULT: PASS (Python tests only; model/browser E2E excluded)'
