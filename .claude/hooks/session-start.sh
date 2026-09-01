#!/bin/bash
# Injects dynamic project context at session start.
#
# Default (minimal): branch + dirty/clean indicator. ~5-10 tokens.
# Set DOTCLAUDE_SESSION_VERBOSE=1 to also emit last commit, file count,
# staged status, stash count, and active PR info.

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
  if ! git diff --cached --quiet 2>/dev/null; then
    CONTEXT="$CONTEXT | staged"
  fi
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
PENDING_DIR="$GAR_STATE_DIR/pending"

# Replay any SessionEnd fallback that could not reach GAR. A successful replay
# removes the local pending record; failures stay durable for the next resume.
if [ -x "$ROOM_CLI" ] && [ -d "$PENDING_DIR" ]; then
  for pending in "$PENDING_DIR"/*.txt; do
    [ -f "$pending" ] || continue
    PENDING_CONTENT=$(cat "$pending" 2>/dev/null || true)
    if [ -n "$PENDING_CONTENT" ] && "$ROOM_CLI" room post --as claude --kind handoff "$PENDING_CONTENT" >/dev/null 2>&1; then
      rm -f "$pending" 2>/dev/null || true
    fi
  done
fi

# workspace_global is the primary mutable continuation channel. Recent room
# context and unread direct messages are fetched separately so broadcasts can
# never starve an older direct request to Claude.
if [ -x "$ROOM_CLI" ]; then
  GAR_OK=1
  RECENT=$("$ROOM_CLI" room recent --limit 12 2>/dev/null) || GAR_OK=0
  DIRECT=$("$ROOM_CLI" room inbox --as claude --unread --direct --limit 12 2>/dev/null) || GAR_OK=0
  if [ "$GAR_OK" = "1" ]; then
    echo ""
    echo "[GAR] workspace_global recent:"
    [ -n "$RECENT" ] && echo "$RECENT" || echo "(no recent messages)"
    echo "[GAR] unread direct for claude:"
    [ -n "$DIRECT" ] && echo "$DIRECT" || echo "(none)"
    if [ -n "$SAFE_SESSION_ID" ]; then
      echo "[GAR] session receipt token: gar-session:$SAFE_SESSION_ID"
      echo "[GAR] When substantial assigned work finishes, run session-end and include that token in the GAR handoff/result. Do not wait for Jacob to say session end."
    fi
    echo "[GAR] ACK direct messages only after receipt. Builder executes work; #490 owns collisions."
  else
    echo "[GAR] workspace_global unavailable at session start; pending handoffs remain local and durable."
  fi
else
  echo "[GAR] workspace_global unavailable at session start; Kitty room CLI not found."
fi

exit 0
