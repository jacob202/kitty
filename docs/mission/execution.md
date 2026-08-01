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

## Slice 0c — Remove dead `stop_owned_listener` · NOT STARTED

- **Depends on:** slice 0 merged
- **Context:** `d9420f3` moved `cmd_down` to an unconditional port sweep and
  left `stop_owned_listener` (`kitty:133`) with zero callers. Its stale test
  assertions were the launcher failure in slice 0; the function itself was left
  in place to keep that diff scoped.
- **Change:** delete the function. Project rule: no dead code.
- **Acceptance:** `grep -c stop_owned_listener kitty` returns 0; launcher tests
  still pass.
- **Local-testable:** yes

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

### A2 — Plan persistence and approved-plan dispatch · NOT STARTED

- **Depends on:** A1
- **Change:** persist `ImagePlan` with an id; add `plan_id` to
  `StudioGenerateRequest`; dispatch from the stored plan, not form state.
  Carry `guidance_tags` through to the renderer — today they die at the plan
  boundary (`extended.py:415` vs `:406`).
- **Acceptance:** a test proving generation dispatched from a stored plan uses
  that plan's refined prompt and guidance, and that a mutated form field after
  approval cannot change what renders.
- **Local-testable:** yes

### A3 — Bounded image-specialist controller · NOT STARTED

- **Depends on:** A1
- **Change:** `gateway/image_agent.py`. Max three rounds, strict JSON actions,
  deterministic validation. Local tools only: list session assets, retrieve one
  guidance skill, inspect current anchor, create validated plan, generate,
  edit/variation, cancel, clarify. Uses existing LLM routing and usage logging.
  Malformed output, unknown references, unsupported operations, missing worker
  capability, and budget refusal all fail loudly. The LLM chooses intent; it
  never mutates job state.
- **Acceptance:** strict-parse tests, loop-bound test, unknown-id rejection,
  budget-refusal test, malformed-output failure test.
- **Local-testable:** yes

### A4 — Real reference-conditioned editing · NOT STARTED

- **Depends on:** A2, A3
- **Change:** add and hash-pin `workflows/image_to_image_v1/`; extend the
  worker request/client schema with authenticated image upload, path safety,
  and explicit denoise/edit strength. Remove the hardcoded workflow name at
  `workers/comfy_worker/app.py:704`. Keep the provider boundary replaceable so
  Qwen-Image-Edit can challenge ComfyUI later.
- **Acceptance:** a test asserting the renderer request carries the parent
  artifact as an actual workflow input and a denoise value. A fresh
  text-to-image reroll containing preservation words fails this slice.
- **Local-testable:** partly — schema and binding yes, real render no

### A5 — Conversational Image Studio UI · NOT STARTED

- **Depends on:** A3
- **Change:** refactor `ImageStudio.tsx` to chat-first. Always-visible
  composer; references and active anchor as chips/thumbnails; assistant states
  what changes and what stays fixed; real stages, cancel, cost, failure
  detail; inline results with "use this" anchor selection; advanced controls
  hidden by default; character library and gallery retained. Plan inspection
  is optional detail, not a mandatory approval screen.
- **Acceptance:** frontend tests for the two-turn conversation and anchor
  selection; `make ui-test && make ui-build`.
- **Local-testable:** yes (tests) / needs browser (real flow)

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

### B1 — Reconstruct the real Builder execution path · NOT STARTED

- **Depends on:** slice 0
- **Change:** none. Produce `docs/mission/builder-map.md`: for each of the 27
  `builder_*` modules, whether it is on the live path, referenced only by
  tests, or dead. Trace one real invocation from `./kitty builder` through to
  worker dispatch.
- **Acceptance:** every module classified with the call site that proves it.
- **Local-testable:** yes (static + CLI tracing)
- **Note:** B2–B10 must not begin before this lands (decision D5).

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
