#!/usr/bin/env bash
# Session-end field survey — read-only inventory of every piece of work that
# could collide with what this session is about to recommend.
#
# One section per source. A source that cannot be reached prints UNAVAILABLE
# with the reason; it never prints an empty section as if it were a clean
# result. Absence of evidence is reported as absence of evidence.
#
# Read-only by construction: no command here writes, fetches, or mutates.

# Deliberately no -e: a single failed probe must not abort the survey.
set -uo pipefail

BASE="${1:-origin/main}"
MAX_BRANCHES=8

hr() { printf '\n== %s ==\n' "$1"; }

hr "THIS WORKTREE"
printf 'root:   %s\n' "$(git rev-parse --show-toplevel 2>&1)"
printf 'common: %s\n' "$(git rev-parse --git-common-dir 2>&1)"
printf 'branch: %s\n' "$(git branch --show-current 2>&1)"
printf 'head:   %s\n' "$(git log --oneline -1 2>&1)"
DIRTY=$(git status --short 2>&1)
if [[ -z "${DIRTY// /}" ]]; then
  echo 'dirty:  clean'
else
  printf 'dirty:\n%s\n' "$DIRTY"
fi

hr "WORKTREES"
if ! WORKTREES=$(git worktree list --porcelain 2>&1); then
  echo "UNAVAILABLE: git worktree list failed: $WORKTREES"
else
  # A registration line alone hides the uncommitted edits a recommendation
  # could collide with, so probe each worktree's status too. Read-only.
  # Strip the literal prefix rather than splitting on whitespace: a worktree
  # path containing a space would otherwise probe a directory that does not
  # exist and report a healthy worktree as unavailable.
  printf '%s\n' "$WORKTREES" | while IFS= read -r line; do
    [[ "$line" != worktree\ * ]] && continue
    wt="${line#worktree }"
    [[ -z "$wt" ]] && continue
    branch=$(git -C "$wt" branch --show-current 2>&1)
    printf '%s  [%s]\n' "$wt" "$branch"
    if ! st=$(git -C "$wt" status --short 2>&1); then
      printf '  UNAVAILABLE: status failed: %s\n' "$st"
    elif [[ -z "${st// /}" ]]; then
      echo '  clean'
    else
      printf '%s\n' "$st" | sed 's/^/  /'
    fi
  done
fi

hr "UNMERGED BRANCHES vs $BASE"
if ! git rev-parse --verify --quiet "$BASE" >/dev/null; then
  echo "UNAVAILABLE: $BASE does not exist locally — run 'git fetch origin' first."
  BRANCHES=""
else
  ALL_BRANCHES=$(git branch -a --no-merged "$BASE" --format='%(refname:short)' 2>/dev/null \
    | grep -v '^origin/HEAD')
  TOTAL_BRANCHES=$(printf '%s\n' "$ALL_BRANCHES" | grep -c . || true)
  BRANCHES=$(printf '%s\n' "$ALL_BRANCHES" | head -n "$MAX_BRANCHES")
  if [[ -z "${BRANCHES// /}" ]]; then
    echo "none — every branch is merged into $BASE"
  else
    shown=0
    while IFS= read -r b; do
      [[ -z "$b" ]] && continue
      all_dirs=$(git diff --name-only "$BASE...$b" 2>/dev/null | cut -d/ -f1 | sort -u)
      # A branch with no diff against the base carries no work to collide with.
      [[ -z "${all_dirs// /}" ]] && continue
      # Every touched path is listed: a collision hidden behind a cap is exactly
      # the failure this inventory exists to prevent.
      dirs=$(printf '%s\n' "$all_dirs" | paste -sd, -)
      meta=$(git log -1 --format='%cr by %an' "$b" 2>&1)
      printf '%s  [%s]  touches: %s\n' "$b" "$meta" "$dirs"
      shown=$((shown + 1))
    done <<< "$BRANCHES"
    [[ "$shown" -eq 0 ]] && echo "none carrying work — unmerged refs exist but none differ from $BASE"
    # Silent truncation would let a colliding branch vanish from the survey.
    if [[ "$TOTAL_BRANCHES" -gt "$MAX_BRANCHES" ]]; then
      echo "TRUNCATED: $TOTAL_BRANCHES unmerged refs, only the first $MAX_BRANCHES inspected."
      echo "           Raise MAX_BRANCHES and re-run before trusting this section."
    fi
  fi
fi

hr "OPEN PULL REQUESTS (drafts included)"
if ! command -v gh >/dev/null 2>&1; then
  echo "UNAVAILABLE: gh not installed — check open PRs another way before claiming the queue is empty."
# A stale ambient GITHUB_TOKEN overrides keyring auth and makes a working
# setup look unauthenticated, so probe and query without it (AGENTS.md).
elif ! env -u GITHUB_TOKEN gh auth status >/dev/null 2>&1; then
  echo "UNAVAILABLE: gh not authenticated even with GITHUB_TOKEN unset."
else
  env -u GITHUB_TOKEN gh pr list --state open --limit 20 \
    --json number,title,isDraft,headRefName,updatedAt,author \
    --template '{{range .}}#{{.number}} {{if .isDraft}}[DRAFT] {{end}}{{.title}} ({{.headRefName}}, {{.author.login}}, {{.updatedAt}}){{"\n"}}{{end}}' 2>&1 \
    || echo "UNAVAILABLE: gh pr list failed — see error above."
fi

hr "BUILDER QUEUE"
# NOT `./kitty builder queue status`: that path calls init_db(), which creates
# the directory and schema and runs migrations. A survey must never mutate
# Builder's authoritative store, and an absent database is unknown state rather
# than an empty queue. builder_status is the supported read-only projection —
# the same one gateway/context_receipt.py uses.
BUILDER_DB="data/kittybuilder/builder_queue.db"
if [[ ! -f "$BUILDER_DB" ]]; then
  echo "UNAVAILABLE: $BUILDER_DB does not exist — Builder state is unknown, not empty."
else
  python3 -c '
import json, sys
from pathlib import Path
from gateway import builder_status
summary = builder_status.build_control_plane_summary(db_path=Path(sys.argv[1]))
# Aggregate counts cannot say WHICH Builder work is in flight, which is what a
# recommendation might duplicate. Initiatives carry that identity.
print(json.dumps({
    "queue": summary.get("queue"),
    "initiatives": summary.get("initiatives"),
}, indent=2, default=str))
' "$BUILDER_DB" 2>&1 || echo "UNAVAILABLE: read-only Builder projection failed — see error above."
fi

hr "CROSS-TOOL CLAIMS (~/kb/NOW.md)"
if [[ -f "$HOME/kb/NOW.md" ]]; then
  # The skill bounds NOW.md at ~50 lines, and the active-project and
  # parallel-work claims live at the top. Tailing it would drop exactly those.
  cat "$HOME/kb/NOW.md"
else
  echo "UNAVAILABLE: $HOME/kb/NOW.md not found — the KB is a separate repo and is not present here."
fi

hr "CARRIED RECOMMENDATIONS (previous .claude/STATE.md)"
if [[ -f .claude/STATE.md ]]; then
  python3 - <<'PY' 2>&1 || echo "UNAVAILABLE: could not parse the kitty-state block."
import json, pathlib, re, sys
text = pathlib.Path(".claude/STATE.md").read_text()
m = re.search(r"<!--\s*kitty-state\s*(\{.*?\})\s*-->", text, re.S)
if not m:
    print("UNAVAILABLE: no kitty-state JSON block in .claude/STATE.md")
    sys.exit(0)
state = json.loads(m.group(1))
recs = state.get("recommendations") or []
if not recs:
    print("none carried (previous STATE.md predates the recommendations field, or had none)")
for r in recs:
    print(f"- [{r.get('status','?')}] {r.get('id','<no-id>')} "
          f"(deferred x{r.get('deferred_count', 0)}, since {r.get('first_deferred','?')})")
    print(f"    what:    {r.get('what','')}")
    print(f"    blocked: {r.get('blocked_by','-')}")
    print(f"    check:   {r.get('release_check','-')}")
PY
else
  echo "UNAVAILABLE: .claude/STATE.md is missing — carried recommendations could not be recovered."
fi

printf '\n== END SURVEY ==\n'
