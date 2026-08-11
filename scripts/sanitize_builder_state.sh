#!/usr/bin/env bash
# Sanitize Builder-generated .claude/STATE.md and .claude/HANDOFF.md
# so they pass CI schema validation. Run from the worktree root.
set -euo pipefail

ACTUAL_HEAD=$(git rev-parse HEAD)
ACTUAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)

file_changed_by_worker() {
  local file="$1"
  if ! git diff --quiet -- "$file"; then
    return 0
  fi
  if ! git diff --cached --quiet -- "$file"; then
    return 0
  fi
  if git ls-files --others --exclude-standard -- "$file" | grep -q .; then
    return 0
  fi
  return 1
}

for f in .claude/STATE.md .claude/HANDOFF.md; do
  [ -f "$f" ] || continue
  file_changed_by_worker "$f" || continue

  python3 - "$f" "$ACTUAL_HEAD" "$ACTUAL_BRANCH" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
head_sha = sys.argv[2]
branch = sys.argv[3]
text = path.read_text(encoding="utf-8")

text = re.sub(r'"status"\s*:\s*"clean"', '"status": "complete"', text)
if re.search(r'"status"\s*:\s*"complete"', text):
    text = re.sub(
        r'("next_action"\s*:\s*")[^"]*(")',
        lambda match: f'{match.group(1)}None{match.group(2)}',
        text,
    )
text = re.sub(
    r'("head_sha"\s*:\s*")[^"]*(")',
    lambda match: f'{match.group(1)}{head_sha}{match.group(2)}',
    text,
)
text = re.sub(
    r'("branch"\s*:\s*")[^"]*(")',
    lambda match: f'{match.group(1)}{branch}{match.group(2)}',
    text,
)
if path.name == "HANDOFF.md":
    text = re.sub(r'"status"\s*:\s*"complete"', '"status": "valid"', text)

path.write_text(text, encoding="utf-8")
PY
done

echo "STATE/HANDOFF sanitized"
