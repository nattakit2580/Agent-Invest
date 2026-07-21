@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Agent Invest - Local Runner

cd /d "%~dp0"

echo.
echo  =========================================
echo   Agent Invest - Starting (Local)
echo  =========================================
echo.

:: ---- 1) Find a working Python (python, then py -3) ----
set "PYLAUNCHER="
python --version >nul 2>&1
if not errorlevel 1 set "PYLAUNCHER=python"

if not defined PYLAUNCHER (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYLAUNCHER=py -3"
)

if not defined PYLAUNCHER (
    echo [ERROR] Python was not found on this machine.
    echo         Install Python 3.11+ from https://www.python.org/downloads/
    echo         During setup, check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)
echo [OK] Found Python: %PYLAUNCHER%

:: ---- 2) Check Node.js / npm ----
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js was not found on this machine.
    echo         Install Node.js 20 LTS from https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo [OK] Found Node.js / npm

:: ---- 3) Backend: create venv (once) ----
echo.
echo [Backend 1/3] Preparing Python environment...
if not exist "backend\.venv\Scripts\python.exe" (
    echo   Creating virtual environment, first run may take a while...
    %PYLAUNCHER% -m venv backend\.venv
    if errorlevel 1 (
        echo [ERROR] Failed to create backend virtual environment.
        pause
        exit /b 1
    )
) else (
    echo   Virtual environment already prepared.
)

set "VENV_PY=%~dp0backend\.venv\Scripts\python.exe"

:: ---- 4) Backend: install dependencies ----
echo [Backend 2/3] Checking Python dependencies...
"%VENV_PY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VENV_PY%" -m pip install -r backend\requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] Failed to install backend dependencies.
    echo         Check your internet connection and run this file again.
    pause
    exit /b 1
)
echo   Dependencies ready.

:: ---- 5) Backend: local .env (SQLite, no Postgres needed) ----
echo [Backend 3/3] Checking configuration...
if not exist "backend\.env" (
    "%VENV_PY%" make_local_env.py
    echo.
    echo   [IMPORTANT] Edit backend\.env and set OPENROUTER_API_KEY to enable AI analysis.
    echo               Get a free key at https://openrouter.ai/keys
    echo.
) else (
    echo   backend\.env already exists, leaving it as-is.
)

:: ---- 6) Frontend: exact lockfile dependencies ----
echo.
echo [Frontend 1/1] Checking Node dependencies...
if not exist "frontend\node_modules" (
    echo   Installing packages, first run may take a while...
    pushd frontend
    call npm ci --no-fund --no-audit
    set "NPM_ERR=%errorlevel%"
    popd
    if not "!NPM_ERR!"=="0" (
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
) else (
    pushd frontend
    call npm ls --depth=0 >nul 2>&1
    set "NPM_CHECK_ERR=%errorlevel%"
    if not "!NPM_CHECK_ERR!"=="0" (
        echo   Dependencies do not match package-lock.json; reinstalling...
        call npm ci --no-fund --no-audit
        set "NPM_ERR=%errorlevel%"
    ) else (
        set "NPM_ERR=0"
    )
    popd
    if not "!NPM_ERR!"=="0" (
        echo [ERROR] npm ci failed.
        pause
        exit /b 1
    )
)

:: ---- 7) Check if OUR backend is already running (verify identity, not just the port) ----
:: A different local app can easily already be sitting on 8000/3000 (common on a dev
:: machine with several projects). Do not assume "port busy" means "this is ours".
set "BACKEND_IS_OURS="
for /f %%a in ('netstat -ano ^| findstr /r /c:"TCP.*:8000 .*LISTENING"') do (
    curl -s -m 2 http://localhost:8000/health 2>nul | findstr /c:"healthy" >nul 2>&1
    if not errorlevel 1 set "BACKEND_IS_OURS=1"
)

:: ---- 8) Launch backend + frontend, each in its own window ----
echo.
if defined BACKEND_IS_OURS (
    echo [INFO] Backend already running on port 8000, leaving it as-is.
) else (
    echo Starting backend  -^> http://localhost:8000
    start "Agent Invest - Backend" cmd /k "cd /d ""%~dp0backend"" && ""%VENV_PY%"" -m uvicorn main:app --reload --port 8000"
)

:: Frontend: always attempt to start. Next.js checks port 3000 itself and falls
:: back to 3001, 3002, etc. automatically if something else already holds it,
:: printing the real URL in its own window - safer than guessing here.
echo Starting frontend -^> http://localhost:3000 (or the next free port; check its window)
start "Agent Invest - Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo.
echo  =========================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo  =========================================
echo.
echo Waiting for the frontend to boot...
ping -n 8 127.0.0.1 >nul

start "" "http://localhost:3000"

echo.
echo Backend and frontend are running in their own windows.
echo Close those windows (or press Ctrl+C inside them) to stop the servers.
echo.
echo NOTE: if port 3000 was already taken by another app on this machine,
echo       Next.js picked a different port automatically - check the
echo       "Agent Invest - Frontend" window title bar / first lines for the
echo       real URL (e.g. http://localhost:3001) and open that instead.
echo.
pause
