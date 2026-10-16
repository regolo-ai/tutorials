#!/usr/bin/env bash
# Creates a virtual environment on first run, installs the requirements and starts the app.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "Created .env. Add your REGOLO_API_KEY and run ./run.sh again."; exit 1; }
HOST=$(grep -E '^HOST=' .env | cut -d= -f2); PORT=$(grep -E '^PORT=' .env | cut -d= -f2)
echo "Open http://${HOST:-127.0.0.1}:${PORT:-8100}"
exec .venv/bin/uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8100}"
