#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUT_DIR="artifacts/repo-context"
mkdir -p "$OUT_DIR"

if command -v repomix >/dev/null 2>&1; then
  REPOMIX=(repomix)
elif command -v npx >/dev/null 2>&1; then
  REPOMIX=(npx --yes repomix@latest)
else
  echo "Repomix is not installed and npx is unavailable." >&2
  echo "Install Node.js or Repomix, then rerun this script." >&2
  exit 1
fi

"${REPOMIX[@]}" --config repomix.config.json

# Produce a Markdown companion when the installed Repomix supports the flags.
if "${REPOMIX[@]}" \
  --config repomix.config.json \
  --style markdown \
  --output "$OUT_DIR/kitty-codebase.md"; then
  :
else
  rm -f "$OUT_DIR/kitty-codebase.md"
  echo "Markdown companion was not produced; the XML bundle is complete." >&2
fi

{
  echo "Kitty repository context bundle"
  echo "generated_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repo_root=$ROOT"
  echo "branch=$(git branch --show-current)"
  echo "head=$(git rev-parse HEAD)"
  echo "dirty_files=$(git status --porcelain | wc -l | tr -d ' ')"
  echo "config=repomix.config.json"
  echo "code_map=docs/CODEBASE_MAP.md"
} > "$OUT_DIR/manifest.txt"

printf '\nGenerated repository context:\n'
printf '  %s\n' "$OUT_DIR/kitty-codebase.xml"
[[ -f "$OUT_DIR/kitty-codebase.md" ]] && printf '  %s\n' "$OUT_DIR/kitty-codebase.md"
printf '  %s\n' "$OUT_DIR/manifest.txt"
printf '\nReview the bundle for sensitive content before uploading it.\n'
