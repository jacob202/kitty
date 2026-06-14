#!/bin/bash
# DoneCheck hook — enforces "done = verified" before ending a session
# Runs before: session ends, PR is created, branch is pushed
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

echo ""
echo "=== Final Session Checklist ==="
echo ""

# Check 1: Uncommitted changes
dirty_count=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [[ "${dirty_count}" -gt 0 ]]; then
  echo "⚠️  UNCOMMITTED CHANGES: ${dirty_count} file(s)"
  echo "   Run: git status --short"
  echo ""
fi

# Check 2: Test baseline
echo "📋 TEST BASELINE (from CLAUDE.md):"
if grep -q "491 passed, 2 deselected" CLAUDE.md 2>/dev/null; then
  echo "   Expected: 491 passed, 2 deselected (bare pytest command)"
  actual=$(python3.11 -m pytest tests/ -q --tb=line 2>&1 | tail -3 | head -1 || echo "unknown")
  echo "   Actual:   ${actual}"
  if echo "${actual}" | grep -q "491 passed"; then
    echo "   ✅ Test baseline is green"
  else
    echo "   ❌ Test baseline mismatch — investigate before claiming done"
  fi
else
  echo "   ⚠️  CLAUDE.md baseline not found or outdated"
fi

echo ""

# Check 3: HANDOFF.md freshness
if [[ -f HANDOFF.md ]]; then
  last_updated=$(grep "^\\*\\*Last updated:\\*\\*" HANDOFF.md 2>/dev/null | head -1 || echo "not found")
  echo "📝 HANDOFF.md status:"
  echo "   ${last_updated}"
  echo "   (Update the timestamp and 'Current state' / 'Open items' before ending)"
else
  echo "❌ HANDOFF.md missing"
fi

echo ""
echo "Done = tests green + evidence shown + HANDOFF.md current."
echo "See CLAUDE.md operating protocol rule #6 ('Done means verified')"
