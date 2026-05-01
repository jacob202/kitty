#!/bin/bash
# Clear Python bytecode cache, run full test suite, report pass count.
# Use after model routing fixes, dependency changes, or anything where
# linter auto-reverts have been observed.

set -e

cd "$(dirname "$0")/.."

echo "→ Clearing .pyc cache..."
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

echo "→ Running full test suite..."
RESULT=$(venv/bin/python -m pytest tests/ -q --tb=short 2>&1 | tail -5)
echo "$RESULT"

# Extract pass count for easy grep
PASSED=$(echo "$RESULT" | grep -oE '[0-9]+ passed' | head -1)
echo ""
echo "✓ Result: ${PASSED:-no pass count detected}"
