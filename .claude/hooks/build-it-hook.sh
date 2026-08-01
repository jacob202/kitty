#!/bin/bash
# Runs one of the build-it plugin's optional hardened-mode hooks.
#
# The plugin's own docs want an absolute <PLUGIN_ROOT> baked into settings.json,
# and ${CLAUDE_PLUGIN_ROOT} only expands for plugin-declared hooks — not for
# hooks declared in project settings like these. Either would hardcode this
# container's cache path and break on the Mac, so resolve the path at run time.
#
# Fail-open: if the plugin is missing, moved, or unreadable we exit 0 and let the
# action through. Kitty's own hooks run before these; a third-party gate must
# never be what stops a turn. Every skip is logged so a silently absent gate is
# still diagnosable — the plugin's own hooks log to the same file.
#
# Usage: build-it-hook.sh <hook-filename>

set -uo pipefail

LOG_PATH=".taskstate/hooks.log"

# Never let logging itself break the hook chain.
skip() {
  { mkdir -p "$(dirname "$LOG_PATH")" &&
    printf '%s [build-it-hook] skipped %s: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${HOOK_NAME:-<none>}" "$1" >>"$LOG_PATH"
  } 2>/dev/null
  exit 0
}

HOOK_NAME="${1:-}"
[ -n "$HOOK_NAME" ] || skip "no hook name given"

CACHE_DIR="${HOME}/.claude/plugins/cache/build-it/build-it"
[ -d "$CACHE_DIR" ] || skip "plugin not installed ($CACHE_DIR missing)"

# Highest installed version wins; the cache keeps one directory per version.
PLUGIN_ROOT=$(find "$CACHE_DIR" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort -V | tail -1)
[ -n "$PLUGIN_ROOT" ] || skip "no version directory under $CACHE_DIR"

HOOK_SCRIPT="${PLUGIN_ROOT}/hooks/${HOOK_NAME}"
[ -f "$HOOK_SCRIPT" ] || skip "$HOOK_SCRIPT not found"

command -v python3 >/dev/null 2>&1 || skip "python3 not on PATH"

# exec preserves the hook's stdin payload and its exit code, so a real block
# from the plugin still blocks.
exec python3 "$HOOK_SCRIPT"
