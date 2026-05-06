#!/usr/bin/env bash
# Launch Goose with local MLX backend (Qwen3.5-4B)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MLX_PORT=8080
MLX_MODEL="${MLX_MODEL:-mlx-community/Qwen3.5-4B-4bit}"

# Find MLX server
MLX_SERVER=""
if [ -f "$PROJECT_ROOT/venv/bin/mlx_lm.server" ]; then
    MLX_SERVER="$PROJECT_ROOT/venv/bin/mlx_lm.server"
elif command -v mlx_lm.server >/dev/null 2>&1; then
    MLX_SERVER="$(command -v mlx_lm.server)"
fi

if [ -z "$MLX_SERVER" ]; then
    echo "ERROR: mlx_lm.server not found"
    exit 1
fi

# Ensure MLX server is running
if ! lsof -i :"$MLX_PORT" >/dev/null 2>&1; then
    echo "Starting MLX server ($MLX_MODEL on port $MLX_PORT)..."
    nohup "$MLX_SERVER" \
        --model "$MLX_MODEL" \
        --host 127.0.0.1 \
        --port "$MLX_PORT" \
        > /tmp/mlx_server.log 2>&1 &
    sleep 5
    if ! lsof -i :"$MLX_PORT" >/dev/null 2>&1; then
        echo "ERROR: Failed to start MLX server. Check /tmp/mlx_server.log"
        exit 1
    fi
    echo "MLX server started."
else
    echo "MLX server already running on port $MLX_PORT."
fi

# Set environment for Goose to use local MLX
export GOOSE_PROVIDER=openai
export GOOSE_MODEL="$MLX_MODEL"
export OPENAI_API_KEY="dummy"
export OPENAI_API_BASE="http://127.0.0.1:$MLX_PORT/v1"
export GOOSE_TEMPERATURE=0.1
export GOOSE_MAX_TOKENS=2048
export GOOSE_TELEMETRY_ENABLED=false

# Find Goose
GOOSE_BIN=""
if [ -f "$HOME/.local/bin/goose" ]; then
    GOOSE_BIN="$HOME/.local/bin/goose"
elif command -v goose >/dev/null 2>&1; then
    GOOSE_BIN="$(command -v goose)"
else
    echo "ERROR: goose not found"
    exit 1
fi

echo "Launching Goose with MLX backend..."
echo "Model: $GOOSE_MODEL"
echo "API Base: $OPENAI_API_BASE"
echo ""

exec "$GOOSE_BIN" "$@"
