#!/usr/bin/env bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Kitty Quick Capture
# @raycast.mode silent
#
# Optional parameters:
# @raycast.icon 🐾
# @raycast.argument1 { "type": "text", "placeholder": "What should Kitty remember?" }
#
# Documentation:
# @raycast.description Save a text capture to Kitty's local inbox without opening chat.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${KITTY_PYTHON:-python3}"
CAPTURE_TEXT="${1:-}"

if [[ -z "${CAPTURE_TEXT// }" ]]; then
  echo "Nothing captured: type something for Kitty to remember." >&2
  exit 2
fi

inbox_args=()
if [[ -n "${KITTY_INBOX_FILE:-}" ]]; then
  inbox_args=(--inbox-file "$KITTY_INBOX_FILE")
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/quick_capture.py" \
  --source raycast_quick_capture \
  "${inbox_args[@]}" \
  "$CAPTURE_TEXT"
