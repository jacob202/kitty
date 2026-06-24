#!/usr/bin/env bash
# PostToolUse — when pytest run shows FAILED, suggest /tdd-loop or /debug-fix.
# Reads tool output from $CLAUDE_TOOL_OUTPUT.

set -euo pipefail

INPUT="$(cat 2>/dev/null || true)"

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

OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"
[[ -z "$OUTPUT" ]] && exit 0

COMMAND=""
if command -v jq >/dev/null 2>&1 && [[ -n "$INPUT" ]]; then
  COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
fi

case "$COMMAND" in
  *pytest*|*"npm test"*|*"npm run test"*|*"pnpm test"*|*"bun test"*|*"vitest"*|*"jest"*)
    ;;
  *)
    exit 0
    ;;
esac

if grep -qE '(FAILED|ERROR|fail|^E\s|^[0-9]+ failed)' <<<"$OUTPUT"; then
  TDD_LOOP_SKILL="$(find_skill tdd-loop || true)"
  DEBUG_FIX_SKILL="$(find_skill debug-fix || true)"
  FAIL_COUNT=$(grep -oE '[0-9]+ failed' <<<"$OUTPUT" | head -1 | grep -oE '[0-9]+' || echo "?")
  echo ""
  echo "[tip] $FAIL_COUNT test(s) failing."
  if [[ -n "$TDD_LOOP_SKILL" && -n "$DEBUG_FIX_SKILL" ]]; then
    echo "[tip] Try:"
    echo "  /tdd-loop <test_path>   — auto-iterate until green"
    echo "  /debug-fix              — investigate root cause first"
  else
    echo "[tip] Missing skill suggestion target(s): tdd-loop=${TDD_LOOP_SKILL:-missing}, debug-fix=${DEBUG_FIX_SKILL:-missing}"
    echo "[tip] Expected local .claude/skills/<name>/SKILL.md or user-level ~/.claude/skills/<name>/SKILL.md."
  fi
fi

exit 0
