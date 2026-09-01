#!/usr/bin/env bash
# Stop — safety net for the memory loop. A shell hook can't summarize the
# conversation itself, so the rich thread note is Kitty's job to write
# before ending. This hook only checks the note actually got written today
# and nudges if it didn't, so the thread never silently drops.

set -euo pipefail

SCRATCHPAD="config/SOUL_SCRATCHPAD.md"
TODAY=$(date +%Y-%m-%d)

[[ ! -f "$SCRATCHPAD" ]] && exit 0

# Did Kitty append an entry dated today?
if grep -q "^## $TODAY" "$SCRATCHPAD" 2>/dev/null; then
  exit 0
fi

echo "[memory] No thread note for $TODAY yet. Before ending, append 3-5 lines to"
echo "[memory] $SCRATCHPAD under a '## $TODAY' header: what Jacob wanted, what"
echo "[memory] landed, and the next concrete step. That's what next session reads back."
exit 0
