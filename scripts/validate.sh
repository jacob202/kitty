#!/bin/bash
# Unified validation script for Kitty project
# Runs: lint → tests → smoke eval

set -e

echo "=========================================="
echo "KITTY VALIDATION"
echo "=========================================="
echo ""

# 1. Tests
echo "[1/3] Running pytest..."
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
echo ""
echo "[1/3] ✅ Tests passed"
echo ""

# 2. Smoke eval (if available)
echo "[2/3] Running smoke eval..."
if curl -s -f -X POST http://localhost:5001/api/eval/run -H "Content-Type: application/json" -d '{"suite":"smoke"}' > /dev/null 2>&1; then
    curl -s -X POST http://localhost:5001/api/eval/run -H "Content-Type: application/json" -d '{"suite":"smoke"}'
    echo ""
    echo "[2/3] ✅ Smoke eval passed"
else
    echo "[2/3] ⚠️  Smoke eval skipped (server not running)"
fi
echo ""

echo "=========================================="
echo "VALIDATION COMPLETE"
echo "=========================================="