#!/usr/bin/env bash
# UNUSED — Previously wired as Cursor **stop** hook; it printed follow-up JSON and caused the
# “Session really over? … STANDUP §9” line to repeat after every agent turn.
#
# To re-enable deliberate stop nags: add to .cursor/hooks.json:
#   "stop": [{ "command": ".cursor/hooks/cursor-standup-stop.sh" }]
#
# Safe no-op JSON (stdin ignored):
cat >/dev/null 2>&1 || true
echo "{}"
exit 0
