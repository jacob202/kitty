#!/bin/bash
# PostToolUse hook for Write|Edit: auto-fix and format the one file just touched.
# The edited path arrives in stdin JSON, not an env var.
# ponytail: Python only — no prettier/eslint installed, and project-wide
# `tsc --noEmit` per edit is too slow to run on every keystroke.

command -v jq >/dev/null 2>&1 || exit 0

FILE_PATH=$(jq -r '.tool_input.file_path // empty')
[ -n "$FILE_PATH" ] || exit 0
[ -f "$FILE_PATH" ] || exit 0

RUFF="${CLAUDE_PROJECT_DIR:-.}/venv/bin/ruff"
command -v "$RUFF" >/dev/null 2>&1 || RUFF=$(command -v ruff) || exit 0

case "$FILE_PATH" in
  *.py)
    "$RUFF" check --fix --quiet "$FILE_PATH" 2>&1 | head -20
    "$RUFF" format --quiet "$FILE_PATH" >/dev/null 2>&1
    ;;
esac

exit 0
