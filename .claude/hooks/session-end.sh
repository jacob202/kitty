#!/usr/bin/env bash
# SessionEnd — last-chance durability for workspace_global.
#
# Normal completion is model-owned: the Stop completion check sends Claude back
# to run /session-end only when substantial assigned work is genuinely done.
# SessionEnd cannot block termination, so this command hook only supplies a
# durable fallback if that normal token-bearing handoff is absent.

set -uo pipefail

HOOK_INPUT=$(cat 2>/dev/null || true)
if ! command -v jq >/dev/null 2>&1; then
  echo "[GAR] SessionEnd fallback unavailable because jq is missing." >&2
  exit 0
fi
if [ -z "$HOOK_INPUT" ] || ! printf '%s' "$HOOK_INPUT" | jq -e 'type == "object"' >/dev/null 2>&1; then
  echo "[GAR] SessionEnd fallback received unreadable hook state." >&2
  exit 0
fi

SESSION_ID=$(printf '%s' "$HOOK_INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)
REASON=$(printf '%s' "$HOOK_INPUT" | jq -r '.reason // "other"' 2>/dev/null || printf 'other')
TRANSCRIPT=$(printf '%s' "$HOOK_INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || true)
SAFE_SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -cd 'A-Za-z0-9._-')
[ -n "$SAFE_SESSION_ID" ] || exit 0

TOKEN="gar-session:$SAFE_SESSION_ID"
GAR_STATE_DIR="${KITTY_GAR_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/kitty/gar-lifecycle}"
GAR_OUTBOX_DIR="${KITTY_GAR_OUTBOX_DIR:-$GAR_STATE_DIR/outbox}"
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
ROOM_CLI="${KITTY_ROOM_CLI:-$PROJECT_ROOT/kitty}"

# Matching token means the model already ran the normal session-end workflow.
if [ -x "$ROOM_CLI" ]; then
  RECENT_JSON=$("$ROOM_CLI" room recent --limit 100 --json 2>/dev/null || true)
  if [ -n "$RECENT_JSON" ] && printf '%s' "$RECENT_JSON" | jq -e --arg token "$TOKEN" '
    any(.[]?;
      .sender_id == "claude"
      and (.message_kind == "handoff" or .message_kind == "result")
      and ((.content // "") | contains($token))
    )
  ' >/dev/null 2>&1; then
    rm -f "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" "$GAR_OUTBOX_DIR/$SAFE_SESSION_ID.json" 2>/dev/null || true
    exit 0
  fi
fi

LAST_MESSAGE=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  LAST_MESSAGE=$(jq -rs '
    [ .[]
      | select(.type == "assistant")
      | (.message.content? // [])[]?
      | select(.type == "text")
      | .text
    ] | last // empty
  ' "$TRANSCRIPT" 2>/dev/null || true)
fi

BRANCH=$(git branch --show-current 2>/dev/null || true)
HEAD_SHA=$(git rev-parse HEAD 2>/dev/null || true)
if [ -n "$LAST_MESSAGE" ]; then
  SUMMARY="${LAST_MESSAGE:0:2400}"
else
  SUMMARY="Session ended before a model-authored final summary. Inspect branch ${BRANCH:-unknown} at ${HEAD_SHA:-unknown}."
fi
FALLBACK="[$TOKEN] Automatic SessionEnd fallback (reason=$REASON). $SUMMARY"

if [ -x "$ROOM_CLI" ]; then
  if "$ROOM_CLI" room post --as claude --kind handoff "$FALLBACK" >/dev/null 2>&1; then
    rm -f "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" "$GAR_OUTBOX_DIR/$SAFE_SESSION_ID.json" 2>/dev/null || true
    exit 0
  fi
fi

# SessionEnd cannot block, so failed delivery becomes a durable local outbox
# record. SessionStart replays these before reading new room context.
if mkdir -p "$GAR_OUTBOX_DIR" 2>/dev/null; then
  TMP_OUTBOX="$GAR_OUTBOX_DIR/.${SAFE_SESSION_ID}.$$"
  if jq -n --arg content "$FALLBACK" --arg session_id "$SAFE_SESSION_ID" \
      '{session_id:$session_id,content:$content}' > "$TMP_OUTBOX" 2>/dev/null \
      && mv "$TMP_OUTBOX" "$GAR_OUTBOX_DIR/$SAFE_SESSION_ID.json" 2>/dev/null; then
    echo "[GAR] workspace_global handoff queued locally for replay on next SessionStart." >&2
    exit 0
  fi
  rm -f "$TMP_OUTBOX" 2>/dev/null || true
fi

echo "[GAR] CRITICAL: could not post or persist SessionEnd fallback for $SAFE_SESSION_ID." >&2
exit 0
