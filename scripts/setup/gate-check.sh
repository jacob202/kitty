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

if [ "$PHASE" = "12" ]; then
    echo "[ Eval Framework ]"
    check "contracts/eval_result.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/contracts/eval_result.py"
    check "evals/ directory exists" \
        "test -d /Users/jacobbrizinski/Projects/kitty/evals"
    check "eval contract tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_eval_contracts.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "memory recall evals pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest evals/test_memory_recall.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "knowledge recall evals pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest evals/test_knowledge_recall.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "context injection evals pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest evals/test_context_injection.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "run_evals.py exits 0" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/python scripts/run_evals.py >/dev/null"
fi

if [ "$PHASE" = "13" ]; then
    echo "[ Siri Shortcut — /ask endpoint ]"
    check "/ask endpoint in app.py" \
        "grep -q 'def ask' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "/ask endpoint tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_ask_endpoint.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "SIRI_SHORTCUT.md exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/docs/SIRI_SHORTCUT.md"
    check "/ask returns 400 on empty message" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_ask_endpoint.py::test_ask_empty_message_returns_400 -q --tb=no 2>/dev/null | grep -q 'passed'"
fi

if [ "$PHASE" = "15" ]; then
    echo "[ LLM 3-Decision Router ]"
    check "route_model() in llm_client.py" \
        "grep -q 'def route_model' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
    check "_is_offline() in llm_client.py" \
        "grep -q 'def _is_offline' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
    check "route_model imported in app.py" \
        "grep -q 'route_model' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "routing tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_llm_routing.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "full test suite passes" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/ -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "qwen3-235b in router default" \
        "grep -q 'qwen3-235b' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
    check "deepseek-r1 in router" \
        "grep -q 'deepseek-r1' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
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

if [ "$PHASE" = "9" ]; then
    echo "[ PDF Pipeline + Schematic Vision ]"
    check "gateway/pdf_pipeline.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf/gateway/pdf_pipeline.py"
    check "gateway/vision.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf/gateway/vision.py"
    check "contracts/pdf_chunk.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf/contracts/pdf_chunk.py"
    check "scripts/ingest_pdf.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf/scripts/ingest_pdf.py"
    check "llama-cloud installed" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/python -c 'import llama_cloud'"
    check "_extract_pdf calls pdf_pipeline in knowledge.py" \
        "grep -q 'pdf_pipeline' /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf/gateway/knowledge.py"
    check "pdf_pipeline tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf && /Users/jacobbrizinski/Projects/kitty/venv/bin/pytest tests/test_pdf_pipeline.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "vision tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf && /Users/jacobbrizinski/Projects/kitty/venv/bin/pytest tests/test_vision.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "full test suite passes (no regressions)" \
        "cd /Users/jacobbrizinski/Projects/kitty/.worktrees/phase-9-pdf && /Users/jacobbrizinski/Projects/kitty/venv/bin/pytest tests/ -q --tb=no 2>/dev/null | grep -q 'passed'"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    echo "Phase $PHASE NOT complete. Fix the failing checks above."
    exit 1
else
    echo "Phase $PHASE COMPLETE ✓"
fi
