#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo '[INFO] FlightInsight quick start - Linux/macOS'
if ! command -v docker >/dev/null 2>&1; then
  echo '[ERROR] Docker CLI is required.' >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo '[ERROR] Docker daemon is unavailable. Start Docker Desktop or Docker Engine.' >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo '[ERROR] Docker Compose v2 is required.' >&2
  exit 1
fi

echo '[1/5] Prepare private .env and download official BTS archives...'
docker run --rm --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$PWD,target=/workspace" \
  -w /workspace python:3.12-slim \
  sh -c 'python scripts/init_env.py && python scripts/download_bts.py'

echo '[2/5] Check Compose configuration...'
docker compose config -q

echo '[3/5] Start PostgreSQL...'
docker compose up -d --wait postgres

echo '[4/5] Import BTS data, skipping already loaded archives...'
docker compose run --build --rm etl

echo '[5/5] Start FastAPI and Streamlit and wait for health checks...'
docker compose up -d --build --wait api dashboard

echo '[VERIFY] Verify API against the expected BTS data...'
docker compose exec -T api python scripts/check_api.py

printf '\n[DONE] FlightInsight is ready.\n'
echo 'Dashboard: http://localhost:8501'
echo 'API docs: http://localhost:8000/docs'
echo 'Data and credentials remain local. No Docker volumes were removed.'
