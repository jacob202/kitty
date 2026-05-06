#!/usr/bin/env bash
# Golden demo script — release smoke with auth-aware chat checks.
#
# Default behavior:
# - hard-fail on route/test failures
# - warn (not fail) when chat provider credentials are missing/invalid
#
# Strict mode:
#   GOLDEN_DEMO_STRICT_CHAT=1 bash scripts/golden_demo.sh
#   -> fails when /api/chat cannot produce a normal model answer

set -euo pipefail

STRICT_CHAT="${GOLDEN_DEMO_STRICT_CHAT:-0}"
BASE_URL="${KITTY_BASE_URL:-http://localhost:5001}"
SKIP_TESTS="${GOLDEN_DEMO_SKIP_TESTS:-0}"

echo "=== Kitty Golden Demo ==="
echo "Base URL: ${BASE_URL}"
echo "Strict chat mode: ${STRICT_CHAT}"
echo "Skip tests: ${SKIP_TESTS}"

echo "[1/4] Pytest suite..."
if [[ "${SKIP_TESTS}" == "1" ]]; then
  echo "⏭️  Skipping pytest (GOLDEN_DEMO_SKIP_TESTS=1)"
else
  venv/bin/python -m pytest tests/ -q --tb=short
  echo "✅ Tests passed"
fi

echo "[2/4] Route smoke..."
if ./kitty status 2>&1 | grep -q "running"; then
  echo "✅ Kitty running"
else
  echo "❌ Kitty not running"
  exit 1
fi

if curl -sS "${BASE_URL}/api/brief" | grep -q "next_action"; then
  echo "✅ /api/brief OK"
else
  echo "❌ /api/brief failed"
  exit 1
fi

if curl -sS -X POST "${BASE_URL}/api/command" -H "Content-Type: application/json" -d '{"command":"/stuck"}' | grep -q "next_action"; then
  echo "✅ /api/command OK"
else
  echo "❌ /api/command failed"
  exit 1
fi

echo "[3/4] Normal chat..."
CHAT_JSON="$(curl -sS -X POST "${BASE_URL}/api/chat" -H "Content-Type: application/json" -d '{"message":"Hello, can you give me a brief response?"}')"
CHAT_TEXT="$(printf '%s' "$CHAT_JSON" | venv/bin/python -c 'import json,sys; print(json.load(sys.stdin).get("response",""))' 2>/dev/null || true)"

if [[ -z "${CHAT_TEXT}" ]]; then
  echo "❌ /api/chat returned empty response"
  exit 1
fi

if [[ "${CHAT_TEXT}" == *"No LLM API key configured"* ]] || [[ "${CHAT_TEXT}" == *"Provider fallback failed"* ]]; then
  if [[ "${STRICT_CHAT}" == "1" ]]; then
    echo "❌ /api/chat provider unavailable in strict mode"
    echo "    response: ${CHAT_TEXT}"
    exit 1
  fi
  echo "⚠️  /api/chat provider unavailable (non-strict): ${CHAT_TEXT}"
else
  echo "✅ /api/chat OK"
fi

echo "[4/4] Specialist example..."
CHAT_JSON_2="$(curl -sS -X POST "${BASE_URL}/api/chat" -H "Content-Type: application/json" -d '{"message":"My 2019 Ridgeline has a P0420 code, what should I check first?"}')"
CHAT_TEXT_2="$(printf '%s' "$CHAT_JSON_2" | venv/bin/python -c 'import json,sys; print(json.load(sys.stdin).get("response",""))' 2>/dev/null || true)"

if [[ -z "${CHAT_TEXT_2}" ]]; then
  echo "❌ Specialist chat response empty"
  exit 1
fi

if [[ "${CHAT_TEXT_2}" == *"No LLM API key configured"* ]] || [[ "${CHAT_TEXT_2}" == *"Provider fallback failed"* ]]; then
  if [[ "${STRICT_CHAT}" == "1" ]]; then
    echo "❌ Specialist chat unavailable in strict mode"
    echo "    response: ${CHAT_TEXT_2}"
    exit 1
  fi
  echo "⚠️  Specialist chat provider unavailable (non-strict)"
else
  echo "✅ Specialist chat OK"
fi

echo ""
echo "🎉 Golden demo checks complete"
