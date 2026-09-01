#!/usr/bin/env bash
# Stop — make session-end continuity automatic.
#
# First completion attempt: require the agent to run /session-end unless this
# session already posted a durable GAR handoff/result. The continuation pass
# accepts that receipt; if the skill still did not post one, publish the final
# assistant summary as a bounded fallback so Jacob never has to type
# "session end" just to preserve continuity.

set -uo pipefail

HOOK_INPUT=$(cat 2>/dev/null || true)
SESSION_ID=""
STOP_HOOK_ACTIVE="false"
LAST_MESSAGE=""
HAS_ACTIVE_BACKGROUND="false"

if ! command -v jq >/dev/null 2>&1; then
  echo "[GAR] stop lifecycle gate unavailable because jq is missing; allowing stop to avoid a loop." >&2
  exit 0
fi
if [ -z "$HOOK_INPUT" ] || ! printf '%s' "$HOOK_INPUT" | jq -e 'type == "object"' >/dev/null 2>&1; then
  echo "[GAR] stop lifecycle gate received unreadable hook state; allowing stop to avoid a loop." >&2
  exit 0
fi

if [ -n "$HOOK_INPUT" ]; then
  SESSION_ID=$(printf '%s' "$HOOK_INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)
  STOP_HOOK_ACTIVE=$(printf '%s' "$HOOK_INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
  LAST_MESSAGE=$(printf '%s' "$HOOK_INPUT" | jq -r '.last_assistant_message // empty' 2>/dev/null || true)
  HAS_ACTIVE_BACKGROUND=$(printf '%s' "$HOOK_INPUT" | jq -r '
    ([.background_tasks[]?, .session_crons[]?]
      | any(.status? as $s | ($s == "running" or $s == "pending" or $s == "queued" or $s == "in_progress")))
  ' 2>/dev/null || printf 'false')
fi

# Do not turn an intermediate stop while work is still running into a handoff.
[ "$HAS_ACTIVE_BACKGROUND" = "true" ] && exit 0

SAFE_SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -cd 'A-Za-z0-9._-')
GAR_STATE_DIR="${KITTY_GAR_STATE_DIR:-${TMPDIR:-/tmp}/kitty-gar-lifecycle}"
STARTED_AT=""
if [ -n "$SAFE_SESSION_ID" ] && [ -f "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" ]; then
  STARTED_AT=$(tr -cd '0-9.' < "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" 2>/dev/null || true)
fi

PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
ROOM_CLI="${KITTY_ROOM_CLI:-$PROJECT_ROOT/kitty}"
ROOM_AVAILABLE=false
HAS_RECEIPT=false
RECEIPT_TOKEN="gar-session:${SAFE_SESSION_ID:-unknown}"
if [ -x "$ROOM_CLI" ]; then
  RECENT_JSON=$($ROOM_CLI room recent --limit 100 --json 2>/dev/null)
  if [ $? -eq 0 ]; then
    ROOM_AVAILABLE=true
    if [ -n "$STARTED_AT" ] && command -v jq >/dev/null 2>&1; then
      if printf '%s' "$RECENT_JSON" | jq -e --argjson started "$STARTED_AT" --arg token "$RECEIPT_TOKEN" '
        any(.[]?;
          .sender_id == "claude"
          and (.message_kind == "handoff" or .message_kind == "result")
          and ((.created_at // 0) >= $started)
          and ((.content // "") | contains($token))
        )
      ' >/dev/null 2>&1; then
        HAS_RECEIPT=true
      fi
    fi
  fi
fi

# A real same-session handoff/result is sufficient continuity evidence.
if [ "$HAS_RECEIPT" = "true" ]; then
  [ -n "$SAFE_SESSION_ID" ] && rm -f "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" 2>/dev/null || true
  exit 0
fi

if [ "$STOP_HOOK_ACTIVE" != "true" ]; then
  printf '{"decision":"block","reason":"Before ending, run /session-end now, then ensure its verified workspace_global handoff/result includes receipt token %s. Jacob should not have to type session end manually."}\n' "$RECEIPT_TOKEN"
  exit 0
fi
# Stop hooks can re-enter after a blocking decision. On that continuation pass,
# do not create a loop: if /session-end did not leave a receipt, preserve the
# final assistant summary as the minimal durable fallback.
if [ "$ROOM_AVAILABLE" = "true" ] && [ -n "$LAST_MESSAGE" ]; then
  FALLBACK="[$RECEIPT_TOKEN] Automatic session-end fallback from Claude. Final assistant summary: ${LAST_MESSAGE:0:2400}"
  if "$ROOM_CLI" room post --as claude --kind handoff "$FALLBACK" >/dev/null 2>&1; then
    [ -n "$SAFE_SESSION_ID" ] && rm -f "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" 2>/dev/null || true
    exit 0
  fi
fi

if [ "$ROOM_AVAILABLE" != "true" ]; then
  echo "[GAR] workspace_global unavailable during final stop; allowing stop to avoid a lifecycle loop." >&2
else
  echo "[GAR] automatic final handoff failed; allowing stop to avoid a lifecycle loop." >&2
fi

# Preserve the older memory-loop nudge as a compatibility fallback. GAR is the
# primary cross-agent continuation channel; this note is only local context.
SCRATCHPAD="config/SOUL_SCRATCHPAD.md"
TODAY=$(date +%Y-%m-%d)
if [ -f "$SCRATCHPAD" ] && ! grep -q "^## $TODAY" "$SCRATCHPAD" 2>/dev/null; then
  echo "[memory] No thread note for $TODAY yet in $SCRATCHPAD." >&2
fi

exit 0
