#!/bin/bash
# Injects dynamic project context at session start.
#
# Default (minimal): branch + dirty/clean indicator. ~5-10 tokens.
# Set DOTCLAUDE_SESSION_VERBOSE=1 to also emit last commit, file count,
# staged status, stash count, and active PR info. ~30-90 tokens, plus
# a network round-trip if `gh` is installed.
#
# Drift nudge: /setupdotclaude saves a fingerprint of the project's
# manifests to .claude/.dotclaude.json (via DOTCLAUDE_FINGERPRINT=1 mode
# below). When the manifests later change, this hook appends a one-line
# nudge to re-run /setupdotclaude. Zero output when nothing drifted.

# Hash the parts of the project manifests that change Claude's config:
# package.json scripts (stable-sorted) plus other manifests wholesale.
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

# Fingerprint mode: print the fingerprint JSON and exit.
# Used by /setupdotclaude: DOTCLAUDE_FINGERPRINT=1 session-start.sh > .claude/.dotclaude.json
if [ "${DOTCLAUDE_FINGERPRINT:-0}" = "1" ]; then
  printf '{"setup_date":"%s","manifest_hash":"%s"}\n' "$(date +%Y-%m-%d)" "$(manifest_hash)"
  exit 0
fi

# Bail early if not in a git repo (nothing useful to inject).
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Claude Code passes hook context on stdin. Record a per-session start marker in
# tmp storage so the Stop hook can distinguish this session's GAR receipts from
# older room traffic without touching the repository.
HOOK_INPUT=$(cat 2>/dev/null || true)
SESSION_ID=""
if command -v jq >/dev/null 2>&1 && [ -n "$HOOK_INPUT" ]; then
  SESSION_ID=$(printf '%s' "$HOOK_INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)
fi
SAFE_SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -cd 'A-Za-z0-9._-')
GAR_STATE_DIR="${KITTY_GAR_STATE_DIR:-${TMPDIR:-/tmp}/kitty-gar-lifecycle}"
if [ -n "$SAFE_SESSION_ID" ]; then
  mkdir -p "$GAR_STATE_DIR" 2>/dev/null || true
  date +%s > "$GAR_STATE_DIR/$SAFE_SESSION_ID.start" 2>/dev/null || true
fi

VERBOSE="${DOTCLAUDE_SESSION_VERBOSE:-0}"
CONTEXT=""

# Branch (essential, cheap).
BRANCH=$(git branch --show-current 2>/dev/null)
if [ -n "$BRANCH" ]; then
  CONTEXT="Branch: $BRANCH"
else
  SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null)
  [ -n "$SHORT_SHA" ] && CONTEXT="HEAD: detached at $SHORT_SHA"
fi

# Dirty indicator (binary, ~free, very useful).
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  CONTEXT="$CONTEXT | dirty"
fi

# Config drift nudge (one short line, only when manifests changed since setup).
META="${DOTCLAUDE_META:-.claude/.dotclaude.json}"
if [ -f "$META" ]; then
  SAVED=$(grep -o '"manifest_hash"[: ]*"[^"]*"' "$META" 2>/dev/null | grep -o '"[^"]*"$' | tr -d '"')
  if [ -n "$SAVED" ] && [ "$(manifest_hash)" != "$SAVED" ]; then
    DRIFT="config drift: project manifests changed since setup. Re-run /setupdotclaude to re-tune"
    if [ -n "$CONTEXT" ]; then CONTEXT="$CONTEXT | $DRIFT"; else CONTEXT="$DRIFT"; fi
  fi
fi

# Verbose extras (opt-in via DOTCLAUDE_SESSION_VERBOSE=1).
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

# workspace_global is the primary mutable cross-agent continuation channel.
# SessionStart fires both for new sessions and resumes, so inject a bounded recent
# window plus Claude's unread direct inbox every time. Never auto-ack here: the
# model must actually receive/read the injected message before acknowledgement.
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
ROOM_CLI="${KITTY_ROOM_CLI:-$PROJECT_ROOT/kitty}"
if [ -x "$ROOM_CLI" ]; then
  GAR_OK=1
  RECENT=$("$ROOM_CLI" room recent --limit 12 2>/dev/null) || GAR_OK=0
  INBOX=$("$ROOM_CLI" room inbox --as claude --unread --limit 12 2>/dev/null) || GAR_OK=0
  if [ "$GAR_OK" = "1" ]; then
    echo ""
    echo "[GAR] workspace_global recent:"
    [ -n "$RECENT" ] && echo "$RECENT" || echo "(no recent messages)"
    echo "[GAR] unread for claude:"
    [ -n "$INBOX" ] && echo "$INBOX" || echo "(none)"
    echo "[GAR] Read relevant context; ACK direct messages only after receipt. Builder executes work; #490 owns collisions."
  else
    echo "[GAR] workspace_global unavailable at session start; do not treat that as an empty room."
  fi
else
  echo "[GAR] workspace_global unavailable at session start; Kitty room CLI not found."
fi

exit 0
