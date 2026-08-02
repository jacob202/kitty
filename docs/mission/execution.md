# Execution — ordered slices

One branch and PR per slice. Check this file and open PRs before starting
anything, so two sessions do not build the same thing twice.

Status vocabulary: `NOT STARTED`, `IN PROGRESS`, `IMPLEMENTED-NOT-VERIFIED`,
`VERIFIED`, `BLOCKED`, `REJECTED`.

## Slice 0 — Restore dependency resolution · VERIFIED

- **Branch/PR:** `claude/kitty-stabilization-fbydi0` → **PR #339, merged
  2026-08-01** as `8c58f52`
- **Owner:** completed
- **Change:** `requirements.txt` openai pin → `>=1.90.0,<1.110.0`; repair
  schema-invalid `.claude/STATE.md` and `.claude/HANDOFF.md` metadata;
  unstale `test_kitty_launcher_runtime`
- **Evidence:** `docs/mission/evidence.md` E1–E6b. Confirmed closed: `tests.yml`
  run 1145 on `origin/main` @ `8c58f52` completed `success`
  (2026-08-01T05:46:08Z), ending the 8-commit red streak.
- **Blocks:** nothing further

## Slice 0b — Enforce required checks on `main` · BLOCKED (needs Jacob)

**The original plan for this slice was wrong and has been replaced. Read this
before acting on any older description of it.**

- **Original plan:** add a `pip install -r requirements.txt` resolvability gate
  to `pr-risk-guardrails.yml`, on the theory that the Dependabot guardrail
  exemption let the bad bump skip the tests gate.
- **Why that was wrong:** it did not skip anything. PR #322 ran `pytest` and it
  **failed** (job 91080470314, 2026-07-31T05:25:32Z), alongside four other red
  checks. The PR was merged 11 hours later at 16:41 with every one of those
  still red. A resolvability gate would have produced one more red check that
  could be merged past exactly as easily. See `failures.md` F7.
- **Actual root cause:** `main` has no enforced required status checks, so a
  red PR is mergeable. Six Dependabot PRs were merged in a 4.5-minute window
  (16:40:42 → 16:45:03) and main was red for the next 8 commits.
- **Correct change:** enable branch protection on `main` requiring `pytest`,
  `lint`, `typecheck`, `hygiene`, `kitty-chat` and `browser-smoke` to pass
  before merge. This is a repository settings change needing admin rights, not
  a workflow file — an agent cannot and should not do it.
- **Acceptance:** open a PR with a deliberately failing test; confirm the merge
  button is blocked rather than merely red.
- **Note:** `docs/reference/PREVENTION_MECHANISMS.md` already *defines* a
  red-main freeze and Gate 0.7 marks it COMPLETE. Defined is not enforced —
  the same specced-versus-built gap that made Gate 0.1's claim false.
- **Local-testable:** no. Requires repo admin.

## Slice 0c — Remove dead `stop_owned_listener` · VERIFIED

- **Depends on:** slice 0 merged (met)
- **Branch/PR:** `cleanup/slice-0c`
- **Context:** `d9420f3` moved `cmd_down` to an unconditional port sweep and
  left `stop_owned_listener` (`kitty:133`) with zero callers. Its stale test
  assertions were the launcher failure in slice 0; the function itself was left
  in place to keep that diff scoped.
- **Change:** deleted the function. Project rule: no dead code.
- **Acceptance met:** `grep -c stop_owned_listener kitty` returns 0; launcher
  tests still pass. `cmd_down`'s unconditional port sweep, the launchd-ordering
  guarantee (bootout before the kill sweep), and port-collision refusals via
  `assert_port_available` are all still covered by
  `tests/test_kitty_launcher_runtime.py`.
- **Evidence:** `bash -n kitty` OK; `python3.12 -m pytest
  tests/test_kitty_launcher_runtime.py -q` → 4 passed.
- **Local-testable:** yes (done)

## Outcome A — Conversational Image Agent (issue #336)

Do not start A4+ before A1–A3 are merged. Do not expand into hosted providers,
LoRA training, multi-character scenes, critic loops, or masking — issue #336's
stop/split rule.

### A1 — Durable image-agent sessions · VERIFIED (against A1's acceptance)

- **Depends on:** slice 0 (met)
- **Branch/PR:** `claude/kitty-stabilization-fbydi0`
- **Change landed:** `gateway/migrations/029_image_sessions.sql` +
  `gateway/image_sessions.py`. Tables `image_sessions` and
  `image_session_turns`, plus a deferred `image_jobs.session_id` column added by
  `_ensure_session_column` (ALTER TABLE has no `IF NOT EXISTS` in SQLite — same
  pattern as `image_jobs._ensure_queue_columns`). Extends `image_jobs`;
  replaces nothing; dispatches nothing.
- **Acceptance met:** `tests/test_image_sessions.py`, 33 tests, all passing;
  `tests/test_image_jobs.py` 43 still passing (76 total, no regressions).
  Covers create/resume, dense per-session turn ordering, anchor selection and
  rejection, parent lineage, unknown-reference and duplicate-reference
  rejection, spend/attempt accumulation, and terminal-session write refusal.
  Restart-resume is exercised by every call opening its own connection.
- **Scope note:** this verifies A1's stated acceptance only. The user-visible
  two-turn browser flow is A6's job and remains unproven.
- **Design notes for the next slice:**
  - `set_anchor` accepts only a succeeded job carrying a verified artifact.
    An anchor that cannot be fed to a renderer fails at selection time with a
    reason, instead of at render time as a silent reroll.
  - `image_jobs.transition` already refuses to mark a job succeeded without an
    artifact, so `set_anchor`'s artifact check is defence in depth. That
    upstream guarantee is pinned by
    `TestAnchor::test_job_store_prevents_artifactless_success` — if it is ever
    removed, that test fails rather than the failure surfacing as a mystery.
  - `update_session()` with no fields and `end_session()` on an ended session
    both raise. Silent no-ops here are how a session forgets its anchor.
- **Local-testable:** yes (done)

### A2 — Plan persistence and approved-plan dispatch · VERIFIED

- **Depends on:** A1 (met)
- **Change landed:** `gateway/migrations/030_image_plans.sql` +
  `gateway/image_plans.py`. The plan is now a durable, session-owned artifact:
  `persist_plan` stores an approved `ImagePlan` under a stable `imgplan_…` id
  owned by the session that created it, and `require_approved_plan` is the
  single gate A2's dispatch path calls. `StudioGenerateRequest` gained
  `plan_id`/`session_id`; `studio_generate` dispatches from the stored plan's
  refined prompt, character, and recipe — request form fields for those are
  ignored, so a post-approval edit cannot change what renders. `guidance_tags`
  are carried through the plan → runner → renderer boundary
  (`image_runner.run` → `image_gen.generate`/`generate_with_character` →
  `provider_params_json` on the job) instead of dying at the plan preview.
  `/studio/plan` still returns an ephemeral preview when no session is given
  (the legacy Image Studio flow), and persists + returns `plan_id` when a
  session is supplied.
- **Acceptance met:** `tests/test_image_plans.py`, 22 tests, all passing;
  `tests/test_image_sessions.py` + `tests/test_image_jobs.py` +
  `tests/test_db.py` + `tests/test_image_recipes.py` +
  `tests/test_image_router.py` + `tests/test_image_cancel.py` +
  `tests/test_image_backends.py` still passing (no regressions). Proves:
  dispatch from a stored plan uses its refined prompt and guidance; a mutated
  form field after approval cannot change what renders; unknown plan → 404;
  cross-session, unapproved, malformed, and empty-session plans → 400 with a
  reason; guidance tags reach the renderer request; and a plan survives a store
  reopen.
- **Scope note:** this verifies A2's stated acceptance only. A3's controller,
  A4's real reference-conditioned editing, and A6's two-turn browser flow
  remain unproven.
- **Design notes for the next slice:**
  - `require_approved_plan(plan_id, session_id)` is the only way a plan id
    becomes render inputs. It fails loud on unknown, malformed, wrong-session,
    and unapproved plans at load time — never at render time.
  - `studio_generate` with `plan_id` still reads `negative_prompt`, `quality`,
    and `identity` from the request; the plan owns prompt, character, recipe,
    and guidance. If A4 wants the negative prompt pinned at approval time, the
    plan must store it.
- **Local-testable:** yes (done)

### A3 — Bounded image-specialist controller · VERIFIED

- **Depends on:** A1 (met)
- **Change landed:** `gateway/image_agent.py`. `decide(session_id, request)`
  runs at most `MAX_ROUNDS` (3) LLM calls through the existing `call_llm`
  routing (`operation="image.agent"`, `response_format=json_object`) and
  returns one validated `AgentDecision`. Read-only actions (`list_assets`,
  `get_guidance`, `inspect_anchor`) feed an observation back and consume a
  round; terminal actions (`generate`, `edit`, `cancel`, `clarify`) are
  validated and returned. The controller persists an approved plan through
  A2's `persist_plan` and records the turn — it never dispatches, so a
  decision is inspectable before any renderer or GPU is touched.
- **Acceptance met:** `tests/test_image_agent.py`, 32 tests, all passing;
  `tests/test_image_plans.py` + `tests/test_image_sessions.py` +
  `tests/test_image_jobs.py` + `tests/test_image_recipes.py` +
  `tests/test_image_router.py` + `tests/test_image_cancel.py` +
  `tests/test_image_backends.py` + `tests/test_db.py` → 161 passed, no
  regressions. Covers strict parsing (non-JSON, JSON array, missing action,
  unknown action, missing field, unexpected field, blank string, non-list,
  repeated entry), the loop bound (three read-only actions exhaust it and
  raise; an observation is fed back and the next round decides), unknown-id
  rejection (character outside the session, anchor the user never selected,
  unknown guidance tag), budget refusal on both attempt and spend ceilings,
  and the capability boundary.
- **Design notes for the next slice:**
  - `_parse_action` is strict on purpose: no code-fence stripping, no
    unknown-key tolerance, no defaulting of a missing field. A dropped
    `denoise` key reads to the user as an honoured one.
  - `edit_workflow_available()` is the capability gate, and it checks for the
    `workflows/image_to_image_v1/` bundle. Until A4 adds it, every `edit`
    raises `CapabilityError` rather than downgrading to a text-to-image
    reroll — issue #336's explicit fail case, pinned by
    `test_edit_is_refused_while_no_edit_workflow_is_installed`. A4 flips this
    by adding the bundle; it does not need to touch the controller.
  - `auto_route` ignores its `operation` argument, so `_route_recipe`
    asserts `supports_img2img` itself. If A4 makes routing operation-aware,
    that assertion becomes redundant rather than wrong.
  - The model reads the anchor, it never chooses one. An `edit` naming a job
    other than the session's current anchor is an unknown reference.
  - **Gap A5 must close:** A3 adds no HTTP route. `decide()` is unreachable
    from the browser until A5 adds a `/studio/agent` endpoint that calls it
    and dispatches the returned `plan_id` through the existing
    `/studio/generate` path. This was left out deliberately to keep an
    unproven endpoint out of the API surface.
- **Scope note:** this verifies A3's stated acceptance only. Every LLM call in
  these tests is a scripted stub. No real model output has been parsed, and no
  image was generated.
- **Local-testable:** yes (done)

### A4 — Real reference-conditioned editing · VERIFIED (schema and binding only)

- **Depends on:** A2, A3 (both met)
- **Change landed:** `workflows/image_to_image_v1/` added and hash-pinned
  (`workflow_sha256` in its manifest; tampering is rejected by the existing
  `WorkflowBundle.load` check). The bundle is `LoadImage → VAEEncode → KSampler
  → VAEDecode → SaveImage`, so the sampler starts from the encoded source image
  rather than an empty latent. `JobRequest` gained `source_image_id` and
  `denoise`; `WorkflowBundle.compile` binds both. The worker gained an
  authenticated `POST /v1/images` that stores an upload under its own content
  hash — the client's filename never reaches the filesystem, so there is no
  traversal left to defend against downstream. `/health` no longer names
  `text_to_image_v1`; it verifies every installed bundle and reports which
  consume a source image. `RunPodWorkerClient` gained `upload_source_image` and
  the two edit fields, which travel together and are omitted together.
- **Acceptance met:** `tests/test_image_to_image.py`, 34 tests, all passing.
  The acceptance assertion is
  `TestCompiledRequest::test_compiled_workflow_carries_the_source_image_and_denoise`
  — the compiled request carries the parent artifact at the `LoadImage` node and
  a denoise value at the sampler. Its inverse,
  `test_a_reroll_with_preservation_words_has_no_source_image_input`, pins the
  fail case: a text-to-image prompt containing "keep his face exactly the same"
  compiles with no `LoadImage` node and `denoise == 1.0`.
- **Design notes for the next slice:**
  - `WorkflowBundle.consumes_source_image` is the definition of an edit — the
    binding, not the prompt. `create_job` enforces agreement in both
    directions: an edit workflow without a source image is a 400, and a source
    image against a text-only workflow is a 400 rather than a silently ignored
    field.
  - `gateway.image_agent.edit_workflow_available()` (A3) checks for this
    bundle's directory. Adding it here is what flips A3's `CapabilityError`
    off — the controller needed no change.
  - The provider boundary is unchanged: the gateway addresses workflows by id,
    so Qwen-Image-Edit can be added as another bundle later.
- **Scope note:** schema and binding only, as this slice's own row predicted.
  Nothing was rendered — no ComfyUI, no GPU, no artifact. The gateway's
  `image_runner` still dispatches text-to-image; wiring an approved `img2img`
  decision through to the worker is A6's job.
- **Local-testable:** partly — schema and binding yes (done), real render no

### A4b — Gateway dispatch of an approved edit · VERIFIED (worker injected)

- **Depends on:** A4 (met)
- **Change landed:** `gateway/image_runner.run_edit()`. Resolves the anchor
  job's artifact from disk, uploads it to the worker, and submits
  `image_to_image_v1` with an explicit denoise. The worker is a parameter, not
  a module lookup — see the blocker below.
- **Acceptance met:** `tests/test_image_edit_dispatch.py`, 14 tests, all
  passing; `tests/test_image_runner.py` + the rest of the image suite → 198
  passed, no regressions. The acceptance assertion is
  `test_edit_sends_the_anchor_artifact_and_a_denoise`. Also covers: the job
  records `img2img` + `parent_id` + workflow id, lineage links to the anchor,
  a successful edit ends terminal with a verified artifact, and every refusal
  path (unknown anchor, unfinished anchor, artifact missing from disk,
  out-of-range denoise, worker success with no artifact, worker failure) leaves
  the job terminal rather than dangling.
- **Security note:** the worker chooses the output filename, so
  `_persist_artifact` keeps only its basename. Pinned by
  `test_a_crafted_output_filename_cannot_escape_the_job_directory`.
- **What this discovered — the real finding:** the gateway has **two unrelated
  image dispatch paths**, and A4 extended the one nothing calls.
  - Live: `gateway/image_gen.py` talks straight to `COMFY_URL`, building
    workflows inline in Python (`_wf_sdxl`, `_wf_ipadapter_sdxl`). This is what
    `image_runner.run` uses today.
  - Unwired: `workers/comfy_worker/` + `gateway/runpod_worker.py` +
    `workflows/*` hash-pinned bundles. `RunPodWorkerClient` has **zero callers
    in `gateway/`**, and there is no `KITTY_WORKER_*` env plumbing anywhere in
    the gateway.
  Issue #336 names the worker lane as the one to reuse and its acceptance
  requires RunPod, so the worker lane is the intended target — but connecting
  it is not a code change alone.
- **BLOCKED on Jacob:** wiring `run_edit` to a real worker needs a worker base
  URL and bearer token read from env/secrets. `AGENTS.md` and `CLAUDE.md`
  non-negotiable 4 put secrets/auth/env changes behind explicit approval, so
  this slice stops at an injected worker. Everything above the credential
  boundary is done and tested.
- **Local-testable:** yes, done (stub worker; no renderer, no GPU, no artifact)

### A5 — Conversational Image Studio UI · VERIFIED (tests only; browser unproven)

- **Depends on:** A3 (met)
- **Backend added here (A3's named gap):** `gateway/routes/extended.py` gained
  `POST /studio/sessions`, `GET /studio/sessions`, `GET /studio/sessions/{id}`,
  `POST /studio/sessions/{id}/anchor`, `DELETE /studio/sessions/{id}`, and
  `POST /studio/agent`. `/studio/agent` maps each controller error to a
  distinct status — 404 unknown session, 429 budget refused, 503 no capable
  renderer, 400 unknown reference or unsupported operation, 502 malformed model
  output or loop exhaustion — so the UI can say what actually went wrong.
  `/studio/generate` now attaches its job to the session and counts the
  attempt, which is what makes "use this" and restart-resume possible.
- **Frontend change landed:** `ImageStudio.tsx` is chat-first. The composer is
  always visible and empties itself after sending; a turn goes to
  `/studio/agent` first and dispatches only what the controller approved, from
  its `plan_id` rather than live form state. Results render inline as
  conversation turns with a "use this" button that sets the session anchor;
  the active anchor shows as a chip. Assistant turns state what stays fixed and
  what changes. `clarify` and `cancel` are answers in the conversation, not
  error banners. Plan inspection moved behind "advanced" — optional detail, no
  longer a step between asking and getting an image. Character library, gallery,
  offline/gateway-failure panels, and the fail-closed Enter behaviour are all
  retained.
- **Acceptance met:** `gateway/kitty-chat/tests/ImageStudio.test.tsx`, 12 tests,
  all passing. The two required cases are
  `runs a two-turn conversation: generate, select a result, then edit it` (which
  also asserts the render dispatches from `plan_id`, not the prompt) and the
  anchor-selection half of it. Plus: a clarifying question renders nothing, a
  refusal is not an error banner, a failing controller names the image
  specialist rather than the renderer, and the composer clears.
- **Test-contract changes:** the primary button is `send`, not `generate`
  (`data-testid="studio-send"`), and `preview plan` now lives behind
  `advanced`. Both existing assertions were updated rather than deleted. The
  PR #355 finding-5 stale-closure test needed the follow-up request retyped,
  because the composer now clears after a send — the fail-closed invariant it
  guards is unchanged and still asserted.
- **Scope note:** this verifies A5's frontend tests only. No browser ran, no
  screenshot exists, and the real two-turn flow against a live gateway is
  unproven. That is A6.
- **Local-testable:** yes (tests, done) / needs browser (real flow)

### A6 — Automatic compute lifecycle · NOT STARTED

- **Depends on:** A4, A5
- **Change:** controller provisions or reuses the configured RunPod worker,
  reports honest startup stages, runs, downloads and verifies the artifact,
  records cost and provenance, and stops compute per session policy.
- **Acceptance:** issue #336's hard acceptance test, all seven steps, with
  browser evidence, job/session records, parent lineage, renderer input,
  workflow/model version, duration, artifact hashes, and RunPod cleanup state.
- **Local-testable:** NO. Requires Kitty running, a browser, RunPod
  credentials, and real GPU spend. **This is the slice that closes Outcome A.**

## Outcome B — Trustworthy KittyBuilder

### B1 — Reconstruct the real Builder execution path · VERIFIED

- **Depends on:** slice 0 (met)
- **Change landed:** `docs/mission/builder-map.md`. No code changed.
- **Acceptance met:** all 27 modules classified with a proving call site —
  26 live, 1 reachable only from tests, 0 dead. One invocation traced in seven
  steps from `kitty:809` to `subprocess.Popen` at
  `gateway/builder_runner.py:1138`.
- **The finding:** `builder_adapters` is implemented, contract-tested, and
  unreachable. `ShellWorkerSession` and `OpenCodeServerSession` both exist;
  `run_packet` accepts `worker_session=` and branches to `_run_via_session`; and
  `_cmd_initiative_run_packet` never passes it
  (`gateway/builder_cli.py:1427-1438`). "KittyBuilder supports pluggable worker
  backends" is false today at the CLI. There is no dead module to delete, which
  makes B2's real question a decision rather than a cleanup: wire the seam, or
  say plainly that subprocess dispatch is the only supported backend.
- **Scope note:** static analysis plus one traced path. No packet was queued and
  no worker ran, so "is imported" is not "does execute". `builder_run.run_initiative`
  and the HTTP control plane were not traced.
- **Local-testable:** yes (done)
- **Note:** B2–B10 may now begin (decision D5 satisfied).

### B2–B10 — NOT STARTED

Blocked on B1. Covers: eliminating contradictory launchers and dead entry
points; deterministic and observable branch/worktree/PR/check/review/retry/
cancellation/exhaustion/restart/recovery behaviour; preventing workers from
leaving conflicting or permanently-red PRs without a surfaced recovery action;
one owner, one state, one evidence trail per queued packet; failed checks and
merge conflicts as actionable Builder state; clean-checkout verification; one
complete mission through queue → execution → branch/commit → PR → checks →
review → merge-ready or an honestly classified terminal failure; restart and
recovery mid-mission without duplicated work or lost state; UI and CLI
agreeing on what is running, blocked, failed, completed and next.

Items 8, 9 and 10 need a real runtime and cannot be closed in a container.

### B11 — Conversational KittyBuilder · NOT STARTED

Deferred by decision D6. Lands after B2–B10, not before.

## Outcome C — One roadmap · VERIFIED for this pass

- **Owner:** this session
- **Change:** `docs/ROADMAP.md` corrected — Gate 0.1 downgraded from COMPLETE
  to the verified red state; Gate 0.8 added for the dependency repair; §3.4
  image lane unblocked per decision D3 and issue #336; every status given a
  verified condition and acceptance evidence.
- **Re-run:** any session that changes a status must re-verify it here.

## Ordering summary

```
slice 0 (done) → 0b → A1 → A2 ┐
                       A1 → A3 ┼→ A4 → A6   (A6 needs GPU + browser)
                             A3 → A5 ┘
slice 0 (done) → B1 → B2..B10 → B11
```

`A6` and `B8/B9/B10` are the only items that strictly cannot be executed in a
credential-less container. Everything else can.
