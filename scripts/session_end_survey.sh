#!/usr/bin/env bash
set -euo pipefail

# session_end_survey.sh — inventory other in-flight work before session-end
# Reports: worktrees, unmerged branches, open PRs+drafts, Builder queue, ~/kb/NOW
# Every section prints a header + data or "UNAVAILABLE". Never silent.

SELF="$0"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== session_end_survey.sh  $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "Repo: $REPO_ROOT"
echo ""

# --- 1. Worktrees ---
echo "--- Worktrees ---"
if git -C "$REPO_ROOT" rev-parse --show-toplevel &>/dev/null; then
  git -C "$REPO_ROOT" worktree list --porcelain 2>&1
else
  echo "UNAVAILABLE"
fi
echo ""

# --- 2. Unmerged branches (not on origin/main) ---
echo "--- Unmerged branches (not on origin/main) ---"
git -C "$REPO_ROOT" branch --no-merged origin/main 2>&1 || echo "UNAVAILABLE"
echo ""

# --- 3. Open PRs + drafts ---
echo "--- Open PRs (including drafts) ---"
if command -v gh &>/dev/null; then
  gh pr list --state open --json number,title,headRefName,state,isDraft 2>&1 || echo "UNAVAILABLE"
else
  echo "UNAVAILABLE (gh not installed)"
fi
echo ""

# --- 4. Builder queue snapshot ---
echo "--- Builder queue ---"
BUILDER_DB="$REPO_ROOT/data/kittybuilder/builder_queue.db"
if [ -f "$BUILDER_DB" ]; then
  echo "DB exists: $BUILDER_DB"
  if command -v python3.12 &>/dev/null; then
    python3.12 -c "
import json, sys
sys.path.insert(0, '$REPO_ROOT/gateway')
try:
    from kittybuilder.control_plane import build_control_plane_summary
    summary = build_control_plane_summary()
    # Print only the queue counts and active initiative names
    q = summary.get('queue', {})
    print('Queue:', json.dumps({k: v for k, v in q.items() if k != 'total'}, indent=2))
    for init in summary.get('initiatives', []):
        if init.get('state') in ('active', 'running', 'failed'):
            print(f'  {init[\"state\"]:8s} {init[\"initiative_id\"]}  ({init.get(\"title\",\"\")})')
except Exception as e:
    print(f'UNAVAILABLE: {e}')
" 2>&1 || echo "UNAVAILABLE (import failed)"
  else
    echo "UNAVAILABLE (python3.12 not found)"
  fi
else
  echo "UNAVAILABLE (DB not found at $BUILDER_DB)"
fi
echo ""

# --- 5. ~/kb/NOW.md ---
echo "--- ~/kb/NOW.md ---"
if [ -f "$HOME/kb/NOW.md" ]; then
  head -30 "$HOME/kb/NOW.md"
else
  echo "UNAVAILABLE ($HOME/kb/NOW.md not found)"
fi
echo ""

# --- 6. Active worktrees with uncommitted changes ---
echo "--- Dirty worktrees ---"
git -C "$REPO_ROOT" worktree list --porcelain | while IFS= read -r line; do
  case "$line" in
    worktree\ *)
      wt="${line#worktree }"
      ;;
    HEAD\ *)
      ;;
    branch\ *)
      br="${line#branch }"
      if [ -d "$wt" ]; then
        dirty="$(git -C "$wt" status --short --porcelain 2>/dev/null || echo 'UNAVAILABLE')"
        if [ -n "$dirty" ] && [ "$dirty" != "UNAVAILABLE" ]; then
          echo "$wt ($br):"
          echo "$dirty" | sed 's/^/  /'
        fi
      fi
      ;;
  esac
done
echo ""

echo "=== end survey ==="