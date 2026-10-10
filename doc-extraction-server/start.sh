#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8050}"
LOG_FILE="${LOG_FILE:-./doc-extract.log}"

exec "$PYTHON_BIN" -m uvicorn app.extractor_main:app --host "${HOST:-0.0.0.0}" --port "$PORT" >> "$LOG_FILE" 2>&1
