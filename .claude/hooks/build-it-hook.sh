#!/bin/bash
# Runs one of the build-it plugin's optional hardened-mode hooks.
#
# The plugin's docs want an absolute <PLUGIN_ROOT> baked into settings.json, and
# ${CLAUDE_PLUGIN_ROOT} only expands for plugin-declared hooks — not for hooks
# declared in project settings like these. Either would hardcode one machine's
# cache path, so the install is resolved at run time from Claude Code's own
# ledger, installed_plugins.json, which records the exact installPath chosen for
# this project. Scanning the shared cache directory instead would run whatever
# version some *other* project installed, and needed `sort -V`, which BSD sort
# on macOS does not have — that silently disabled both gates on the Mac.
#
# Fail-open: if the plugin is missing or unreadable we exit 0 and let the action
# through. Kitty's own hooks run before these; a third-party gate must never be
# what stops a turn. Every skip is logged, and the --check mode reports an
# unavailable gate out loud at session start so fail-open is never silent.
#
# Usage: build-it-hook.sh <hook-filename>
#        build-it-hook.sh --check

set -uo pipefail

LOG_PATH=".taskstate/hooks.log"
PLUGIN_ID="build-it@build-it"
LEDGER="${HOME}/.claude/plugins/installed_plugins.json"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

MODE="${1:-}"
CHECK_ONLY=false
if [ "$MODE" = "--check" ]; then
  CHECK_ONLY=true
  HOOK_NAME="turn-end-gate.py"
else
  HOOK_NAME="$MODE"
fi

log() {
  { mkdir -p "$(dirname "$LOG_PATH")" &&
    printf '%s [build-it-hook] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" >>"$LOG_PATH"
  } 2>/dev/null
}

# A gate that cannot run is reported, not swallowed: --check says so where the
# operator will see it, every other mode leaves a log line and allows the action.
unavailable() {
  log "skipped ${HOOK_NAME:-<none>}: $1"
  if [ "$CHECK_ONLY" = true ]; then
    echo "build-it hardened gates are NOT active: $1"
    echo "  Both hooks are declared in .claude/settings.json but cannot run."
    echo "  Reinstall with: claude plugin install ${PLUGIN_ID} --scope project"
  fi
  exit 0
}

[ -n "$HOOK_NAME" ] || unavailable "no hook name given"
command -v python3 >/dev/null 2>&1 || unavailable "python3 not on PATH"
[ -f "$LEDGER" ] || unavailable "plugin ledger not found at $LEDGER"

# Resolve THIS project's install, not the highest version in the shared cache.
PLUGIN_ROOT=$(python3 - "$LEDGER" "$PLUGIN_ID" "$PROJECT_DIR" <<'PY'
import json, os, sys

ledger_path, plugin_id, project_dir = sys.argv[1:4]
try:
    with open(ledger_path) as handle:
        entries = json.load(handle)["plugins"][plugin_id]
except (OSError, ValueError, KeyError, TypeError):
    sys.exit(1)

project_dir = os.path.realpath(project_dir)


def rank(entry):
    """This project's own install wins; a user-scope install is the fallback."""
    recorded = entry.get("projectPath")
    if recorded and os.path.realpath(recorded) == project_dir:
        return 0
    return 1 if entry.get("scope") == "user" else 2


for entry in sorted(entries, key=rank):
    path = entry.get("installPath")
    if path and os.path.isdir(path):
        print(path)
        break
else:
    sys.exit(1)
PY
)
[ -n "$PLUGIN_ROOT" ] || unavailable "no usable install recorded for ${PLUGIN_ID} in $LEDGER"

HOOK_SCRIPT="${PLUGIN_ROOT}/hooks/${HOOK_NAME}"
[ -f "$HOOK_SCRIPT" ] || unavailable "$HOOK_SCRIPT not found"

if [ "$CHECK_ONLY" = true ]; then
  exit 0
fi

# exec preserves the hook's stdin payload and its exit code, so a real block
# from the plugin still blocks.
exec python3 "$HOOK_SCRIPT"
