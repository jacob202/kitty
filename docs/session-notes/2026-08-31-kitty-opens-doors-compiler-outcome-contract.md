# Outcome Contract — Kitty opens the doors compiler

## Identity
- Task: compile and queue the safe backend subset of the "Kitty is sophisticated" slate
- Execution owner: interactive compiler; packet execution owner: Builder
- Branch/worktree: `docs/kitty-opens-doors-compiler-20260831` / `/private/tmp/kitty-opens-doors-compiler-20260831`
- Base SHA: `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
- Repair-cycle limit: 2

## User-visible outcome
Builder has a non-empty safe queue of backend packets that open existing Kitty capabilities without colliding with active PR owners.

## Acceptance criteria
| ID | Observable criterion | Verification | Evidence |
|---|---|---|---|
| AC-1 | Compiler emits an exact-schema manifest and companion docs from one structured source | `python scratchpad/assemble.py` | generated files + exit 0 |
| AC-2 | New manifest has no preflight errors and Builder accepts it | packet preflight + `initiative validate --json` | 0 errors + `valid:true` |
| AC-3 | Only non-colliding packets are applied to live Builder | issue #490/open-PR path check + Builder status | v2 packet IDs queued/running |
| AC-4 | Existing v1 run is not disturbed | `initiative status kitty-opens-the-doors-20260831-v1 --json` | same task/attempt continues |

## Non-goals
- Do not queue `KF-SCHEDULE-01` while PR #725 or #735 owns `gateway/app.py`.
- Do not feed frontend-only packets to Builder.
- Do not push, merge, spend, or touch secrets/data from packet workers.

## Prohibited shortcuts
- Do not mutate the already-applied v1 manifest; use v2.
- Do not invent cross-manifest dependencies.
- Do not claim a packet shipped a visible UI outcome without its interactive companion.

## Final state
`implemented, awaiting verification`
