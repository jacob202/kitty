#!/usr/bin/env bash
# Run at the start of each Claude Code session to catch common blockers early.
set -euo pipefail

OK=0; WARN=0; FAIL=0
pass() { echo "  ✓ $1"; OK=$((OK + 1)); }
warn() { echo "  ⚠ $1"; WARN=$((WARN + 1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${KITTY_ENV_FILE:-${ROOT_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  export PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/venv/bin/python}"
  source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"
  load_env_assignments "${ENV_FILE}"
fi

echo "=== Kitty preflight ==="

# 1. gh auth
ambient_auth=0
keyring_auth=0
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  ambient_auth=1
fi
if command -v gh &>/dev/null && env -u GITHUB_TOKEN gh auth status &>/dev/null; then
  keyring_auth=1
fi

if [[ "${ambient_auth}" == "1" ]]; then
  pass "gh auth ok"
elif [[ -n "${GITHUB_TOKEN:-}" && "${keyring_auth}" == "1" ]]; then
  pass "gh auth keyring ok"
else
  fail "gh auth unavailable — run: env -u GITHUB_TOKEN gh auth login"
fi

# 2. stale GITHUB_TOKEN
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  if [[ "${keyring_auth}" == "1" ]]; then
    warn "stale GITHUB_TOKEN masks valid keyring auth; use env -u GITHUB_TOKEN for GitHub commands"
    if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
      if ! grep -Fqx "export GITHUB_TOKEN=''" "${CLAUDE_ENV_FILE}" 2>/dev/null; then
        echo "export GITHUB_TOKEN=''" >> "${CLAUDE_ENV_FILE}"
      fi
    fi
  else
    warn "GITHUB_TOKEN is set and no keyring fallback is available"
  fi
else
  pass "GITHUB_TOKEN not set (clean)"
fi

# 3. git remote protocol
remote_url=$(git -C "${ROOT_DIR}" remote get-url origin 2>/dev/null || true)
if [[ -z "${remote_url}" ]]; then
  fail "git remote origin is missing"
elif [[ "$remote_url" == git@* ]]; then
  warn "git remote uses SSH: $remote_url — switch to HTTPS if auth fails"
else
  pass "git remote: $remote_url"
fi

# 4. Required API keys
required_keys=(ANTHROPIC_API_KEY)

for key in "${required_keys[@]}"; do
  if [[ -n "${!key:-}" ]]; then
    pass "$key is set"
  else
    fail "$key missing — add to .env"
  fi
done

# 5. MLX/Ollama models
if command -v mlx_lm.generate &>/dev/null || python3 -c "import mlx_lm" &>/dev/null 2>&1; then
  pass "mlx_lm available"
elif command -v ollama &>/dev/null; then
  warn "mlx_lm not found; ollama available as fallback"
else
  warn "neither mlx_lm nor ollama found"
fi

echo ""
echo "=== ${OK} ok / ${WARN} warnings / ${FAIL} failures ==="
[[ $FAIL -eq 0 ]]
