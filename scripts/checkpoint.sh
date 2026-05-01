#!/bin/bash
# Checkpoint work-in-progress.
# Usage: ./scripts/checkpoint.sh "message"
# Stages all tracked changes, commits with timestamp + message.
# Use during long autonomous runs to preserve state across usage limits.

set -e

cd "$(dirname "$0")/.."

MSG="${1:-checkpoint}"
TS=$(date +%Y-%m-%dT%H%M)

# Only stage tracked files (no -A to avoid sensitive untracked files)
git add -u

if git diff --cached --quiet; then
  echo "→ No changes to checkpoint."
  exit 0
fi

git diff --cached --stat
echo ""
read -p "Commit these changes as 'checkpoint $TS: $MSG'? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "→ Aborted."
  git reset
  exit 0
fi

git commit -m "checkpoint $TS: $MSG"
echo "✓ Checkpoint committed."
