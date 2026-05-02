#!/bin/bash
# Kitty Session Starter — run at the start of every session
set -e

echo "=== Kitty Session Start ==="
echo ""

echo "[1/5] KittyBuilder PM brief..."
python3 scripts/kitty_builder.py --brief | sed -n '1,80p'
echo ""

echo "[2/5] Verifying setup..."
bash scripts/verify_setup.sh
echo ""

echo "[3/5] Running tests..."
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short 2>&1 | tail -1
echo ""

echo "[4/5] Checking server status..."
if ./kitty status 2>&1 | grep -q "running"; then
    echo "✅ Server running"
else
    echo "⚠️  Server not running — start with: ./kitty"
fi
echo ""

echo "[5/5] Golden demo..."
if bash scripts/golden_demo.sh 2>&1 | tail -3 | grep -q "passed"; then
    echo "✅ Golden demo passed"
else
    echo "⚠️  Golden demo had issues — check scripts/golden_demo.sh output"
fi
echo ""
echo "=== Session ready ==="
