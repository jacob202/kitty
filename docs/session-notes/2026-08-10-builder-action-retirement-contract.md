# Outcome contract: retire legacy Builder action surface

## Identity

- Task: Retire the dead `/builder/action` compatibility surface.
- Execution owner: `interactive`
- Branch/worktree: `feat/agent-council-relay` / `/Users/jacobbrizinski/Projects/kitty`
- Base SHA: `165862c2c8ab8e86e50f8271d3c3ebef78abdf4f`
- Repair-cycle limit: `2`

## User-visible outcome

Builder control has one production command boundary: `/builder/command`. The
legacy `/builder/action` adapter and its obsolete action-queue registrations no
longer create a second control path, while canonical command behavior remains
unchanged.

## Acceptance criteria

| ID | Observable criterion | Verification command or interaction | Required evidence |
|---|---|---|---|
| AC-1 | No production or source adapter implements `/builder/action`. | `rg -n "builder_control|@router.post\(\"/builder/action\"" gateway --glob '*.py'` | No legacy adapter/module or direct route implementation remains. |
| AC-2 | Builder-specific legacy action kinds are not registered in the generic action queue or signed tier file. | `rg -n "builder\\.(run_next|pause_initiative|resume_initiative|cancel_task|cleanup)" gateway/action_queue.py config/action_tiers.json` | No matches; generic action-queue tests still pass. |
| AC-3 | The canonical Builder command boundary and existing durable behavior remain valid. | `venv/bin/python -m pytest -q tests/test_action_queue.py tests/test_builder_routes.py tests/test_builder_commands.py tests/test_architecture_fitness.py` | Focused suite passes. |

## Non-goals

- Do not redesign Builder's state machine, routing, recovery, or evidence flow.
- Do not remove `packet_id` compatibility from the canonical command model.
- Do not edit historical documents, generated evidence, or unrelated UI/history work.

## Prohibited shortcuts

- Do not infer runtime success from code inspection alone.
- Do not treat the implementer's own review as independent acceptance.
- Do not silently weaken a criterion after implementation begins.
- Do not replace unavailable evidence with optimistic language.

## Context that must survive compaction or handoff

- Accepted requirements and decisions: canonical `/builder/command` is the only Builder control boundary; delete only dead legacy action artifacts.
- Current implementation state: production route already excludes `/builder/action`; legacy module, tests, queue executors, and tier entries remain.
- Changed paths and current SHA: prior user changes are present; mutation starts from `165862c2c8ab8e86e50f8271d3c3ebef78abdf4f` plus the existing dirty worktree.
- Known failures/blockers: context receipt reports unrelated stale checkpoint/PR metadata; Builder projection was not requested for this source-only slice.
- Exact next verification action: run the focused pytest, lint, mypy, compile, and diff checks after the deletion.

## Verifier report

| Criterion | Verdict (`PASS`, `FAIL`, `UNVERIFIED`) | Evidence | Required repair |
|---|---|---|---|
| AC-1 | PASS | `gateway/routes/builder_control.py` is absent; the production-source search returned no matches. | None. |
| AC-2 | PASS | The five retired kinds are absent from `gateway/action_queue.py` and `config/action_tiers.json`. | None. |
| AC-3 | UNVERIFIED | Focused boundary suite: 72 passed. Adjacent Mission/Builder tests: 167 passed. BuilderSurface UI test: 20 passed. Ruff, mypy, compileall, and diff check passed. The broader Builder/provider run recorded 1118 passes; its publish failure passed after restoring the checkout's transient `core.bare=false` metadata. | Independent review still required; one unrelated recovery test remains failing outside this slice. |

## Final state

Choose exactly one:

- `verified`
- `implemented, awaiting verification`
- `blocked`
- `failed`

Evidence-bound summary:

Final state: `implemented, awaiting verification`

Verification details: the focused suite emitted one existing Starlette/httpx
deprecation warning. The broader run initially also encountered a transient
checkout metadata failure because `.git/config` had `core.bare=true`; restoring
the worktree flag made
`TestMergeAndVerify.test_raises_when_no_pr_linked` pass in isolation. The
remaining unrelated failure is
`TestRecoveryExercise.test_killed_run_packet_recovers_end_to_end` (task remains
`running` after process reaping); neither path uses the retired action surface.
