#!/bin/sh
# Block macOS Finder metadata (Icon\r files, .DS_Store) from being committed.
# Runs as a pre-commit framework local hook.

STAGED=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null)
if [ -z "$STAGED" ]; then
  exit 0
fi

JUNK=""
for f in $STAGED; do
  base=$(basename "$f")
  case "$base" in
    .DS_Store) JUNK="$JUNK $f" ;;
    ._'*')     JUNK="$JUNK $f" ;;
    Icon*)     JUNK="$JUNK $f" ;;
  esac
done

if [ -n "$JUNK" ]; then
  echo ""
  echo "macOS Finder metadata in staged files:"
  for j in $JUNK; do echo "  $j"; done
  echo ""
  echo "These are ignored by .gitignore but snuck in (force-add or"
  echo "the working tree got Finder'd). To recover:"
  echo "  git reset HEAD -- <files>"
  echo "Then run:  find . -name 'Icon*' -not -path '*/.git/*' -not -path '*/node_modules/*' -delete"
  echo ""
  exit 1
fi
