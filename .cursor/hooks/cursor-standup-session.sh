#!/usr/bin/env bash
# Cursor sessionStart hook: inject docs/STANDUP.md into agent context (JSON on stdout).
set -euo pipefail
export KITTY_HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python3 <<'PY'
import json, os, sys
from pathlib import Path

root = Path(os.environ["KITTY_HOOK_ROOT"])
try:
    payload = json.load(sys.stdin)
except json.JSONDecodeError:
    payload = {}
roots = payload.get("workspace_roots") or []
base = Path(roots[0]) if roots else root
standup_path = base / "docs" / "STANDUP.md"
if not standup_path.is_file():
    standup_path = root / "docs" / "STANDUP.md"
text = standup_path.read_text(encoding="utf-8") if standup_path.is_file() else ""
block = f"## Project standup ({standup_path.name})\n\n{text}"
print(json.dumps({"continue": True, "additional_context": block}))
PY
