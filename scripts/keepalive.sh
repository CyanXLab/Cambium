#!/bin/bash
# Keepalive launcher for Cambium.
# Uses relative paths so it works on any machine.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load .env if present
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

export MODELSCOPE_API_KEY="${MODELSCOPE_API_KEY:-}"
export MODELSCOPE_BASE_URL="${MODELSCOPE_BASE_URL:-https://api-inference.modelscope.cn/v1}"
export MODELSCOPE_MODEL="${MODELSCOPE_MODEL:-}"
export PORT="${PORT:-3000}"

# Use exec so we replace the shell, simpler for the supervisor
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --log-level info \
  --workers 1 \
  --no-access-log
