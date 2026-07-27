#!/usr/bin/env bash
# Launch the My AI Chat platform (foreground)
set -euo pipefail

cd "$(dirname "$0")/.."

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

echo "==> My AI Chat starting on http://0.0.0.0:${PORT}"
echo "    Model:    ${MODELSCOPE_MODEL}"
echo "    Backend:  ${MODELSCOPE_BASE_URL}"
echo

exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --log-level info
