@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required. Install Node.js and open a new terminal.
  exit /b 1
)
node "%~dp0scripts\dev-all.mjs" %*
exit /b %errorlevel%
