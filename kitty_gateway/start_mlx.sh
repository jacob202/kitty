#!/bin/bash
# Start the MLX local model server for private/sensitive queries
# Model: Qwen3.5-4B-4bit — stays on device, never calls cloud APIs
set -euo pipefail

MLX_MODEL="${MLX_MODEL:-mlx-community/Qwen3.5-4B-4bit}"
MLX_HOST="${MLX_HOST:-127.0.0.1}"
MLX_PORT="${MLX_PORT:-8010}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found for MLX server startup."
  exit 1
fi

echo "Starting MLX LM server on port ${MLX_PORT}..."
echo "Model: ${MLX_MODEL}"
echo "Used for: medical, financial, and other sensitive queries"

if [[ "${MLX_SMOKE:-0}" == "1" ]]; then
  echo "MLX_SMOKE=1 set; exiting before server start."
  exit 0
fi

python3 -m mlx_lm.server \
    --model "${MLX_MODEL}" \
    --port "${MLX_PORT}" \
    --host "${MLX_HOST}"
