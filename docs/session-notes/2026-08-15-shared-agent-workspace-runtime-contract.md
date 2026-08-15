# Outcome contract: shared agent workspace runtime

## Identity

- Task: turn the existing shared-agent-room prototype into a small, usable, model-backed room.
- Execution owner: `interactive`
- Branch/worktree: `feat/shared-agent-workspace-v1` at `.claude/worktrees/feat-shared-agent-workspace-v1`
- Base SHA: `92b154567f563c97153438404201c4acf0c9ffea`
- Repair-cycle limit: `2`

## User-visible outcome

Jacob can create or reopen a local durable room, send a request, and watch Planner, Researcher, Builder, and Reviewer exchange durable messages while Kitty truthfully shows progress, partial work, and failures.

## Acceptance criteria

| ID | Observable criterion | Verification command or interaction | Required evidence |
|---|---|---|---|
| AC-1 | A room reopens with its messages, turns, and event history after a reload. | Focused Gateway and route tests; browser reload. | Durable rows returned by the room API and rendered transcript. |
| AC-2 | A submitted turn records per-agent start/completion state and a Planner to Researcher to Builder to Reviewer message chain. | Focused Gateway tests and real local model run. | Parent/recipient links plus durable events. |
| AC-3 | A provider or agent failure persists a failed/incomplete turn and visible failure record; it never reports completion. | Focused failure test. | Turn state, failure event, and system status message. |
| AC-4 | Builder only produces a proposal/handoff; it does not create KittyBuilder work. | Focused Gateway test and code review. | No Builder queue write or submission call. |
| AC-5 | The Agents view distinguishes prompts, handoffs, proposals, reviews, progress, failures, and incomplete work while it refreshes a running room. | Vitest and local browser acceptance. | UI test assertions and live browser evidence. |
| AC-6 | The completed slice passes the requested backend/frontend/build checks and a real configured-model local acceptance. | Recorded final commands. | Command output and persisted room transcript/events. |

## Non-goals

- Do not create a second Builder queue, submit a Mission, or start a Builder worker.
- Do not touch Letta, Discord, credentials, provider preferences, or unrelated worktrees.
- Do not add token streaming; durable agent-status updates are the required live progress surface.

## Prohibited shortcuts

- Do not use a fake backend for final browser acceptance.
- Do not turn provider errors into a completed response or hide partial messages.
- Do not claim Builder execution from a room proposal.
- Do not infer runtime success from code inspection alone.

## Context that must survive compaction or handoff

- Accepted requirements and decisions: four named agents participate; Builder is proposal-only; all room runtime state remains in Kitty's app database.
- Current implementation state: room turns are durable, serialized, background-executed Planner-to-Researcher-to-Builder-to-Reviewer handoffs. Builder is explicitly proposal-only. Startup interruption recovery records only transitions it wins.
- Changed paths and current SHA: begin from `92b154567f563c97153438404201c4acf0c9ffea`; runtime work is committed as `854f4e9e` and published in PR #498.
- Known failures/blockers: the configured live provider chain exhausted after two real model responses; AgentRouter's configured GPT-5.5 route has no credential. Ports 8000 and 4000 remain occupied by processes from an unknown checkout.
- Exact next verification action: configure a usable GPT-5.5/GPT-5.4 provider route, then submit and retain evidence for a clean four-agent room turn.

## Verifier report

| Criterion | Verdict (`PASS`, `FAIL`, `UNVERIFIED`) | Evidence | Required repair |
|---|---|---|---|
| AC-1 | PASS | Focused Gateway/route tests and live browser showed the persisted room transcript on the next submission. | None. |
| AC-2 | UNVERIFIED | Deterministic lifecycle test proves the four-agent durable chain; live configured providers returned real Planner and Researcher output, then exhausted before Builder/Reviewer. | Restore a usable configured model route and repeat the four-agent live turn. |
| AC-3 | PASS | Failure and timeout tests pass; live Builder/provider exhaustion persisted a failed turn and incomplete system message rather than completion. | None. |
| AC-4 | PASS | Builder prompt and focused lifecycle test enforce a proposal-only handoff; no room code calls KittyBuilder queue or worker APIs. | None. |
| AC-5 | PASS | 353 frontend tests and production build pass; live UI showed running progress, handoffs, failure status, and incomplete work. | None. |
| AC-6 | UNVERIFIED | Full backend suite passes: 4,172 tests, 0 failures, 0 errors, 1 skipped. Static checks, frontend suite, and production build pass. A successful configured-model four-agent run is unavailable. | Restore a usable provider route. |

## Final state

`blocked on external provider availability`

Evidence-bound summary: the runtime implementation is committed and has a passing full test suite; it is not a verified live delivery until the configured provider can complete a clean four-agent room turn.
