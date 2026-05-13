#!/usr/bin/env bash
# Kitty — Cursor sessionStart: inject compact standup block (same source as Claude hook).
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/_standup_compact_json.py"
