#!/bin/bash
set -e
source ~/kitty-services/venv/bin/activate

export OPENAI_API_BASE_URL="http://localhost:8001/v1"
export OPENAI_API_KEY="kitty-local-key-change-me"
export WEBUI_SECRET_KEY="kitty-webui-secret-change-me"
export DEFAULT_MODELS="kitty-default"
export PORT=3000

echo "Starting Open WebUI on port 3000..."
echo "Interface will be at: http://localhost:3000"
open-webui serve
