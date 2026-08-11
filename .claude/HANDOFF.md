# Handoff — Kitty/KittyBuilder boundary refactor

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-11T01:05:00Z",
  "branch": "feat/agent-council-relay",
  "worktree": "/Users/jacobbrizinski/Projects/kitty",
  "status": "implemented_awaiting_verification",
  "execution_owner": "interactive",
  "active_mission": "docs/ACTIVE_MISSION.md",
  "completed_items": [
    "Submitted approved Missions through the durable Builder initiative path",
    "Persisted and enforced Mission model/provider routing policy",
    "Retired the unmounted /builder/action adapter, tests, executors, and tier entries",
    "Added architecture-fitness coverage and committed e42657c7"
  ],
  "blockers": [
    "Independent verification is still required",
    "One unrelated killed-worker recovery test remains failing",
    "Builder read-only projection is unavailable under local Python 3.9"
  ],
  "invalidation_conditions": [
    "A future session changes commit e42657c7",
    "The parallel agent-council changes in 56c2064e are claimed by this assignment"
  ],
  "next_action": "Independently review e42657c7, then decide whether to open a PR",
  "parallel_work": [
    {"kind":"parallel_commit","ref":"agent-council changes included in 56c2064e","owner":"prior interactive session; not independently reviewed here","touches":["scripts/agent_council.py","tests/test_agent_council.py"],"observed_at":"2026-08-11T01:07:00Z"}
  ],
  "recommendations": [],
  "pull_request": null,
  "head_sha": "e42657c7",
  "kb_receipt": null
}
-->

## Outcome

Committed `e42657c7` (`refactor: consolidate Kitty Builder control boundary`).
Tracked upstream is `origin/feat/agent-council-relay` at `afaa8c99`; local branch is ahead 1.
The local branch currently reports its tracked origin branch as `[gone]`.
The commit contains the Mission-to-Builder submission/routing seam and retires
the unmounted `/builder/action` compatibility surface. The follow-up handoff
commit `56c2064e` also contains parallel agent-council changes that this
session did not independently review.

## Verification

- `venv/bin/python -m pytest -q tests/test_action_queue.py tests/test_builder_routes.py tests/test_builder_commands.py tests/test_architecture_fitness.py tests/test_tool_server.py` — 72 passed.
- `venv/bin/python -m pytest -q tests/test_builder_initiative.py tests/test_builder_run.py` — 167 passed.
- `npm test -- --run tests/BuilderSurface.test.tsx` — 20 passed.
- Ruff — passed; mypy — 6 source files, no issues; compileall and diff check — passed.
- Broader Builder/provider run — 1,118 passed; one unrelated killed-worker recovery test remains failing.

## Boundaries

- The worktree is clean, but `scripts/agent_council.py` and
  `tests/test_agent_council.py` in `56c2064e` belong to parallel prior work and
  were not independently reviewed in this session.
- Builder projection was unavailable under Python 3.9; treat it as unavailable,
  not empty.
- The isolated publish test passed after restoring transient `.git/config`
  `core.bare=false` metadata.

## Next action

Next action: independently review commit `e42657c7`. Keep the killed-worker
recovery failure separate from this retired-route slice.

## Session records

- Execution owner: `interactive`.
- KB effectiveness receipt: to be recorded for this session.
- Correction: `~/kb/corrections/2026-08-10-shared-worktree-core-bare.md`.
- Workflow signal: `shared-worktree-core-bare` (observed, not promoted).
