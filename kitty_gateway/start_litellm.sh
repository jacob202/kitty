#!/bin/bash
set -e
cd /Users/jacobbrizinski/Projects/kitty
set -a && source /Users/jacobbrizinski/Projects/kitty/.env && set +a
source ~/kitty-services/venv/bin/activate

echo "Starting LiteLLM proxy on port 8001..."
litellm --config kitty_gateway/litellm_config.yaml --port 8001 --host 127.0.0.1
