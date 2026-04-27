#!/usr/bin/env bash
# Safe Kitty workspace bootstrap.
#
# This script prepares missing support folders without overwriting the live app.
# It intentionally does not create a root-level `kitty/` Python package because this
# repo already has an executable launcher named `kitty`.

set -euo pipefail

PROJECT_ROOT="${KITTY_ROOT:-$HOME/Projects/kitty}"
GARAGE_UI="$PROJECT_ROOT/garage-ui"

echo "Preparing Kitty workspace at $PROJECT_ROOT"

if [[ ! -d "$PROJECT_ROOT" ]]; then
  echo "ERROR: $PROJECT_ROOT does not exist."
  echo "Clone or move the runnable Kitty repo there first."
  exit 1
fi

cd "$PROJECT_ROOT"

if [[ -f "$PROJECT_ROOT/kitty" ]]; then
  echo "Found existing launcher file: $PROJECT_ROOT/kitty"
  echo "Keeping it. No root-level kitty/ package will be created."
fi

mkdir -p \
  "$PROJECT_ROOT/docs/imports" \
  "$PROJECT_ROOT/docs/archive" \
  "$PROJECT_ROOT/data/audit" \
  "$PROJECT_ROOT/data/eval" \
  "$PROJECT_ROOT/data/feedback" \
  "$PROJECT_ROOT/data/rlhf" \
  "$PROJECT_ROOT/data/training/audio" \
  "$PROJECT_ROOT/data/training/vision" \
  "$PROJECT_ROOT/evals/artifacts" \
  "$PROJECT_ROOT/logs" \
  "$HOME/.kitty" \
  "$HOME/.goose/recipes" \
  "$HOME/.goose/skills" \
  "$HOME/.goose/kitty-knowledge/patterns"

if [[ ! -f "$PROJECT_ROOT/.env.example" ]]; then
  cat > "$PROJECT_ROOT/.env.example" <<EOF
OPENROUTER_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
GEMINI_API_KEY=
KITTY_MODEL=openrouter/free
KITTY_MAX_MODEL=deepseek/deepseek-r1-0528
MLX_MODEL=mlx-community/Qwen3.5-4B-4bit
KITTY_ENABLE_LOCAL_MLX=0
KITTY_ENABLE_EXPERIMENTAL_SWARM=0
KITTY_ENABLE_INTERNAL_API=0
EOF
  echo "Created .env.example"
else
  echo "Kept existing .env.example"
fi

if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  echo "Created .env from .env.example"
else
  echo "Kept existing .env"
fi

if [[ -d "$GARAGE_UI" && -f "$GARAGE_UI/package.json" ]]; then
  echo "garage-ui package.json found."
else
  echo "WARNING: garage-ui/package.json is missing. Frontend install/build will not run."
fi

cat <<EOF

Workspace prep complete.

Next checks:
  ./kitty status
  /opt/homebrew/bin/python3.12 -m pytest tests/test_voice_routes.py tests/test_web_chat_phase1.py -q --tb=short
  cd garage-ui && npm run build

Start surfaces:
  ./kitty restart
  cd garage-ui && npm run dev
EOF
