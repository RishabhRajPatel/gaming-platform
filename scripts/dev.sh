#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Starting Postgres + Redis"
docker compose up -d postgres redis

echo "==> Applying migrations"
cd rummy/backend
# shellcheck disable=SC1091
source .venv/bin/activate
alembic upgrade head

echo "==> Backend on :8000 (Ctrl+C to stop). Run frontend separately: cd rummy/frontend && npm run dev"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
