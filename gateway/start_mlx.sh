#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi

source "${ROOT_DIR}/venv/bin/activate"

if ! command -v mlx_lm.server >/dev/null 2>&1; then
  echo "Error: mlx_lm.server not found in ${ROOT_DIR}/venv"
  exit 1
fi

MLX_HOST="${MLX_HOST:-127.0.0.1}"
MLX_PORT="${MLX_PORT:-8010}"
MLX_MODEL="${MLX_MODEL:-mlx-community/Qwen3.5-4B-4bit}"

echo "Starting MLX server on ${MLX_HOST}:${MLX_PORT}..."
echo "Model: ${MLX_MODEL}"

if [[ "${MLX_SMOKE:-0}" == "1" ]]; then
  echo "MLX_SMOKE=1 set; exiting before server start."
  exit 0
fi

exec mlx_lm.server --host "${MLX_HOST}" --port "${MLX_PORT}" --model "${MLX_MODEL}"
