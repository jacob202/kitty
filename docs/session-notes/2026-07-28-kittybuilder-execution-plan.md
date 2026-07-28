# KittyBuilder execution plan — durable continuation packet

## Read this first

This is the operational continuation packet for the KittyBuilder recovery,
product-truthfulness, and image-planning work started 2026-07-28. It is written
so a lower-cost worker can continue without rediscovering the investigation.

Before any mutation, re-verify:

```bash
git status --short --branch
git log -5 --oneline
./kitty context --agent
```

Read, in this order:

1. `START_HERE.md`
2. `docs/AUTHORITY_MAP.md`
3. `docs/ACTIVE_MISSION.md`
4. `docs/ROADMAP.md`
5. `docs/session-notes/2026-07-28-kittybuilder-recovery-checkpoint.md`
6. `docs/research/GENEVOLVE_ADAPTATION_2026-07-28.md`
7. `.slim/deepwork/kittybuilder-reliability-and-brain.md` if it exists locally

## Hard rules

- Never edit `data/kittybuilder/*` directly. Use only supported Builder CLI/API
  projections; do not claim, release, retry, pause, cancel, or requeue a
  canonical Builder record until fresh runtime evidence proves the action.
- The worktree-local Builder DB is empty and healthy. It is not the canonical
  queue. Do not use its doctor result as proof that the live queue is healthy.
- The existing runtime at port 4000 was serving canonical commit `1c6487d`, not
  this worktree. Do not use browser behavior as proof for this branch until this
  worktree is explicitly launched and its build identity is visible.
- Do not create a second Builder queue, state store, scheduler, or project
  manager. Kitty consumes bounded Builder projections; Builder owns execution
  truth.
- Do not run tests, lint, typecheck, or build until Jacob explicitly sends
  `/qg` or `/qg all`, per `AGENTS.md`. Write focused regression tests with the
  repair, record the exact commands that need to run, and mark them unexecuted.
- Commit every coherent checkpoint after reviewing its staged diff. Never push
  or merge without Jacob's explicit request.

## Evidence already gathered

### Live Builder and UI

- `GET http://127.0.0.1:4000/proxy/runtime/manifest` reported Builder
  `degraded`, six partial packet records out of 75, and a queue of 80 total:
  11 queued, 2 blocked, 3 awaiting review, 36 done, 28 cancelled.
- The Builder page was information-rich but unsafe and overwhelming: 91
  reachable controls in a short desktop viewport, 45 attention items, and a
  duplicated full-packet modal. The `Read-only execution status` label conflicts
  with visible resume/cleanup controls that can mutate Builder state.
- The Work page and Builder page overlap but the running Work view did not show
  its promised Builder signal/link. The design direction is **Work = calm
  cross-domain now page**, **Build = read-only decision radar**, and only an
  explicitly labelled Manage Builder flow may mutate state after a scope
  confirmation. Degraded, stale, partial, and failed evidence must remain
  visible and drilled down, never hidden.

### Reliability review findings

The completed independent reliability review identified:

1. `gateway/builder_run.py` collapses `LOOP_CANCELLED` into exhausted packet
   handling. Cancellation must remain a distinct durable outcome and cannot
   consume/expose an exhaustion state.
2. `gateway/builder_attempt.py` and `gateway/builder_loop.py` can treat an
   outcome-null attempt as stale without sufficient run/PID/lease liveness
   evidence. `gateway/builder_initiative.py` can then leave a recovery-only
   blocked task outside selection. Recovery must preserve lease/attempt fencing.
3. `gateway/builder_status.py` hides cancellation provenance and can surface a
   raw stored initiative state that disagrees with the derived state.
4. Some of the six partial records are historic malformed publication/policy
   evidence, not a parser failure. Do not rewrite history merely to make the
   health badge green.
5. `kittybuilder-brain-v1` is active in the runtime but its retained initiative
   README says its source harvest already exists and downstream work must not be
   re-run until the roadmap promotes the delta. Do not retry
   `KB-BRAIN-00-source-harvest`.

### Frontend/backend alignment review findings

Implement after the recovery semantics are stable, in this order:

1. Hide unsupported repair actions that return `{ok:false}` while UI indicates
   success.
2. Remove mutation controls from the declared read-only Builder surface.
3. Distinguish provider `configured` from `health unknown`/`health available`.
4. Use Gateway health separately from LiteLLM model discovery in Settings.
5. Make the visible command-palette trigger actually open the palette or remove
   it.
6. Surface Studio transport/non-OK errors as actionable errors, not empty data.
7. Check an unavailable Builder fact before showing zero-queue/ready wording.

### GenEvolve research

The external source is cloned read-only at
`.slim/clonedeps/repos/MeiGen-AI__GenEvolve/`, pinned to `23c847c`. Its useful
pattern is a validated **plan → renderer** boundary, not its GPU/vLLM agent.
Kitty must retain its existing image jobs, local character references, renderer
controls, cancellation, and health semantics. Do not adopt GenEvolve's external
web/image search, `/tmp` cache, silent tool-error continuation, CUDA stack, or
unbounded ReAct loop.

Immediate discovered Studio contract repairs:

- `ImageStudio.tsx:145-150` sends `seed` and `image_count`, but
  `StudioGenerateRequest` in `gateway/routes/extended.py:406-414` declares
  neither. Either implement both end-to-end or reject them explicitly.
- `reference_ids` is declared but ignored by the route-to-runner call at
  `gateway/routes/extended.py:623-630`; resolve supported local references or
  remove the misleading field.
- `gateway/image_backends.py` registers ComfyUI and Stability while
  `gateway/image_runner.py:67-87` only routes ComfyUI and Draw Things. Align the
  visible engine choice with actual dispatch before adding renderer features.

## Active and blocked agent state at checkpoint

| Task | Dispatch | State | Required disposition |
| --- | --- | --- | --- |
| `task_d55e5ed58966` | `ctx_b453d4b457f6` | completed | Its stale-recovery repair was inspected and committed as `160806f fix(builder): fence stale attempt recovery`. |
| `task_25543048a25b` | proven `term_834dc3b6` session | completed | Its cancellation repair was inspected and committed as `08de685 fix(builder): preserve cancellation outcomes`. |
| `task_4a10b406a5e9` | `ctx_0501d3bc50dd` | blocked | New-terminal startup produced no work; superseded by `task_d55e5ed58966`. Preserve history, do not reuse. |
| `task_66658e84d90c` | `ctx_1777bd8eaed8` | blocked | New-terminal startup produced no work; superseded by `task_25543048a25b`. Preserve history, do not reuse. |
| `task_38303796bac9` | `ctx_3b73e1141f57` | blocked | Architecture terminal never started. It is not an approval and must not be waited on indefinitely. |

Completed review evidence came from working Orca sessions:

- `task_23fbbecd370f` reliability review, `ctx_1f4fbe008591`
- `task_eff4dfd1daae` eight-lens Work/Builder swarm, `ctx_0ec018f773ab`
- `task_9ce58b27bacb` frontend/Gateway alignment, `ctx_06f44c7780bf`

The canonical evidence handoff `msg_fcc2df76f79b` remains unanswered. It is
not needed to make source repairs because the supported live runtime projection
was already captured; it is needed before a later canonical queue mutation.

## Immediate execution sequence

### A. Stale-attempt recovery (completed)

Completed in `160806f fix(builder): fence stale attempt recovery`. The focused
regression command remains unexecuted pending `/qg`:

```bash
python3.12 -m pytest tests/test_builder_attempt.py tests/test_builder_loop.py tests/test_builder_initiative.py -q
```

The completed lane:

1. Check `git status --short --branch` and `git diff --name-only` before
   reading the diff. Expected writer-owned paths are
   `gateway/builder_attempt.py`, `gateway/builder_loop.py`,
   `gateway/builder_initiative.py`, and focused tests only.
2. Read the full diff. Reject unrelated changes or any `data/` mutation.
3. Ensure the implementation records a conservative liveness decision rather
   than guessing: durable run identity, PID/lease status, and explicit
   recovery-only reason must govern stale reconciliation.
4. Ensure a recovered blocked task cannot bypass claim version, lease token,
   or attempt budget invariants when it becomes selectable again.
5. Do not run gates yet. Stage expected files, review `git diff --cached`, then
   commit a focused Conventional Commit such as
   `fix(builder): prove stale attempt recovery`.
6. Record the exact focused gate command the next `/qg` must execute.

### B. Cancellation truthfulness (completed)

Completed in `08de685 fix(builder): preserve cancellation outcomes`. It keeps
`LOOP_CANCELLED` distinct from exhaustion, preserves cancellation provenance in
the status projection, and adds focused coverage. Its unexecuted `/qg` command:

```bash
python3.12 -m pytest tests/test_builder_run.py tests/test_builder_status.py -q
```

The completed lane required:

1. Keep `LOOP_CANCELLED` distinct from exhaustion in `builder_run.py`.
2. Preserve cancellation reason/event provenance in `builder_status.py` without
   fabricating a terminal outcome.
3. Add focused regression coverage in the two named test files.
4. Avoid all canonical queue mutations and do not run gates until `/qg`.
5. Stage, inspect, and commit only this diff, for example
   `fix(builder): preserve cancellation outcomes`.

### C. Validate and reconcile, only when authorized

When Jacob sends `/qg`, run only the two focused test groups first, then the
relevant quality gate if failures or integration scope justify it. After code
evidence exists, launch this worktree's Kitty processes on non-conflicting ports
and use browser evidence to prove the served build SHA plus recovery/projection
states. Do not touch the canonical Builder queue until its fresh projection
matches all preconditions in the recovery checkpoint.

## Builder vs direct classification

**Direct specialist only:** Builder recovery state machine, stale attempt
identity/liveness, cancellation semantics, status projection truthfulness,
mission/roadmap boundary decisions, any UI behavior requiring design judgment,
Brain interaction design, and any runtime database reconciliation.

**Potential Builder work only after a fresh packet authoring pass:** small
mechanical code/tests with current anchors, a clean base SHA, runnable
unmodified-tree failure, deterministic acceptance command, no UI judgment, no
canonical queue action, no external service, and a narrow allowed-path list.
Do not classify existing cancelled/queued packets from stale screen labels;
fresh supported state and source evidence decide eligibility.

## Later phases after recovery proof

1. Designer owns Work/Build consolidation and Builder Brain conversational
   surface. It consumes bounded projections only and never becomes a parallel
   queue/authority.
2. Implement the alignment repairs above with visual/browser proof on the
   actual served worktree.
3. Repair the current Studio contract before introducing a local `ImagePlan`.
   Then add only plan metadata, local selected reference provenance, and curated
   local guidance; send actual generation through existing `image_runner` and
   `image_jobs`.
4. Run an updated expert swarm only after the unified operational surface exists
   in a running worktree, not against the old canonical UI.

## Commit history carrying this work

- `40b04ee docs(builder): checkpoint recovery diagnosis`
- `96de6e6 docs(builder): record live surface findings`
- `3dc7a29 docs(builder): add worker continuation contract`
- `ea941b6 docs(image): record Genevolve adaptation plan`
- `8ab6754 docs(builder): record unavailable phase gate`
- `435325f docs(builder): add execution continuation`
- `160806f fix(builder): fence stale attempt recovery`
- `08de685 fix(builder): preserve cancellation outcomes`

Commit this continuation packet before resuming any code mutation.
