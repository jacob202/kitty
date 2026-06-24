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
  if [[ -n "$CATCHUP_SKILL" && -n "$SHIP_SKILL" ]]; then
    echo "[session] Recent handoff: $HANDOFF. /catchup to resume, /ship when ready."
  elif [[ -n "$CATCHUP_SKILL" ]]; then
    echo "[session] Recent handoff: $HANDOFF. /catchup to resume."
  else
    echo "[session] Recent handoff: $HANDOFF."
  fi
fi

# Also flag uncommitted changes
if git -C . status --porcelain 2>/dev/null | grep -q .; then
  CHANGED=$(git -C . status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [[ -n "$CATCHUP_SKILL" && -n "$SHIP_SKILL" ]]; then
    echo "[session] $CHANGED uncommitted change(s) — /catchup to review, /ship if ready."
  elif [[ -n "$CATCHUP_SKILL" ]]; then
    echo "[session] $CHANGED uncommitted change(s) — /catchup to review."
  elif [[ -n "$SHIP_SKILL" ]]; then
    echo "[session] $CHANGED uncommitted change(s) — /ship if ready."
  else
    echo "[session] $CHANGED uncommitted change(s)"
  fi
fi

exit 0
