#!/usr/bin/env bash
# Run at the start of each Claude Code session to catch common blockers early.
set -euo pipefail

OK=0; WARN=0; FAIL=0
pass() { echo "  ✓ $1"; ((OK++)); }
warn() { echo "  ⚠ $1"; ((WARN++)); }
fail() { echo "  ✗ $1"; ((FAIL++)); }

echo "=== Kitty preflight ==="

# 1. gh auth
if gh auth status &>/dev/null; then
  pass "gh auth ok"
else
  fail "gh auth: not logged in — run: gh auth login"
fi

# 2. stale GITHUB_TOKEN
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  warn "GITHUB_TOKEN is set — may conflict with gh auth. Unset with: unset GITHUB_TOKEN"
else
  pass "GITHUB_TOKEN not set (clean)"
fi

# 3. git remote protocol
remote_url=$(git -C "$(dirname "$0")/.." remote get-url origin 2>/dev/null || true)
if [[ "$remote_url" == git@* ]]; then
  warn "git remote uses SSH: $remote_url — switch to HTTPS if auth fails"
else
  pass "git remote: $remote_url"
fi

# 4. Required API keys
required_keys=(ANTHROPIC_API_KEY)
env_file="$(dirname "$0")/../.env"
[[ -f "$env_file" ]] && set -a && source "$env_file" && set +a 2>/dev/null || true

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
