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
# Anchored, not relative: invoked from a subdirectory, a relative .claude path
# resolves against that subdirectory and the checkpoint reads as missing — so
# the carried recommendations vanish and get overwritten on the next write.
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
# Overridable: the truncation warning below is only actionable if raising
# this does not require editing a tracked script.
MAX_BRANCHES="${MAX_BRANCHES:-8}"

hr() { printf '\n== %s ==\n' "$1"; }

hr "THIS WORKTREE"
printf 'root:   %s\n' "$(git rev-parse --show-toplevel 2>&1)"
printf 'common: %s\n' "$(git rev-parse --git-common-dir 2>&1)"
printf 'branch: %s\n' "$(git branch --show-current 2>&1)"
printf 'head:   %s\n' "$(git log --oneline -1 2>&1)"
# Capture the status before classifying the output: a failed probe printed
# under "dirty:" reads as a change listing, and an empty failure reads as clean.
if ! DIRTY=$(git status --short 2>&1); then
  printf 'dirty:  UNAVAILABLE: git status failed: %s\n' "$DIRTY"
elif [[ -z "${DIRTY// /}" ]]; then
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
  # An enumeration failure must not read as "everything is merged".
  if ! RAW_BRANCHES=$(git branch -a --no-merged "$BASE" --format='%(refname:short)' 2>&1); then
    # Do NOT fall through: the clean-result path below would then also print
    # "every branch is merged", contradicting the failure just reported.
    echo "UNAVAILABLE: cannot enumerate branches against $BASE: $RAW_BRANCHES"
    RAW_BRANCHES=""
    ENUMERATION_FAILED=1
  fi
  ALL_BRANCHES=$(printf '%s\n' "$RAW_BRANCHES" | grep -v '^origin/HEAD' || true)
  TOTAL_BRANCHES=$(printf '%s\n' "$ALL_BRANCHES" | grep -c . || true)
  BRANCHES=$(printf '%s\n' "$ALL_BRANCHES" | head -n "$MAX_BRANCHES")
  if [[ "${ENUMERATION_FAILED:-0}" == "1" ]]; then
    :  # already reported UNAVAILABLE above; no clean result to claim
  elif [[ -z "${BRANCHES// /}" ]]; then
    echo "none — every branch is merged into $BASE"
  else
    shown=0
    while IFS= read -r b; do
      [[ -z "$b" ]] && continue
      # A failed diff (shallow clone, missing object, no merge base) must not
      # be read as "this branch touches nothing" — that hides a live collision.
      if ! raw_diff=$(git diff --name-only "$BASE...$b" 2>&1); then
        printf '%s  UNAVAILABLE: cannot diff against %s: %s\n' "$b" "$BASE" "$raw_diff"
        shown=$((shown + 1))
        continue
      fi
      all_dirs=$(printf '%s\n' "$raw_diff" | cut -d/ -f1 | sort -u)
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
      echo "           Re-run with MAX_BRANCHES=$TOTAL_BRANCHES to inspect them all."
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
  PR_LIMIT=100
  if ! PRS=$(env -u GITHUB_TOKEN gh pr list --state open --limit "$PR_LIMIT" \
    --json number,title,isDraft,headRefName,updatedAt,author \
    --template '{{range .}}#{{.number}} {{if .isDraft}}[DRAFT] {{end}}{{.title}} ({{.headRefName}}, {{.author.login}}, {{.updatedAt}}){{"\n"}}{{end}}' 2>&1); then
    echo "UNAVAILABLE: gh pr list failed: $PRS"
  else
    printf '%s\n' "$PRS"
    # A PR whose head is not a local remote-tracking branch has no entry in the
    # branch section above, so without this its collision scope is unknown.
    while IFS= read -r pr_line; do
      [[ "$pr_line" != \#* ]] && continue
      pr_num="${pr_line%% *}"; pr_num="${pr_num#\#}"
      if pr_files=$(env -u GITHUB_TOKEN gh pr view "$pr_num" --json files \
        --jq '[.files[].path] | map(split("/")[0]) | unique | join(",")' 2>&1); then
        printf '     #%s touches: %s\n' "$pr_num" "${pr_files:-<none>}"
      else
        printf '     #%s touches: UNAVAILABLE: %s\n' "$pr_num" "$pr_files"
      fi
    done <<< "$PRS"
    # --limit is a maximum fetched, not a page size: hitting it means the
    # inventory may be short a colliding PR and cannot be called complete.
    if [[ "$(printf '%s\n' "$PRS" | grep -c '^#')" -ge "$PR_LIMIT" ]]; then
      echo "TRUNCATED: hit the --limit of $PR_LIMIT open PRs; raise it before trusting this section."
    fi
  fi
fi

hr "BUILDER QUEUE"
# NOT `./kitty builder queue status`: that path calls init_db(), which creates
# the directory and schema and runs migrations. A survey must never mutate
# Builder's authoritative store, and an absent database is unknown state rather
# than an empty queue. builder_status is the supported read-only projection —
# the same one gateway/context_receipt.py uses.
# Builder's database lives in the canonical checkout's untracked data/ dir.
# `git worktree` does not populate that, so a relative path from an isolated
# Orca worktree would report Builder unavailable while the real queue has work.
CANONICAL_ROOT=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")
[[ -z "$CANONICAL_ROOT" || "$CANONICAL_ROOT" == "." ]] && CANONICAL_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
BUILDER_DB="$CANONICAL_ROOT/data/kittybuilder/builder_queue.db"
if [[ ! -f "$BUILDER_DB" ]]; then
  echo "UNAVAILABLE: $BUILDER_DB does not exist — Builder state is unknown, not empty."
else
  # PYTHONPATH, not cwd: invoked from a subdirectory, `from gateway import ...`
  # would fail and the authoritative queue would read as UNAVAILABLE.
  PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
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
if [[ -f "$REPO_ROOT/.claude/STATE.md" ]]; then
  REPO_ROOT="$REPO_ROOT" python3 - <<'PY' 2>&1 || echo "UNAVAILABLE: could not parse the kitty-state block."
import json, os, pathlib, re, sys
text = pathlib.Path(os.environ["REPO_ROOT"], ".claude/STATE.md").read_text()
m = re.search(r"<!--\s*kitty-state\s*(\{.*?\})\s*-->", text, re.S)
if not m:
    print("UNAVAILABLE: no kitty-state JSON block in .claude/STATE.md")
    sys.exit(0)
state = json.loads(m.group(1))
recs = state.get("recommendations")
if recs is None and state.get("schema_version", 1) >= 2:
    print("UNAVAILABLE: schema_version 2 checkpoint has no recommendations key; "
          "carry-forward state is corrupt, not empty")
    sys.exit(0)
if recs is not None and not isinstance(recs, list):
    print(f"UNAVAILABLE: recommendations is {type(recs).__name__}, not a list; "
          "carry-forward state is corrupt, not empty")
    sys.exit(0)
recs = recs or []
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
  echo "UNAVAILABLE: $REPO_ROOT/.claude/STATE.md is missing — carried recommendations could not be recovered."
fi

printf '\n== END SURVEY ==\n'
