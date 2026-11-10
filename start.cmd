@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

echo [INFO] FlightInsight quick start - Windows
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker CLI not found. Install and start Docker Desktop.
    exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker engine is unavailable. Start Docker Desktop ^(Linux containers^).
    exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose v2 is required.
    exit /b 1
)

echo [1/5] Prepare private .env and download official BTS archives...
docker run --rm --mount "type=bind,source=%CD%,target=/workspace" -w /workspace python:3.12-slim sh -c "python scripts/init_env.py && python scripts/download_bts.py"
if errorlevel 1 goto failed

echo [2/5] Check Compose configuration...
docker compose config -q
if errorlevel 1 goto failed

echo [3/5] Start PostgreSQL...
docker compose up -d --wait postgres
if errorlevel 1 goto failed

echo [4/5] Import BTS data, skipping already loaded archives...
docker compose run --build --rm etl
if errorlevel 1 goto failed

echo [5/5] Start FastAPI and Streamlit and wait for health checks...
docker compose up -d --build --wait api dashboard
if errorlevel 1 goto failed

echo [VERIFY] Verify API against the expected BTS data...
docker compose exec -T api python scripts/check_api.py
if errorlevel 1 goto failed

echo.
echo [DONE] FlightInsight is ready.
echo Dashboard: http://localhost:8501
echo API docs: http://localhost:8000/docs
echo Data and credentials remain local. No Docker volumes were removed.
exit /b 0

:failed
echo.
echo [ERROR] Startup stopped. Check the preceding message.
echo [HELP] docker compose ps
echo [HELP] docker compose logs --tail=80 api dashboard postgres
exit /b 1
