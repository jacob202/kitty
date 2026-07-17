# Handoff — 2026-07-16 — Continue Builder UI V1 at review

## Start here; do not repeat recovery

- Worktree:
  `/Users/jacobbrizinski/Projects/kitty/.worktrees/builder-ui-v1-complete`
- Branch: `feat/builder-ui-v1-complete`
- Verified base: `719ee15072ae53fcfb284a7865af06a0892ccf60`
- Draft PR: https://github.com/jacob202/kitty/pull/183
- Commits in order:
  - `da5a117` — recovered original read-only runtime status surface
  - `8f63233` — completed bounded schema-v2 backend projection and tests
  - `95cfd3e` — completed investigation UI, focus handling, and tests
- Original source `b1c1d7` from closed stacked PR #182 was missing from main.
  It has already been recovered. Do not cherry-pick it again and do not recreate
  either Builder UI worktree.

## Review surface

- Backend source/tests:
  `gateway/builder_status.py`, `gateway/builder_initiative.py`,
  `gateway/runtime_manifest.py`, `tests/test_builder_status.py`, and
  `tests/test_builder_initiative.py`.
- Client completion source/tests:
  `gateway/kitty-chat/src/components/BuilderSurface.tsx`,
  `gateway/kitty-chat/src/lib/gateway.ts`, and
  `gateway/kitty-chat/tests/BuilderSurface.test.tsx`.
- Recovered navigation/polling files are already in `da5a117`:
  `page.tsx`, `HomeState.tsx`, `Rail.tsx`, `queries.ts`, and their focused tests.

## Contract reviewers should protect

- Eight bulk snapshot queries; no per-packet SQL loop.
- Attempt history limited to ten with total/truncation metadata and newest first.
- Retry budget counts `failed`/`aborted`, not `crashed`.
- Eligibility/initiative derivation delegates to pure helpers beside the
  canonical scheduler semantics.
- Per-packet degraded records stay visible and do not collapse the whole
  manifest.
- Safe bounded summaries only; no raw output, local paths, process IDs, command
  arrays, environment, or secrets.
- Only canonical HTTPS GitHub PR links are clickable.
- Composite initiative + packet identity is used in the backend and UI.
- No mutation controls in V1.

## Verification ledger

- Backend: `616 passed` broad; `115 passed` focused.
- Frontend: `150 passed` complete; `52 passed` focused.
- TypeScript, Ruff, mypy, and `git diff --check`: passed.
- Browser: 24 scenarios passed across desktop/mobile; no reproducible Builder
  UI issue. Focus return, all failure classes, truncated history, partial data,
  duplicate IDs, stale/unavailable/empty/fetch failure, and Kitty isolation were
  exercised.
- Production Webpack compilation succeeds but the final Next 16 route check is
  blocked by an unchanged main-branch export in
  `gateway/kitty-chat/src/app/proxy/[...path]/route.ts`. Keep that separate from
  this PR unless Jacob explicitly expands scope.

## Known deferral

Logs and artifacts intentionally render unavailable. A future safe delivery API
must be bounded/cursor-based, keyed by durable resource IDs, report content type,
limits, and truncation, redact server-side, and never expose a local path,
command, environment value, or credential-bearing payload.

## Next action

Read PR #183 checks and review comments. Address only Builder-slice findings,
rerun the narrow affected suite plus the complete frontend/Builder suites when
warranted, and push normal commits only. Do not merge, force-push, rewrite
history, delete worktrees, or introduce Builder mutation endpoints.

---

## Historical checkpoint preserved below

### Handoff — 2026-07-16 — Engineering Leverage closeout

## Current truth

- Branch: `chore/engineering-leverage-phase-8-9`
- Base: `origin/main @ 6cd464fe6f867b6cd90a7f8d5e6c63ac8239c753`
- Decision: keep Engineering Leverage and Builder integrity as one branch and one PR.
- Builder Phase 2 lease/identity wiring is complete and its former xfails pass.
- `kb_mrm5ru85_9ea7` is cancelled. Do not claim, recreate, or restart it.
- No remote action has occurred. Pushing or creating the PR still requires Jacob.

## Preserve these worktrees

- `/Users/jacobbrizinski/Projects/kitty/.worktrees/campaign-p1-05` — `codex/campaign-p1-05`
- `/Users/jacobbrizinski/Projects/kitty/.worktrees/reconcile-builder-campaign` — `reconcile-builder-campaign`
- `/Users/jacobbrizinski/Projects/kitty/.worktrees/reconcile-phase2-p104` — `codex/reconcile-phase2-p104`
- `/Users/jacobbrizinski/Projects/kitty/.worktrees/reconcile-wip-campaign` — `feat/wip-campaign-and-runtime`

## What landed in the closeout

- `7ceb511` — production `run_packet` uses atomic lease + attempt claims, verifies
  post-worker Git/scope identity, and owner-fences deliberate release paths.
- `aee7c4a` — new packets cannot persist without a resolvable durable base SHA.
- `c2584bb` — the new MCP Ruff/mypy CI scope is green rather than known-red.
- `3a7e798` — initiative integration tests use the base SHA from their own repo.
- The audit bridge, project status, skill registry, canonical architecture,
  PR description, STATE, and this handoff now describe current behavior.

The complete validation ledger and the single unchanged full-suite failure are in
`.claude/STATE.md`.

## Deferred audit work

Do not reinterpret `✓` or `⏸` rows in
`docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md`.

- D2/A1: inspect references/history for the five root temporary artifacts before
  proposing archive or deletion.
- A2/H5: move the eight named generic skills out of the active registry while
  preserving their content; Jacob chose archive, not permanent deletion.
- D4/A3/H2: identify and migrate unique `scripts/curation/` behavior before removal.

These are mechanical follow-ups and should not displace the Builder UI read model.

## Implementation-ready Builder UI task

### Goal

Expose one truthful, read-only Builder status projection through the existing
runtime-manifest API, then render that projection in the existing Kitty UI. Do not
add mutation buttons in the first pass. The current
`runtime_manifest._builder_fact()` exposes only queue counts and initiative rows,
which is insufficient to explain an active or failed packet.

### Canonical ownership

| Concern | Owner | Canonical states/data |
|---|---|---|
| Initiative and packet definition/eligibility | `gateway/builder_initiative.py` | `active`, `paused`, `completed`, `failed`; dependencies, policy, allowed paths, durable `base_sha` |
| Task lifecycle | `gateway/builder_queue.py` | `queued`, `claimed`, `running`, `blocked`, `pr_opened`, `awaiting_review`, `done`, `failed`, `cancelled` |
| Attempt lifecycle | `gateway/builder_attempt.py` | open (`outcome is null`), `succeeded`, `failed`, `aborted`, `crashed`; attempt budget excludes `crashed` |
| Branch ownership | `gateway/builder_queue.py` `branch_leases` | lease ID, packet, worker, branch, canonical worktree, base SHA |
| Worker process | `gateway/builder_queue.py` + `builder_runner.py` | `starting`, `running`, `cancel_requested`, `exited`, `failed`, `timeout`, `cancelled`, `interrupted`, `lease_lost`, `scope_violation` |
| Validation/review | `gateway/builder_attempt.py` | validation `passed`/`failed`/`skipped`; review `approve`/`request_changes`/`reject` |
| Publication | `gateway/builder_publish.py` + `pr_links` | task publication states plus PR URL, checks, review, merged flag |
| Timeline/failure class | `gateway/builder_queue.py` events | append-only events; `infrastructure_failed` carries `counts_toward_budget: false` |

Packet status is a projection, not a new state machine. Derive it from the task,
attempt budget, lease/run, dependencies, and last relevant event.

### Required read-only projection

Add a small serializer module (recommended:
`gateway/builder_status.py`) and have `runtime_manifest._builder_fact()` call it.
Return a versioned value shaped like:

```text
{
  schema_version,
  queue,
  initiatives: [{
    initiative_id, title, state, pause_reason, next_packet, counts,
    packets: [{
      packet_id, title, task_id, task_state, eligibility,
      budget: {used, max, exhausted},
      attempt: {id, number, outcome, validation_status, review_verdict,
                failure_kind, updated_at} | null,
      lease: {id, worker_id, branch, base_sha, created_at} | null,
      run: {id, state, started_at, last_heartbeat_at, ended_at, exit_code} | null,
      publication: {pr_url, checks_state, review_state, merged} | null,
      last_event: {id, type, created_at, reason, counts_toward_budget} | null
    }]
  }]
}
```

Use bounded/cursor-like reads: latest attempt, latest run, latest relevant event,
and current lease only. Do not return every event on each 15-second poll.

### Truthful client behavior

- Loading: show a neutral skeleton; do not imply an empty queue.
- Stale: when `valid_until` has passed, keep the last snapshot visibly marked
  stale and disable future mutation controls.
- Unavailable/unknown: show the runtime fact's exact `reason`; never convert it to
  an empty Builder state.
- Cancelled: distinguish task `cancelled`, run `cancelled`, and attempt `aborted`.
- Crashed/infrastructure failure: show retryable infrastructure failure and that it
  did not consume attempt budget; do not label it implementation failure.
- Exhausted: derive from budget and show operator intervention required even when
  the underlying task is `blocked`.
- Live progress: retain the current 15-second runtime-manifest poll initially.
  Add a faster poll only while a run is active; no websocket is required for v1.

### Operator actions for a later mutation pass

- `queued`: run packet or cancel.
- `claimed`: inspect; operator release only when no live run owns it.
- `running`: request cancellation; never release directly.
- `blocked`: inspect evidence, retry through the existing release/run path, or
  publish only when successful attempt evidence exists.
- `pr_opened` / `awaiting_review`: sync PR/check/review state.
- `done` / `failed` / `cancelled`: read/archive only.

Do not expose these as enabled UI actions until explicit backend action endpoints
enforce the same fencing and legal transitions as the CLI.

### Fields that are unsafe or not ready

- Do not expose absolute worktree/log/artifact paths, command arrays, environment
  variables, process IDs, raw validation output, raw review output, or unbounded
  error payloads. They may leak local paths, prompts, or credentials.
- There is no public bounded `list_branch_leases`/status-projection API yet.
  Add the read serializer instead of making the UI join SQLite concepts.
- `list_events()` is unbounded; the projection needs a latest-event query rather
  than shipping full history.
- Failure reason needs a small enum (`implementation`, `identity`, `validation`,
  `review`, `infrastructure`, `cancelled`, `exhausted`) plus a sanitized message.

### Files and tests for the cheaper implementation pass

- Backend: `gateway/builder_status.py` (new),
  `gateway/runtime_manifest.py`, and focused `tests/test_builder_status.py` plus
  runtime-manifest contract coverage.
- Client: `gateway/kitty-chat/src/lib/gateway.ts`,
  `gateway/kitty-chat/src/lib/queries.ts`, and the existing Builder/RightPanel
  surface; add a focused component test.
- Acceptance: projection is deterministic on an isolated DB, handles missing DB
  as an explicit runtime fact, caps events, omits unsafe fields, represents every
  state above, and the UI distinguishes loading/stale/unavailable/crashed/exhausted.

## Stop conditions

- Do not push, merge, rewrite history, delete worktrees, or restart the cancelled
  initiative without explicit authorization.
- Do not build a second Builder state machine in TypeScript.
- Do not start deferred destructive audit work while implementing the UI read model.
