#!/usr/bin/env bash
# Install the canonical pre-commit hook for this repo.
#
# Copies scripts/pre-commit.template to .git/hooks/pre-commit and makes it
# executable. Re-run after editing the template to pick up changes.
#
# Usage:  scripts/install-pre-commit.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO_ROOT/scripts/pre-commit.template"
TARGET="$REPO_ROOT/.git/hooks/pre-commit"

if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: template not found at $TEMPLATE" >&2
    exit 1
fi

cp "$TEMPLATE" "$TARGET"
chmod +x "$TARGET"
echo "Installed pre-commit hook to $TARGET"
