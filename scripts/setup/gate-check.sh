#!/bin/bash
# Gate check script — verify a phase is actually done
# Usage: ./scripts/setup/gate-check.sh <phase-number>
set -e

PHASE=${1:-1}
PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  ✓ $desc"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Gate Check — Phase $PHASE ==="
echo ""

if [ "$PHASE" = "1" ]; then
    echo "[ Infrastructure ]"
    check "LiteLLM proxy reachable on port 8001" \
        "curl -sf http://localhost:8001/health"
    check "Open WebUI reachable on port 3000" \
        "curl -sf http://localhost:3000"
    check "MLX server reachable on port 8010" \
        "curl -sf http://localhost:8010/v1/models"
    check "kitty_gateway/litellm_config.yaml exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/kitty_gateway/litellm_config.yaml"
    check "contracts/routing_decision.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/contracts/routing_decision.py"
    check "contracts tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_contracts.py -q"
    check "Default model routes successfully" \
        "curl -sf -X POST http://localhost:8001/v1/chat/completions \
            -H 'Authorization: Bearer kitty-local-key-change-me' \
            -H 'Content-Type: application/json' \
            -d '{\"model\":\"kitty-default\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}],\"max_tokens\":5}' \
            | grep -q choices"
fi

if [ "$PHASE" = "2" ]; then
    echo "[ Kitty Gateway ]"
    check "Kitty Gateway reachable on port 8000" \
        "curl -sf http://localhost:8000/health"
    check "Domain classification returns valid domain" \
        "curl -sf -X POST http://localhost:8000/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{\"messages\":[{\"role\":\"user\",\"content\":\"My car makes a noise\"}]}' \
            | grep -qE 'repair|soul'"
    check "prompts/soul_v1.md exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/prompts/soul_v1.md"
    check "gateway/app.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    echo "Phase $PHASE NOT complete. Fix the failing checks above."
    exit 1
else
    echo "Phase $PHASE COMPLETE ✓"
fi
