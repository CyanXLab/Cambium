#!/bin/bash
cd /home/z/my-project/ai-chat
export MODELSCOPE_API_KEY="ms-a300ec43-a4f3-49d2-9044-2fdbc269f3b9"
export MODELSCOPE_BASE_URL="https://api-inference.modelscope.cn/v1"
export MODELSCOPE_MODEL="Qwen/Qwen3.5-122B-A10B"
export PORT=3000

# Use exec so we replace the shell, simpler for the supervisor
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 3000 \
  --log-level info \
  --workers 1 \
  --no-access-log
