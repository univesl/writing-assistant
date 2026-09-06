#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

PYTHON_BIN="${PYTHON_BIN:-/home/liubin/miniconda3/envs/writing-kng/bin/python}"
PORT="${PORT:-8050}"
LOG_FILE="${LOG_FILE:-/home/liubin/logs/wa-doc-extract.log}"

mkdir -p "$(dirname "$LOG_FILE")" upload uploads
exec "$PYTHON_BIN" -m uvicorn app.extractor_main:app --host "${HOST:-0.0.0.0}" --port "$PORT" >> "$LOG_FILE" 2>&1
