#!/usr/bin/env bash
set -euo pipefail

echo "=== Setup Verification ==="

if [[ -x "venv/bin/python" ]]; then
  PY="venv/bin/python"
  PIP="venv/bin/pip"
else
  PY="python3"
  PIP="pip3"
fi

echo "1. Local model host (Ollama)..."
curl -sS localhost:11434/api/tags >/dev/null \
  && echo "   ✅ Ollama running" \
  || echo "   ⚠️ Ollama not running (optional unless local model path is used)"

echo "2. ChromaDB import..."
"$PY" -c "import chromadb; chromadb.Client()" 2>/dev/null \
  && echo "   ✅ ChromaDB accessible" \
  || echo "   ❌ ChromaDB import failed"

echo "3. LightRAG import..."
"$PY" -c "import lightrag" 2>/dev/null \
  && echo "   ✅ LightRAG installed" \
  || echo "   ⚠️ LightRAG not installed (optional unless KITTY_BUILDER_USE_LIGHTRAG=1)"

echo "4. Python dependencies..."
"$PIP" check 2>/dev/null | grep -q "No broken requirements found" \
  && echo "   ✅ No broken dependencies" \
  || echo "   ⚠️ Dependency issues detected (run '$PIP check' for details)"

echo "5. Canonical project files..."
[[ -f "scripts/kitty_builder.py" ]] \
  && echo "   ✅ scripts/kitty_builder.py present" \
  || echo "   ❌ scripts/kitty_builder.py missing"
[[ -f "TASKS.md" ]] \
  && echo "   ✅ TASKS.md present" \
  || echo "   ❌ TASKS.md missing"
[[ -f "docs/STANDUP.md" ]] \
  && echo "   ✅ docs/STANDUP.md present" \
  || echo "   ❌ docs/STANDUP.md missing"
