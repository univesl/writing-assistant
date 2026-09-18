#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
SCREEN_NAME="${SCREEN_NAME:-wa-doc-extract}"
screen -S "$SCREEN_NAME" -X quit 2>/dev/null || true
screen -dmS "$SCREEN_NAME" bash -lc "cd '$PWD' && exec '$PWD/start.sh'"
echo "started $SCREEN_NAME"
