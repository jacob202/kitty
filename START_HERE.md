# Kitty — Start Here

This is the canonical cold-start bootloader. It routes to authorities and
live evidence; it does not duplicate current state.

## Boot sequence

1. Confirm `pwd -P`, `git rev-parse --show-toplevel`, and
   `git worktree list --porcelain`. The worktree must share Git state with
   `~/Projects/kitty`; Desktop copies are invalid.
2. Inspect `git status --short --branch`, branch, HEAD, `origin/main`, and
   recent commits. Do not stash, clean, switch, or overwrite unrelated work to
   simplify the checkout.
3. Read only the authority and code required by the task. For code changes, use
   the canonical order below as needed; live Git/GitHub/runtime state outranks
   stale handoff prose.
4. Before mutation, inspect current worktrees and local claims:
   `python3 scripts/work_claim.py status`.
5. Acquire one explicit claim covering the paths you intend to change:
   `python3 scripts/work_claim.py claim --owner <id> --task <task> --path <scope>`.
   Overlapping active scopes are blocked; non-overlapping work remains allowed.
6. Do not use Builder or GAR during ordinary startup. Inspect either only for an
   explicit Builder/GAR task, rollback, or historical evidence request.
7. Immediately before mutation, re-check branch, HEAD, dirty paths, scope,
   authorization, and the exact files to change.

## Task routing

- Informational: load only the directly relevant authority and live evidence.
- Planning: use current conversation plus verified repository/runtime state;
  do not require GAR or legacy checkpoints.
- Code change: claim the intended paths, load the narrow code/test surface, and
  run focused verification after each coherent change.
- Builder work: only an explicit Builder request may inspect or run preserved
  Builder machinery. Bare `next` never selects or runs a Builder packet.
- Completion: verify the requested outcome, release the local claim when safe,
  report exact evidence, and stop. No mandatory session-end workflow follows.

## Canonical reading order

<!-- kitty-reading-order:start -->
1. [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md) — concern router
2. [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) — highest design authority
3. [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) — product purpose
4. [`AGENTS.md`](AGENTS.md) — engineering doctrine
5. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current system shape
6. [`docs/DECISIONS.md`](docs/DECISIONS.md) — accepted decisions
7. [`docs/ROADMAP.md`](docs/ROADMAP.md) — active delivery order
8. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — dated shipped evidence
9. [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) — one approved mission
<!-- kitty-reading-order:end -->

GAR is preserved historical/optional evidence, not a mandatory startup or
handoff surface. `.claude/STATE.md` and `.claude/HANDOFF.md` are compatibility
snapshots only and must not establish current assignment, ownership, branch, or
next action.

`docs/reference/MULTI_AGENT_COORDINATION.md` is historical/operational reference.
The active collision boundary for ordinary work is the shared Git worktree claim
state plus live Git/GitHub evidence.

`docs/reference/CONTEXT_ENGINEERING.md` provides staged-loading detail by task
type (what to load for informational, planning, and code-change work). This
file owns the cold-start receipt and the canonical reading order only; it does
not duplicate the staged-load procedure.

## Minimal command set

```bash
git status --short --branch
git worktree list --porcelain
python3 scripts/work_claim.py status
python3 scripts/work_claim.py claim --owner <id> --task <task> --path <scope>
```

Use focused tests for focused changes; reserve full quality gates for an
explicit `/qg`, CI, or user request. Builder/GAR commands are compatibility
tools and are not part of normal startup.

Push, merge, deletion, history rewrite, credentials, auth/env changes, paid
execution, and heavy dependencies remain approval-gated.
