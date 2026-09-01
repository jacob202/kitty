#!/bin/bash
# Injects dynamic project context at session start.

manifest_hash() {
  {
    if command -v jq >/dev/null 2>&1 && [ -f package.json ]; then
      jq -S '.scripts // {}' package.json
    elif [ -f package.json ]; then
      cat package.json
    fi
    for f in pyproject.toml Cargo.toml go.mod Gemfile composer.json Makefile; do
      [ -f "$f" ] && cat "$f"
    done
  } 2>/dev/null | cksum | tr -d ' '
}

if [ "${DOTCLAUDE_FINGERPRINT:-0}" = "1" ]; then
  printf '{"setup_date":"%s","manifest_hash":"%s"}\n' "$(date +%Y-%m-%d)" "$(manifest_hash)"
  exit 0
fi

git rev-parse --git-dir >/dev/null 2>&1 || exit 0

HOOK_INPUT=$(cat 2>/dev/null || true)
SESSION_ID=""
if command -v jq >/dev/null 2>&1 && [ -n "$HOOK_INPUT" ]; then
  SESSION_ID=$(printf '%s' "$HOOK_INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)
fi
SAFE_SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -cd 'A-Za-z0-9._-')
GAR_STATE_DIR="${KITTY_GAR_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/kitty/gar-lifecycle}"
GAR_OUTBOX_DIR="${KITTY_GAR_OUTBOX_DIR:-$GAR_STATE_DIR/outbox}"
if [ -n "$SAFE_SESSION_ID" ]; then
  mkdir -p "$GAR_STATE_DIR" 2>/dev/null || true
  date +%s > "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" 2>/dev/null || true
fi

VERBOSE="${DOTCLAUDE_SESSION_VERBOSE:-0}"
CONTEXT=""
BRANCH=$(git branch --show-current 2>/dev/null)
if [ -n "$BRANCH" ]; then
  CONTEXT="Branch: $BRANCH"
else
  SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null)
  [ -n "$SHORT_SHA" ] && CONTEXT="HEAD: detached at $SHORT_SHA"
fi
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  CONTEXT="$CONTEXT | dirty"
fi

META="${DOTCLAUDE_META:-.claude/.dotclaude.json}"
if [ -f "$META" ]; then
  SAVED=$(grep -o '"manifest_hash"[: ]*"[^"]*"' "$META" 2>/dev/null | grep -o '"[^"]*"$' | tr -d '"')
  if [ -n "$SAVED" ] && [ "$(manifest_hash)" != "$SAVED" ]; then
    DRIFT="config drift: project manifests changed since setup. Re-run /setupdotclaude to re-tune"
    if [ -n "$CONTEXT" ]; then CONTEXT="$CONTEXT | $DRIFT"; else CONTEXT="$DRIFT"; fi
  fi
fi

if [ "$VERBOSE" = "1" ]; then
  LAST_COMMIT=$(git log --oneline -1 2>/dev/null)
  [ -n "$LAST_COMMIT" ] && CONTEXT="$CONTEXT | Last: $LAST_COMMIT"
  CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  [ "$CHANGES" -gt 0 ] 2>/dev/null && CONTEXT="$CONTEXT | $CHANGES files changed"
  if ! git diff --cached --quiet 2>/dev/null; then CONTEXT="$CONTEXT | staged"; fi
  STASH_COUNT=$(git stash list 2>/dev/null | wc -l | tr -d ' ')
  [ "$STASH_COUNT" -gt 0 ] 2>/dev/null && CONTEXT="$CONTEXT | $STASH_COUNT stash(es)"
  if command -v gh >/dev/null 2>&1; then
    PR_INFO=$(gh pr view --json number,title,state --jq '"PR #\(.number): \(.title) (\(.state))"' 2>/dev/null)
    [ -n "$PR_INFO" ] && CONTEXT="$CONTEXT | $PR_INFO"
  fi
fi
[ -n "$CONTEXT" ] && echo "$CONTEXT"

PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
ROOM_CLI="${KITTY_ROOM_CLI:-$PROJECT_ROOT/kitty}"

# Replay durable SessionEnd fallbacks before reading new room context.
if [ -x "$ROOM_CLI" ] && [ -d "$GAR_OUTBOX_DIR" ] && command -v jq >/dev/null 2>&1; then
  for queued in "$GAR_OUTBOX_DIR"/*.json; do
    [ -f "$queued" ] || continue
    QUEUED_CONTENT=$(jq -r '.content // empty' "$queued" 2>/dev/null || true)
    if [ -n "$QUEUED_CONTENT" ] && "$ROOM_CLI" room post --as claude --kind handoff "$QUEUED_CONTENT" >/dev/null 2>&1; then
      rm -f "$queued" 2>/dev/null || true
    fi
  done
fi

bounded_messages() {
  # Bound both per-message and total injected context. CLI text starts each
  # message with its durable message id, so one physical line is one message.
  awk '{ line=$0; if (length(line)>900) line=substr(line,1,900) "…"; print line }' \
    | head -n 8 | head -c 6000
}

if [ -x "$ROOM_CLI" ]; then
  RECENT_ERR=$(mktemp "${TMPDIR:-/tmp}/kitty-gar-recent.XXXXXX")
  DIRECT_ERR=$(mktemp "${TMPDIR:-/tmp}/kitty-gar-direct.XXXXXX")
  RECENT=$("$ROOM_CLI" room recent --limit 8 2>"$RECENT_ERR")
  RECENT_RC=$?
  if [ "$RECENT_RC" -ne 0 ]; then
    RECENT=$("$ROOM_CLI" room recent --limit 8 2>"$RECENT_ERR")
    RECENT_RC=$?
  fi
  DIRECT=$("$ROOM_CLI" room inbox --as claude --unread --direct-only --limit 8 2>"$DIRECT_ERR")
  DIRECT_RC=$?
  if [ "$DIRECT_RC" -ne 0 ]; then
    DIRECT=$("$ROOM_CLI" room inbox --as claude --unread --direct-only --limit 8 2>"$DIRECT_ERR")
    DIRECT_RC=$?
  fi

  if [ "$RECENT_RC" -eq 0 ] && [ "$DIRECT_RC" -eq 0 ]; then
    RECENT_BOUNDED=$(printf '%s\n' "$RECENT" | bounded_messages)
    # Remove direct rows already present in the recent window before injection.
    DIRECT_DEDUP=$(printf '%s\n' "$DIRECT" | awk -F: -v recent="$RECENT_BOUNDED" '
      { id=$1; if (id != "" && index(recent, id ":") == 0) print $0 }
    ')
    DIRECT_BOUNDED=$(printf '%s\n' "$DIRECT_DEDUP" | bounded_messages)
    echo ""
    echo "[GAR] workspace_global recent:"
    [ -n "$RECENT_BOUNDED" ] && echo "$RECENT_BOUNDED" || echo "(no recent messages)"
    echo "[GAR] unread direct for claude:"
    [ -n "$DIRECT_BOUNDED" ] && echo "$DIRECT_BOUNDED" || echo "(none; directs already shown above may still need ACK)"
    if [ -n "$SAFE_SESSION_ID" ]; then
      echo "[GAR] session receipt token: gar-session:$SAFE_SESSION_ID"
      echo "[GAR] When substantial assigned work finishes, run /session-end and include that token in the workspace_global handoff/result. Do not wait for Jacob to say session end."
    fi
    echo "[GAR] ACK direct messages only after receipt. Builder executes work; #490 owns collisions."
  else
    echo "[GAR] workspace_global unavailable at session start; do not treat this as an empty room."
    if [ "$RECENT_RC" -ne 0 ]; then
      RECENT_DIAG=$(head -c 500 "$RECENT_ERR" 2>/dev/null || true)
      echo "[GAR] recent failed (exit $RECENT_RC): ${RECENT_DIAG:-no diagnostic output}"
    fi
    if [ "$DIRECT_RC" -ne 0 ]; then
      DIRECT_DIAG=$(head -c 500 "$DIRECT_ERR" 2>/dev/null || true)
      echo "[GAR] direct inbox failed (exit $DIRECT_RC): ${DIRECT_DIAG:-no diagnostic output}"
    fi
    echo "[GAR] Any queued SessionEnd handoffs remain durable in $GAR_OUTBOX_DIR."
  fi
  rm -f "$RECENT_ERR" "$DIRECT_ERR" 2>/dev/null || true
else
  echo "[GAR] workspace_global unavailable at session start; Kitty room CLI not found."
fi

exit 0
