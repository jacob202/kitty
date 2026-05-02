#!/usr/bin/env bash
# Cursor stop hook: nudge agent to update docs/STANDUP.md (followup_message).
set -euo pipefail
exec python3 <<'PY'
import json, sys
sys.stdin.read()
msg = (
    "Before ending: update docs/STANDUP.md handoff (Rule 10/11) — what you did, "
    "proof, what’s next for Jacob."
)
print(json.dumps({"followup_message": msg}))
PY
