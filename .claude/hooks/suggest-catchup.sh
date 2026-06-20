#!/usr/bin/env bash
# SessionStart — if handoff doc exists and was recently updated, suggest /catchup.

set -euo pipefail

find_skill() {
  local skill_name="$1"
  local skill_path

  for skill_path in ".claude/skills/$skill_name/SKILL.md" "$HOME/.claude/skills/$skill_name/SKILL.md"; do
    if [[ -f "$skill_path" ]]; then
      printf '%s\n' "$skill_path"
      return 0
    fi
  done

  return 1
}

HANDOFF="docs/AGENT_HANDOFF.md"
[[ ! -f "$HANDOFF" ]] && exit 0

CATCHUP_SKILL="$(find_skill catchup || true)"
SHIP_SKILL="$(find_skill ship || true)"

# Only suggest if handoff was updated in last 7 days
if command -v find &>/dev/null && [[ -n "$(find "$HANDOFF" -mtime -7 2>/dev/null)" ]]; then
  echo ""
  echo "[session] Found recent handoff at $HANDOFF"
  if [[ -n "$CATCHUP_SKILL" && -n "$SHIP_SKILL" ]]; then
    echo "[tip] Run /catchup to pick up where you left off, or /ship to wrap and commit."
  else
    echo "[session] Missing skill suggestion target(s): catchup=${CATCHUP_SKILL:-missing}, ship=${SHIP_SKILL:-missing}"
    echo "[session] Expected local .claude/skills/<name>/SKILL.md or user-level ~/.claude/skills/<name>/SKILL.md."
  fi
fi

# Also flag uncommitted changes
if git -C . status --porcelain 2>/dev/null | grep -q .; then
  CHANGED=$(git -C . status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [[ -n "$CATCHUP_SKILL" && -n "$SHIP_SKILL" ]]; then
    echo "[session] $CHANGED uncommitted change(s) — /ship if ready, /catchup to review"
  else
    echo "[session] $CHANGED uncommitted change(s)"
    echo "[session] Missing skill suggestion target(s): catchup=${CATCHUP_SKILL:-missing}, ship=${SHIP_SKILL:-missing}"
  fi
fi

exit 0
