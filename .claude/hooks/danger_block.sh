#!/bin/bash
# DangerBlock hook — prevents destructive git operations that broke past sessions
# Runs before: git rm, git reset, git checkout, git clean, git commit
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

# Trap to detect which command is being run (passed as argument)
COMMAND="${1:-unknown}"
ARGS="${2:-}"

case "${COMMAND}" in
  git-rm)
    # Prevent rm of data/ or critical dirs
    if echo "${ARGS}" | grep -qE '(data/|\.env|\.webui_secret)'; then
      echo "❌ BLOCKED: git rm on critical directory. Use 'git rm --cached' or review manually." >&2
      exit 1
    fi
    ;;
  git-commit)
    # Check for secrets and binaries in staged files
    if git diff --cached --name-only | grep -qE '(\.env|\.webui_secret|\.db$|\.sqlite3$|chroma\.sqlite3)'; then
      echo "❌ BLOCKED: Attempting to commit secrets or binary databases." >&2
      echo "   Staged files containing .env, .webui_secret, .db, .sqlite3, or chroma.sqlite3:" >&2
      git diff --cached --name-only | grep -E '(\.env|\.webui_secret|\.db$|\.sqlite3$|chroma\.sqlite3)' >&2
      exit 1
    fi
    ;;
  git-reset-hard)
    # Prevent reset --hard on uncommitted work
    if [[ -n "$(git status --porcelain)" ]]; then
      echo "❌ BLOCKED: reset --hard with uncommitted changes. Stash first if intentional." >&2
      exit 1
    fi
    ;;
  *)
    # Unknown command, allow
    exit 0
    ;;
esac

exit 0
