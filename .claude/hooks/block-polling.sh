#!/usr/bin/env bash
# Block CI polling loops. Waiting on PR checks should use `gh pr checks
# --watch` or `gh pr merge --auto`, never until/while/for + sleep loops.
# A blocked command costs nothing; a 16x sleep loop costs 16 round-trips.
set -euo pipefail

input=$(cat 2>/dev/null || true)
cmd=$(printf '%s' "$input" | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception:
    print("")' 2>/dev/null || true)

[ -z "$cmd" ] && exit 0

has_sleep=$(printf '%s' "$cmd" | grep -qE '\bsleep\b' && echo 1 || echo 0)
has_gh_wait=$(printf '%s' "$cmd" | grep -qE '(until|while|for).*(gh pr (checks|view|status)|gh run view|gh pr merge)' && echo 1 || echo 0)

if [ "$has_sleep" = "1" ] && [ "$has_gh_wait" = "1" ]; then
  echo "BLOCKED: CI polling loop detected. Polling wastes an agent round-trip per iteration." >&2
  echo "" >&2
  echo "Use instead:" >&2
  echo "  gh pr checks <N> --watch      # one command, exits when checks finish" >&2
  echo "  gh pr merge <N> --auto        # GitHub merges automatically when checks pass" >&2
  echo "" >&2
  echo "If you must wait a bounded time, use: gh pr checks <N> --watch --interval 15" >&2
  exit 2
fi

exit 0
