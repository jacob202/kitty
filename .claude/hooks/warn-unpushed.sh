#!/usr/bin/env bash
# Stop — nudge when finished work is sitting only in the working tree or
# only on the local branch. Push is Jacob's call, not this hook's; it only
# makes sure work he'd expect to see on the remote doesn't quietly stay
# local. Never blocks — always exits 0.

set -uo pipefail

# Not a git repo, or git unavailable — nothing to check.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

DIRTY=""
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  DIRTY="uncommitted changes"
fi

# Empty on detached HEAD — treated as "no branch to check upstream for".
BRANCH=$(git branch --show-current 2>/dev/null || true)
UNPUSHED=""
if [[ -n "$BRANCH" ]]; then
  UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
  if [[ -z "$UPSTREAM" ]]; then
    UNPUSHED="branch '$BRANCH' has never been pushed"
  else
    AHEAD=$(git rev-list --count "${UPSTREAM}..HEAD" 2>/dev/null || echo 0)
    if [[ "$AHEAD" -gt 0 ]]; then
      UNPUSHED="$AHEAD commit(s) on '$BRANCH' not pushed to $UPSTREAM"
    fi
  fi
fi

[[ -z "$DIRTY" && -z "$UNPUSHED" ]] && exit 0

if [[ -n "$DIRTY" && -n "$UNPUSHED" ]]; then
  echo "[git] $DIRTY, and $UNPUSHED. Commit and push before you call this done."
elif [[ -n "$DIRTY" ]]; then
  echo "[git] $DIRTY. Commit before you call this done."
else
  echo "[git] $UNPUSHED. Push before you call this done."
fi
exit 0
