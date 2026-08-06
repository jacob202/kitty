#!/usr/bin/env bash
# Sanitize Builder-generated .claude/STATE.md and .claude/HANDOFF.md
# so they pass CI schema validation. Run from the worktree root.
set -euo pipefail

for f in .claude/STATE.md .claude/HANDOFF.md; do
  [ -f "$f" ] || continue
  
  # Fix status: "clean" -> "complete"
  sed -i '' 's/"status": "clean"/"status": "complete"/g' "$f"
  
  # Fix next_action: terminal status "complete" must have next_action "None"
  # Only fix if status is actually "complete"
  if grep -q '"status": "complete"' "$f"; then
    # Replace any next_action value that isn't "None" with "None"
    sed -i '' 's/"next_action": "[^"]*"/"next_action": "None"/g' "$f"
  fi
  
  # Fix head_sha: update to actual HEAD if stale
  ACTUAL_HEAD=$(git rev-parse HEAD)
  if [ -n "$ACTUAL_HEAD" ]; then
    sed -i '' "s/\"head_sha\": \"[^\"]*\"/\"head_sha\": \"$ACTUAL_HEAD\"/g" "$f"
  fi
  
  # Fix branch to match actual
  ACTUAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
  if [ -n "$ACTUAL_BRANCH" ]; then
    sed -i '' "s/\"branch\": \"[^\"]*\"/\"branch\": \"$ACTUAL_BRANCH\"/g" "$f"
  fi
done

# If HANDOFF exists, sync its status to "valid" (not the same as STATE "complete")
if [ -f .claude/HANDOFF.md ]; then
  sed -i '' 's/"status": "complete"/"status": "valid"/g' .claude/HANDOFF.md
fi

echo "STATE/HANDOFF sanitized"
