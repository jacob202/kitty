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
# never be what stops a turn.
#
# Usage: build-it-hook.sh <hook-filename>

set -uo pipefail

HOOK_NAME="${1:-}"
if [ -z "$HOOK_NAME" ]; then
  exit 0
fi

CACHE_DIR="${HOME}/.claude/plugins/cache/build-it/build-it"
[ -d "$CACHE_DIR" ] || exit 0

# Highest installed version wins; the cache keeps one directory per version.
PLUGIN_ROOT=$(find "$CACHE_DIR" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort -V | tail -1)
[ -n "$PLUGIN_ROOT" ] || exit 0

HOOK_SCRIPT="${PLUGIN_ROOT}/hooks/${HOOK_NAME}"
[ -f "$HOOK_SCRIPT" ] || exit 0

command -v python3 >/dev/null 2>&1 || exit 0

# exec preserves the hook's stdin payload and its exit code, so a real block
# from the plugin still blocks.
exec python3 "$HOOK_SCRIPT"
