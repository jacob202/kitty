# KittyBuilder follow-on roadmap

## Goal

Make KittyBuilder's free-worker path reliable end to end, then close the
security/state-integrity blockers and preserve the remaining product and
handoff work as executable packets instead of rediscovering it in chat.

## Background

The first evidence slice is committed in `e42bfbb`: attempt artifacts are
scoped by task, and each run writes a privacy-bounded manifest. The previous
LF-01 run still exposed an adapter seam: the untracked OpenCode worker and
reviewer wrappers are not yet required to consume or verify the manifest, so a
worker/reviewer can still read stale or ambiguous context. The existing queue,
worktree, contract, and review gates are the source of truth; this roadmap
deepens those seams instead of adding a second orchestration service.

## Files

### Immediate vertical slice — free-worker adapter hardening

- `[MOD]` `scripts/kittybuilder_opencode_worker.sh` — require and locally stage
  the context manifest, pass only worktree-local paths to OpenCode, and fail
  loudly when the worker writes a result for a different attempt.
- `[MOD]` `scripts/kittybuilder_opencode_reviewer.sh` — stage the bundle,
  implementation result, and context manifest locally; require an independent
  read-only review and verify the reviewer output belongs to this attempt.
- `[NEW]` `tests/test_kittybuilder_opencode_adapters.py` — run both adapters
  against fake `opencode` commands and prove path isolation, required env,
  result copying, and reviewer immutability checks.
- `[MOD]` `docs/KITTYBUILDER_ORCA_SETUP.md` — document the adapter contract,
  manifest verification, and the exact free-worker stop conditions.

### Follow-on lanes — planned, not implemented in this slice

- `[MOD]` `docs/initiatives/trust-lane-v1.json` — keep TL-01 → TL-05 packet
  order and record evidence links/status; do not mix T2 work into this file.
- `[MOD]` `gateway/kitty-chat/src/components/` and
  `[MOD]` `gateway/kitty-chat/src/lib/gateway.ts` — TL-01/TL-03/TL-04 UI
  reliability slices, each with its existing focused tests.
- `[MOD]` `gateway/doctor.py`, `[MOD]` `kitty`, `[NEW]`
  `tests/test_doctor_freshness.py` — TL-02 stale-process freshness warning.
- `[MOD]` `gateway/memories.py`, `[MOD]` `gateway/routes/memories.py`,
  `[MOD]` `gateway/monitors.py`, `[MOD]` `gateway/routes/monitors.py`,
  `[MOD]` `tests/` — TL-05 fail-loud sweep, with one regression test per
  converted error path.
- `[MOD]` `kitty`, `[MOD]` `gateway/kitty-chat/src/app/proxy/[...path]/route.ts`,
  `[MOD]` `gateway/routes/capture.py`, `[MOD]` `gateway/routes/knowledge.py`,
  `[NEW]` targeted security tests — T2 Card A: loopback binding, proxy target
  allowlisting, and SSRF-safe local-file/URL ingestion.
- `[MOD]` `gateway/agent_runner.py`, `[MOD]` `gateway/task_runner.py`,
  `[MOD]` `gateway/verifier.py`, `[NEW]` targeted state-machine tests — T2
  Card B: completion must be evidence-backed and cancellation must be durable.
- `[NEW]` `gateway/builder_evidence.py`, `[NEW]` `gateway/routes/builder.py`,
  `[MOD]` `gateway/routes/register.py`, `[NEW]` route tests, and `[MOD]`
  `gateway/kitty-chat/src/` — read-only Builder evidence for Kitty's delegated
  work card; expose status, next action, failure reason, and artifact links,
  not raw logs.
- `[NEW]` `docs/fable-context/KITTYBUILDER-HANDOFF-V2.md` — canonical Fable
  preload containing architecture, current commits, packet order, model
  routing, known holes, and operating boundaries.
- `[MOD]` `docs/BLUEPRINT.md`, `[MOD]` `docs/ARCHITECTURE.md`, and `[MOD]`
  `docs/LEARNINGS.md` — reconcile code-backed decisions after the lanes land;
  do not create speculative roadmap prose before evidence exists.

## Steps

### Lane 0 — preserve context before execution

- [ ] Save this roadmap and link it from `.claude/STATE.md` and
  `.claude/HANDOFF.md`.
- [ ] Keep the current `main` commit, active LF-01 worktree, untracked adapter
  scripts, and concurrent `trust-lane-v1` edits visible; never stage them by
  accident.
- [ ] Treat every packet as a closed contract: objective, allowed paths,
  forbidden paths, validation command, reviewer, stop condition, and evidence
  location.

### Lane 1 — harden the free OpenCode adapters (implement next)

- [ ] Make the worker copy `KB_BUNDLE_PATH` and
  `KB_CONTEXT_MANIFEST_PATH` into the isolated worktree before calling
  OpenCode; the model prompt must reference only those local copies.
- [ ] Make the worker write to a local result path, validate that the JSON
  exists and is a single object, then copy it to the runner-owned
  `KB_RESULT_PATH` only after the local attempt ID matches.
- [ ] Make the reviewer stage the bundle, implementation result, and context
  manifest locally; include their SHA-256 values in the prompt and require a
  read-only worktree check before and after the review.
- [ ] Add fake-OpenCode adapter tests that cover missing env, stale external
  paths, result absence, result copy success, reviewer mutation, and clean
  success.
- [ ] Run the adapter tests plus the 106-test Builder slice, then rerun LF-01
  with a separate reviewer. Preserve all artifacts when it fails.

### Lane 2 — complete the existing T0/T1 trust lane

- [ ] Execute TL-01, TL-02, TL-03, TL-04, and TL-05 in packet order using
  separate implementation and review sessions.
- [ ] After each packet, record commit SHA, test command/result, reviewer
  verdict, and remaining uncertainty in the queue evidence and handoff.
- [ ] Do not let a free worker touch T2 Card A/B files; escalate those cards
  instead of widening an apparently successful packet.

### Lane 3 — close T2 safety rails

- [ ] Card A: confirm the UI and gateway bind loopback by default, reject
  non-loopback proxy targets unless explicitly allowlisted, and constrain URL
  downloads/local paths against SSRF and filesystem escape. Add negative tests
  before changing defaults.
- [ ] Card B: enumerate every task/agent terminal transition, require durable
  evidence before `completed`, make cancellation observable and idempotent,
  and add crash/timeout/late-result tests.
- [ ] Run the security/state tests with Codex/Jacob review; no autonomous free
  worker, push, merge, or secret/env change is allowed in this lane.

### Lane 4 — make evidence useful to Kitty

- [ ] Add a read-only Builder evidence seam that reads manifests without
  exposing raw prompts, secrets, or log tails.
- [ ] Bind the Home delegated-work card to that seam with explicit loading,
  empty, failed, and retry states; keep Kitty usable when Builder is offline.
- [ ] Add route and browser tests proving stale/missing manifests fail visibly
  rather than becoming an infinite spinner.

### Lane 5 — release audit and Fable preload

- [ ] Run the Python suite, frontend tests/build, browser smoke, and
  `./kitty doctor --json`; classify every failure as code, optional dependency,
  runtime, or environment.
- [ ] Reconcile `docs/BLUEPRINT.md`, `docs/ARCHITECTURE.md`, and
  `docs/LEARNINGS.md` with only verified behavior.
- [ ] Write the Fable preload with current commit, working tree, preserved
  worktrees, packet statuses, known holes, model/provider routing, and exact
  next command. Exclude secrets and private runtime data.

### Lane 6 — product value after trust is stable

- [ ] Implement the resume-loop surfaces that consume real state: one next
  action, needs-you escalations, and while-you-were-away evidence.
- [ ] Make memory consolidation real before exposing Insights/dreams as if they
  were populated.
- [ ] Revisit Chroma/integrations only after the capture → knowledge → state
  path has a verified, truthful lifecycle.

## Verification

### Immediate slice

- `bash -n scripts/kittybuilder_opencode_worker.sh scripts/kittybuilder_opencode_reviewer.sh`
  → no shell syntax errors.
- `venv/bin/ruff check gateway/builder_context.py gateway/builder_loop.py tests/`
  (scoped to touched Python tests) → clean.
- `venv/bin/pytest tests/test_kittybuilder_opencode_adapters.py
  tests/test_builder_context.py tests/test_builder_loop.py
  tests/test_builder_runner.py tests/test_builder_attempt.py -q` → all pass.
- A real LF-01 attempt produces distinct task-scoped artifacts, a manifest with
  context hashes, and an independent review verdict; a failed attempt remains
  inspectable.

### Final acceptance

- No free worker can read an external/stale bundle by accident.
- No reviewer can approve its own mutation or a different attempt's result.
- T2 security and completion-state risks have explicit owners and tests.
- Kitty can show delegated-work truth without depending on raw logs.
- Fable can resume from the handoff document without reading this chat.

## Key concepts

| Concept | Meaning |
| --- | --- |
| `KB_BUNDLE_PATH` | Runner-owned packet bundle; adapters may read it only after copying it locally. |
| `KB_CONTEXT_MANIFEST_PATH` | Runner-owned hash manifest for instructions/skills and task context. |
| `run-manifest.json` | Durable, privacy-bounded evidence for one task/attempt. |
| T0/T1 | Free, isolated implementation/review work with no push, secrets, or destructive actions. |
| T2 | Security, auth, persistence, concurrency, destructive, or broad-scope work requiring Codex/Jacob. |

## Approach and rejected alternatives

- Reuse the existing queue, worktree, contract, and manifest seams; do not add a
  telemetry service or a second database.
- Harden adapters before adding more agents; otherwise every new worker
  multiplies the same context-integrity failure.
- Keep the evidence API read-only and metadata-first; exposing transcript/log
  tails to the UI would create a new privacy and product-scope problem.
- Keep trust-lane packets separate from T2 cards; merging them would make free
  routing look safer than it is.

## Risks and mitigations

- **OpenCode ignores a prompt path:** local staging plus hash verification makes
  the wrong file detectable and preserves the failed artifact.
- **Concurrent edits are staged accidentally:** explicit file lists and the
  session handoff are mandatory before every commit.
- **Docs drift again:** each packet's closeout records evidence first, then the
  canonical docs are updated from that evidence.
- **A green worker hides a false completion:** the queue runner, deterministic
  validation, independent review, and T2 state tests remain separate gates.
