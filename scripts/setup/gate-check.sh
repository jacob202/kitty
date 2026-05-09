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
        "curl -sf -H 'Authorization: Bearer kitty-local-key-change-me' http://localhost:8001/v1/models"
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

if [ "$PHASE" = "8" ]; then
    echo "[ Voice — STT + TTS ]"
    check "gateway/stt.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/stt.py"
    check "gateway/tts.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/tts.py"
    check "/v1/audio/transcriptions in app.py" \
        "grep -q 'audio/transcriptions' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "/v1/audio/speech in app.py" \
        "grep -q 'audio/speech' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "voice gateway tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_voice_gateway.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "edge-tts installed" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/python -c 'import edge_tts'"
    check "faster-whisper installed" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/python -c 'import faster_whisper'"
fi

if [ "$PHASE" = "7" ]; then
    echo "[ Morning Brief + Pushover ]"
    check "gateway/brief.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/brief.py"
    check "gateway/notify.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/notify.py"
    check "scripts/brief.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/scripts/brief.py"
    check "contracts/brief_item.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/contracts/brief_item.py"
    check "launchd plist exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/kitty_gateway/com.kitty.morning-brief.plist"
    check "/brief endpoint in app.py" \
        "grep -q '/brief' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "brief tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_brief.py -q --tb=no 2>/dev/null | grep -q 'passed'"
fi

if [ "$PHASE" = "11" ]; then
    echo "[ Backup + Tailscale ]"
    check "scripts/backup.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/scripts/backup.py"
    check "backup plist exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/kitty_gateway/com.kitty.backup.plist"
    check "tailscale-access.md exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/docs/tailscale-access.md"
    check "restic installed" \
        "test -x /opt/homebrew/bin/restic"
    check "backup launchd agent loaded" \
        "launchctl list | grep -q com.kitty.backup"
    check "RESTIC_PASSWORD set in .env" \
        "grep -q 'RESTIC_PASSWORD=.' /Users/jacobbrizinski/Projects/kitty/.env"
    check "backup tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_backup.py -q --tb=no 2>/dev/null | grep -q 'passed'"
fi

if [ "$PHASE" = "6" ]; then
    echo "[ Full Ingestion Sweep ]"
    check "ingest_phase6.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/scripts/ingest_phase6.py"
    check "ChatGPT extractor in knowledge.py" \
        "grep -q '_extract_chatgpt_json' /Users/jacobbrizinski/Projects/kitty/gateway/knowledge.py"
    check "journal extractor in knowledge.py" \
        "grep -q '_extract_sqlite_journal' /Users/jacobbrizinski/Projects/kitty/gateway/knowledge.py"
    check "knowledge tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_knowledge.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "Claude Code sessions dir exists" \
        "test -d $HOME/.claude/projects/-Users-jacobbrizinski-Projects-kitty"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    echo "Phase $PHASE NOT complete. Fix the failing checks above."
    exit 1
else
    echo "Phase $PHASE COMPLETE ✓"
fi
