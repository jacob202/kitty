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
git worktree list 2>&1 || echo "UNAVAILABLE: git worktree list failed"

hr "UNMERGED BRANCHES vs $BASE"
if ! git rev-parse --verify --quiet "$BASE" >/dev/null; then
  echo "UNAVAILABLE: $BASE does not exist locally — run 'git fetch origin' first."
  BRANCHES=""
else
  BRANCHES=$(git branch -a --no-merged "$BASE" --format='%(refname:short)' 2>/dev/null \
    | grep -v '^origin/HEAD' | head -n "$MAX_BRANCHES")
  if [[ -z "${BRANCHES// /}" ]]; then
    echo "none — every branch is merged into $BASE"
  else
    shown=0
    while IFS= read -r b; do
      [[ -z "$b" ]] && continue
      dirs=$(git diff --name-only "$BASE...$b" 2>/dev/null | cut -d/ -f1 | sort -u | head -6 | paste -sd, -)
      # A branch with no diff against the base carries no work to collide with.
      [[ -z "${dirs// /}" ]] && continue
      meta=$(git log -1 --format='%cr by %an' "$b" 2>&1)
      printf '%s  [%s]  touches: %s\n' "$b" "$meta" "$dirs"
      shown=$((shown + 1))
    done <<< "$BRANCHES"
    [[ "$shown" -eq 0 ]] && echo "none carrying work — unmerged refs exist but none differ from $BASE"
  fi
fi

hr "OPEN PULL REQUESTS (drafts included)"
if ! command -v gh >/dev/null 2>&1; then
  echo "UNAVAILABLE: gh not installed — check open PRs another way before claiming the queue is empty."
elif ! gh auth status >/dev/null 2>&1; then
  echo "UNAVAILABLE: gh not authenticated (check for a stale GITHUB_TOKEN)."
else
  gh pr list --state open --limit 20 \
    --json number,title,isDraft,headRefName,updatedAt,author \
    --template '{{range .}}#{{.number}} {{if .isDraft}}[DRAFT] {{end}}{{.title}} ({{.headRefName}}, {{.author.login}}, {{.updatedAt}}){{"\n"}}{{end}}' 2>&1 \
    || echo "UNAVAILABLE: gh pr list failed — see error above."
fi

hr "BUILDER QUEUE"
if [[ ! -x ./kitty ]]; then
  echo "UNAVAILABLE: ./kitty not executable from $(pwd)"
else
  ./kitty builder queue status --json 2>&1 | head -40 \
    || echo "UNAVAILABLE: builder queue status failed — see error above."
fi

hr "CROSS-TOOL CLAIMS (~/kb/NOW.md)"
if [[ -f "$HOME/kb/NOW.md" ]]; then
  tail -n 30 "$HOME/kb/NOW.md"
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
  echo "no previous .claude/STATE.md"
fi

printf '\n== END SURVEY ==\n'
