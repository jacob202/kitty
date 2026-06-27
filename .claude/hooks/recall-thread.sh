#!/usr/bin/env bash
# SessionStart — read the thread back in. Surfaces the most recent
# SOUL_SCRATCHPAD entry and any durable preferences so Kitty opens a
# session already knowing where things were left, instead of cold.
#
# Token-cheap by design: caps the scratchpad readback so a long history
# never floods context. Only the latest entry carries the live thread.

set -euo pipefail

SCRATCHPAD="config/SOUL_SCRATCHPAD.md"
PREFS="config/PREFERENCES.md"
MAX_LINES=25

# Most recent scratchpad entry: everything from the last "## " header to EOF.
if [[ -f "$SCRATCHPAD" ]]; then
  LAST_ENTRY=$(awk '/^## /{buf=""} {buf=buf $0 "\n"} END{printf "%s", buf}' "$SCRATCHPAD" 2>/dev/null \
    | grep -v '^<!--' | sed '/^$/d' | head -n "$MAX_LINES")
  if [[ -n "${LAST_ENTRY// /}" ]]; then
    echo ""
    echo "[thread] Picking up from last session:"
    echo "$LAST_ENTRY"
  fi
fi

# Durable preferences — only the actual entries (lines starting with "- "),
# never the explanatory prose. Kept short by design.
if [[ -f "$PREFS" ]]; then
  PREF_BODY=$(grep '^- ' "$PREFS" 2>/dev/null | head -n 30)
  if [[ -n "${PREF_BODY// /}" ]]; then
    echo ""
    echo "[prefs] Jacob's standing preferences:"
    echo "$PREF_BODY"
  fi
fi

exit 0
