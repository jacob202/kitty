#!/usr/bin/env bash
# Quick local image gen. Usage: ./scripts/gen.sh "your prompt" [num]
set -euo pipefail

cd "$(dirname "$0")/.."
export FAL_KEY="${FAL_KEY:-a221b381-f0b3-4816-bf37-a6aada78bd48:60b3ae35e673288c84233510ece7fd73}"

PROMPT="${1:?need a prompt}"
NUM="${2:-4}"

mcp/imagen/.venv/bin/python3 scripts/gen.py "$PROMPT" "$NUM"
