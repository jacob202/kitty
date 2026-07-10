#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/Projects/kitty"
BASE="0f05ae0"
STAMP="$(date +%Y%m%d-%H%M%S)"
BRANCH="feat/kittybuilder-free-campaign-$STAMP"
WORKTREE="$HOME/orca/workspaces/kitty/$BRANCH"
TASKDIR="/tmp/kittybuilder-free-campaign-$STAMP"
LOG="/tmp/kittybuilder-free-campaign-$STAMP.log"

mkdir -p "$TASKDIR"
git -C "$REPO" worktree add -b "$BRANCH" "$WORKTREE" "$BASE"
cd "$WORKTREE"
bash scripts/orca_worktree_setup.sh

cat >"$TASKDIR/01-kb-s1b.md" <<'CARD'
# KB-S1B

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement dependency eligibility, deterministic next-packet selection, initiative status projection, CLI support, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/02-kb-s2a.md" <<'CARD'
# KB-S2A

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement bounded immutable context bundles for packet attempts, dependency summaries, prior results, decisions, base SHA, artifact paths, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/03-kb-s2b.md" <<'CARD'
# KB-S2B

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement strict machine-readable implementation and review result contracts, malformed-result handling, persistence or artifacts, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/04-kb-s3a.md" <<'CARD'
# KB-S3A

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement deterministic validation commands with durable SHA-bound evidence, bounded output, status reporting, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/05-kb-s3b.md" <<'CARD'
# KB-S3B

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement an independent read-only review stage with structured findings, reviewed-SHA freshness checks, approval gates, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/06-kb-s4.md" <<'CARD'
# KB-S4

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement bounded review-driven repair attempts, no-progress detection, retry limits, repeated validation and review, escalation, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/07-kb-s5a.md" <<'CARD'
# KB-S5A

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement safe branch push and idempotent pull-request create-or-update support with safeguards and tests. Do not auto-merge.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/08-kb-s5b.md" <<'CARD'
# KB-S5B

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement CI status and merge reconciliation for the current head SHA, stale-result rejection, failure capture, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/09-kb-s6a.md" <<'CARD'
# KB-S6A

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement the deterministic orchestration tick and continuation loop across implementation, validation, review, repair, PR, CI, merge waiting, and packet advancement.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

cat >"$TASKDIR/10-kb-s6b.md" <<'CARD'
# KB-S6B

Work directly in the current Kitty worktree.

Do not ask for a hero document, master specification, approval document, or more instructions. Treat the repository, tests, `.claude/STATE.md`, and `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` as authoritative.

Goal: Implement durable decisions, budgets, attempt limits, pause/resume, restart reconciliation, circuit breakers, operator status, and tests.

Requirements:

- inspect only relevant files;
- preserve the existing queue lifecycle, fencing, recovery, runner, briefs, operator controls, shadow runner, and completed initiative behavior;
- make the smallest correct implementation;
- add focused tests;
- run focused tests and the complete Builder regression suite;
- run ruff and `git diff --check`;
- fix verified defects;
- create one focused commit;
- update `.claude/STATE.md`;
- leave a clean worktree;
- do not push, merge, open a PR, use paid providers, spawn extra subagents, or write another large architecture document.

Stop only for a genuine unsafe ambiguity or technical blocker.
CARD

nohup caffeinate -i bash -c '
set -euo pipefail
cd "$1"
taskdir="$2"

for task in "$taskdir"/*.md; do
    echo
    echo "===== STARTING $(basename "$task") ====="
    bash scripts/opencode_free_train.sh "$task"

    if [[ -n "$(git status --porcelain=v1 --untracked-files=all)" ]]; then
        echo "ERROR: dirty worktree after $(basename "$task")"
        git status --short --branch
        exit 21
    fi

    echo "===== COMPLETED $(basename "$task") ====="
    git log -1 --oneline
done

echo "===== CAMPAIGN COMPLETE ====="
git log --oneline --decorate -12
' bash "$WORKTREE" "$TASKDIR" >"$LOG" 2>&1 </dev/null &

echo
echo "Free KittyBuilder campaign launched."
echo "PID: $!"
echo "Branch: $BRANCH"
echo "Worktree: $WORKTREE"
echo "Log: $LOG"
echo
echo "Check progress with:"
echo "tail -f \"$LOG\""
