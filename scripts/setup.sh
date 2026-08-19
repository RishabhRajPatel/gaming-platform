#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Preparing .env"
[ -f .env ] || cp .env.example .env

echo "==> Backend deps"
cd rummy/backend
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ../..

echo "==> Frontend deps"
cd rummy/frontend
npm install
cd ../..

echo "==> Done. Next: ./scripts/dev.sh"
