#!/usr/bin/env bash
# Kitty Session Starter — run at start of a coding session.
# Modes:
#   --quick (default): brief + setup + server checks + light route smoke
#   --full: includes full tests + golden demo (without duplicate pytest)
set -euo pipefail

MODE="${1:---quick}"
if [[ "$MODE" != "--quick" && "$MODE" != "--full" ]]; then
  echo "Usage: bash scripts/start-session.sh [--quick|--full]"
  exit 2
fi

if [[ -x "venv/bin/python" ]]; then
  PY="venv/bin/python"
else
  PY="python3"
fi

echo "=== Kitty Session Start (${MODE#--}) ==="
echo ""

echo "[1/6] KittyBuilder PM brief..."
"$PY" scripts/kitty_builder.py --brief | sed -n '1,80p'
echo ""

echo "[2/6] Verifying setup..."
bash scripts/verify_setup.sh
echo ""

echo "[3/6] Warming caches..."
if [[ -x "venv/bin/python" ]]; then
  venv/bin/python scripts/warm_cache.py 2>/dev/null || true
  if [[ ! -f "data/cache/file_index.json" ]]; then
    venv/bin/python scripts/build_file_index.py 2>/dev/null || true
  fi
fi
echo "✅ Caches warmed"
echo ""

if [[ "$MODE" == "--full" ]]; then
  echo "[4/6] Running full tests..."
  "$PY" -m pytest tests/ -q --tb=short 2>&1 | tail -1
else
  echo "[4/6] Quick baseline check..."
  if QUICK_OUT="$("$PY" -m pytest tests/test_builder_intake.py -q --tb=short 2>&1)"; then
    printf "%s\n" "$QUICK_OUT" | tail -1
    echo "✅ Quick baseline passed"
  else
    printf "%s\n" "$QUICK_OUT" | tail -3
    echo "⚠️  Quick baseline failed (quick mode continues). Investigate before risky work."
  fi
fi
echo ""

echo "[5/6] Checking server status..."
if ./kitty status 2>&1 | grep -q "running"; then
    echo "✅ Server running"
    if curl -sS http://localhost:5001/api/brief | grep -q "next_action"; then
      echo "✅ /api/brief smoke passed"
    else
      echo "⚠️  /api/brief smoke failed"
    fi
else
    echo "⚠️  Server not running — start with: ./kitty"
fi
echo ""

echo "[6/6] Golden demo..."
if [[ "$MODE" == "--full" ]]; then
  if GOLDEN_DEMO_SKIP_TESTS=1 bash scripts/golden_demo.sh 2>&1 | tail -6 | grep -q "Golden demo checks complete"; then
      echo "✅ Golden demo passed"
  else
      echo "⚠️  Golden demo had issues — run: bash scripts/golden_demo.sh"
  fi
else
  echo "⏭️  Skipped in quick mode. Run '--full' for full demo."
fi
echo ""
echo "=== Session ready ==="
