#!/usr/bin/env bash
# Launch the My AI Chat platform as a daemon (double-fork → reparent to init).
# This is the recommended way to keep the service alive in sandboxed environments
# where background processes spawned by shells get reaped.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [ -f "${PROJECT_DIR}/.env" ]; then
  set -a
  . "${PROJECT_DIR}/.env"
  set +a
fi

export MODELSCOPE_API_KEY="${MODELSCOPE_API_KEY:-ms-a300ec43-a4f3-49d2-9044-2fdbc269f3b9}"
export MODELSCOPE_BASE_URL="${MODELSCOPE_BASE_URL:-https://api-inference.modelscope.cn/v1}"
export MODELSCOPE_MODEL="${MODELSCOPE_MODEL:-Qwen/Qwen3.5-122B-A10B}"
export PORT="${PORT:-3000}"

# Kill any existing instance
pkill -f "app.main:app" 2>/dev/null || true
sleep 1

# Daemonize via Python double-fork
exec python3 "${SCRIPT_DIR}/daemonize.py" \
  "${PROJECT_DIR}" \
  python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --log-level info
