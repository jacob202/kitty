# Kitty Canonical Roadmap

**Status:** Active authority
**Ratified:** 2026-07-26; rewritten 2026-07-31 (recovery baseline)
**Owner:** Jacob, with Kitty or an explicitly assigned strong-model planner
**Authority:** ADR 0020 and `docs/AUTHORITY_MAP.md`

This is the only active roadmap. Older roadmaps, plans, audits, packets, and
initiative manifests remain evidence or backlog input until they are reviewed
and dispositioned here. Nothing is deleted merely because it is not active.
Every retained document has exactly one disposition in the ledger at
`docs/DISPOSITION_LEDGER.md`.

## Operating rule

Finish one trustworthy end-to-end product loop before expanding feature scope.

Current delivery chain:

> approved intent → authored bounded packet → proactive Builder execution →
> deterministic validation → independent review → policy-controlled merge →
> durable result → concise Kitty report

---

## Gate 0 — Repository and Release Recovery (IN PROGRESS)

### Objective

Restore a green `main` branch, repair CI automation, resolve the open PR queue,
and establish one truthful planning surface before any feature work proceeds.

### Ordered outcomes

0.1 **Restore green main**
- Python and frontend CI are green from a clean checkout.
- Was COMPLETE at `59f598c5` (2026-07-31) and **regressed the same day**.
- History of the regression (resolved): `tests.yml` `pytest` failed on 8
  consecutive main commits — runs 1124, 1125, 1126, 1127, 1132, 1133, 1134,
  1139, through HEAD `b68268b`. The job died at
  `pip install -r requirements.txt` with `ResolutionImpossible`; no test ran.
- Cause: Dependabot `600c0fa` raised the `openai` pin above the ceiling
  `mem0ai` 0.1.x requires. See outcome 0.8.
- Repair merged as PR #339 (`8c58f52`, 2026-08-01).
- Acceptance evidence met: `tests.yml` run **1145** on `origin/main` @
  `8c58f52` completed `success` (2026-08-01T05:46:08Z), ending the 8-commit red
  streak that ran from `092372b1` through `b68268b0`.
- Status: **VERIFIED** (2026-08-01, run 1145).
- This outcome regressed once already, silently, because a status line outlived
  its measurement. It stays true only while 0.7 is unenforced — re-measure, do
  not re-read.

0.2 **Repair PR automation**
- Labeler v5 schema, PR description comment permissions, risk-guardrails
  Dependabot exemption, pr-review-routing deletion.
- Verified: merged via #327 and #330.
- The "all five automation gates produce `success`" claim was measured against
  human PRs only and was false for Dependabot: `check-description` had no
  Dependabot waiver, so it failed on every open dependency PR (#314-320) while
  `pr-risk-guardrails.yml` had carried one since #327. Waiver added to
  `pr-description-check.yml`, matching the sibling gate's exact-login test.
- Status: COMPLETE. Re-measure this on a Dependabot PR, not a human one — the
  two gates disagreed for a week because only human PRs were checked.

0.3 **Reconcile open PR queue**
- Resolved overlap between #330 (test fix) and #306 (RunPod): merged #330,
  parked #306.
- Landed minimal main-green repair via #327, #328, #330.
- Repaired PR automation through #327.
- Harvested unique findings from #326 (48h review) and #328 (progress review):
  launcher build-freshness fix landed in #328, review docs preserved in
  `docs/research/pr-review-48h-2026-07-31.md` and
  `docs/research/pr-306-runpod-review-2026-07-31.md`.
- Closed #304 (stale continuity metadata), #308 (WIP Copilot on parked branch).
- Parked RunPod/Image Studio work until Phase 3 authorization (PR #306 remains
  open as draft reference).
- 13 Dependabot PRs (#311-323): now pass guardrails gate after #327. Mergeable
  individually as CI allows.
- Status: COMPLETE for triage. Dependabot PRs remain open for individual merge.

0.4 **Establish one truthful planning surface**
- Rewrite this roadmap as the sole authoritative sequence.
- Produce a complete disposition ledger (`docs/DISPOSITION_LEDGER.md`) covering
  every retained file under `docs/plans/`, `docs/planning/`, `docs/packets/`,
  `docs/initiatives/`, `docs/research/`, `docs/audit/`, and active
  recommendations.
- Resolve Phase 1/Phase 2 contradiction: the roadmap now defines both phases,
  and the active mission KLF-001 sits within Phase 2.
- Ensure clean workers can determine current priority from this file and
  supported runtime evidence.
- Status: COMPLETE with this commit. Ledger at `docs/DISPOSITION_LEDGER.md`.

0.5 **Fix competing launcher paths and probe/open mismatch**
- VERIFIED 2026-07-31: no `com.kitty.ui` launch agent is installed or loaded.
- Two Next servers from different Kitty checkouts simultaneously occupy port
  4000 on separate IPv4/IPv6 bindings. `kitty` probes `127.0.0.1:4000` (hits
  canonical IPv4) but opens `http://localhost:4000` (browser resolves to IPv6,
  hits piddock worktree). The operator validates one checkout and views another.
- `pid_owned_by_kitty()` (`kitty:90-95`) scopes "Kitty-owned" to `$KITTY_ROOT`
  only. Running `./kitty down` from the canonical checkout leaves piddock
  worktree listeners running as "unrelated."
- The #328 freshness repair applies to `start_ui.sh` only — which is never
  invoked since the launch agent doesn't exist. The `kitty` CLI starts `next
  dev` directly, bypassing all freshness checks.
- Required fix: one canonical UI bootstrap used by `kitty`, `launchd`, phone
  access, and production startup:
  - one host/address used consistently for probing and opening;
  - refusal to launch when any IPv4 or IPv6 listener comes from another worktree;
  - mode, checkout path, source SHA, build SHA, PID, and port printed at startup;
  - stale-build handling shared rather than implemented in only one launcher;
  - shutdown that recognizes conflicting Kitty worktrees instead of calling
    them unrelated.
- Dependencies: Gate 0.4 (planning surface).
- Verification: `./kitty up` from two separate worktrees; the second must
  refuse to start. `./kitty down` from either worktree must stop all Kitty
  listeners on all ports. `curl http://127.0.0.1:4000/health` and
  `curl http://[::1]:4000/health` must return the same response from the same
  process. `./kitty status` must report source SHA, build SHA, checkout path,
  and freshness for every Kitty-owned listener.
- Artifacts: updated `kitty` CLI, shared bootstrap library, launcher contract.
- Implementer: strong model with repo and shell access.
- Verifier: independent model (must have repo, shell, and browser access to
  confirm both loopback addresses hit the same process).
- Failure: any listener from a non-canonical worktree survives `./kitty down`;
  any health probe hits a different process than the browser opens.
- Evidence: `./kitty status` output showing one listener per port, matching
  `lsof -iTCP:4000 -sTCP:LISTEN`.
- Owner: Jacob (authorization).
- Status: PENDING.

0.6 **Define the launcher contract**
- One launcher contract across production (`launchd`) and development
  (`./kitty up`) modes.
- Both paths delegate to shared bootstrap and health logic.
- Expose: mode, source SHA, build SHA, ports, process ownership, freshness.
- No silent alternate path may serve an unknown build.
- `scripts/desktop/start_ui.sh` now rebuilds when source is newer than the last
  build and fails loud on build failure (from #328), but this path is not
  currently invoked since no launch agent is installed.
- Status: COMPLETE as document. Implementation blocked on outcome 0.5.

0.7 **Add enforceable prevention mechanisms**
- Red-main freeze: CI status check on `main` branch push is required.
- One active implementation lane: at most one non-Dependabot feature PR open
  against `main` at a time.
- Branch freshness and conflict checks: CI gate on out-of-date branches.
- Open-PR overlap detection: CI comment when two PRs touch the same files.
- Required checks: all six CI jobs must pass before merge.
- Independent review: every PR must pass review by a model other than the author.
- Stale-draft policy: drafts unchanged for 7 days are auto-closed.
- Roadmap inventory coverage: every file under docs/plans/, docs/planning/,
  docs/packets/, docs/initiatives/ must appear in the disposition ledger.
- Active mission phase must exist in the roadmap: CI check verifies this.
- Evidence requirements: UI evidence (browser-smoke), restore evidence
  (test suite), cost evidence (where applicable), cleanup evidence (where
  applicable).
- Status: **DEFINED, NOT ENFORCED.** Corrected 2026-08-01 from COMPLETE.
  The mechanisms are written down in `docs/reference/PREVENTION_MECHANISMS.md`;
  none of them is enforced by the repository.
- Verified counter-example: the first listed mechanism is the red-main freeze
  ("CI status check on `main` branch push is required"). PR #322 ran `pytest`,
  `pytest` failed at 2026-07-31T05:25:32Z, and the PR was merged at 16:41 that
  day with that failure and four other red checks still standing. It was one of
  six Dependabot PRs merged inside 4.5 minutes; `main` was red for the next 8
  commits.
- `main` has no enforced required status checks, so a red PR is mergeable.
  Writing the policy down did not create the branch protection rule.
- Required to actually close: enable branch protection on `main` requiring
  `pytest`, `lint`, `typecheck`, `hygiene`, `kitty-chat`, `browser-smoke`.
  This needs repo admin rights — Jacob, not an agent.
- Acceptance evidence: a PR with a deliberately failing test whose merge button
  is blocked, not merely red.
- Detail: `docs/mission/evidence.md` E7.

0.8 **Keep the dependency tree resolvable**
- Current verified condition: `requirements.txt` could not be installed at all
  from a clean checkout. Reproduced locally with CI's exact error before any
  change was made.
- User-visible outcome: CI can run; no merge can leave the tree unresolvable.
- Owner subsystem: repository tooling / `.github/workflows`.
- Dependencies: none. This blocks every other outcome in every phase.
- Change landed: `openai` pin restored to `>=1.90.0,<1.110.0` (mem0ai 0.1.x's
  own ceiling) with a comment recording the coupling. Clean venv install now
  resolves; the CI pytest command returns 3452 passed / 7 failed / 77.50%
  coverage against a 73% floor. Four failures are container-environmental; the
  three real ones were schema-invalid `.claude/` checkpoint metadata, repaired
  in the same branch.
- Merged as PR #339 (`8c58f52`, 2026-08-01).
- Remaining work: none here. An earlier draft of this outcome proposed adding a
  resolvability gate to `pr-risk-guardrails.yml`, on the theory that the
  Dependabot exemption let `600c0fa` skip the tests gate. **That was wrong.**
  `pytest` ran on PR #322 and failed; the PR was merged anyway. Nothing was
  bypassed, so a new gate would only add another ignorable red check. The
  enforcement gap is tracked under outcome 0.7.
- Acceptance evidence met: `tests.yml` run **1145** on `origin/main` @
  `8c58f52` completed `success` (2026-08-01T05:46:08Z).
- Status: **VERIFIED** (2026-08-01, run 1145).
- Detail: `docs/mission/evidence.md` E1–E7.

### Exit criteria

Gate 0 exits when:
- All outcomes 0.1 through 0.8 are complete with verified evidence.
- CI is green on `origin/main` with all six required jobs passing.
- No open PR older than 7 days without activity (excluding approved Dependabot).
- The disposition ledger contains every retained planning file.
- `./kitty down` from the canonical checkout cleans all Kitty-owned listeners
  across all worktrees.
- `curl http://127.0.0.1:4000/health` and `curl http://[::1]:4000/health`
  return the same response from the same process.
- `./kitty status` reports source SHA, build SHA, checkout path, PID, and
  freshness for every managed listener.

---

## Phase 1 — Trustworthy End-to-End Proof

### Objective

Prove the full delivery chain works end to end: Builder executes approved
packets, survives failure without fabrication, and produces independently
verifiable results.

### Ordered outcomes

1.1 **Close Builder reliability by evidence**
- Calculate the exact remaining delta of Packet 026/027 Builder reliability.
- Prove crash/restart, stale lease, dirty worktree, interrupted review, and
  provider-exhaustion recovery.
- Prove Builder can state what happened without fabricated success.
- Dependencies: Gate 0 complete.
- Verification: `./kitty builder initiative doctor --json` reports consistent
  state before and after induced failures.
- Artifacts: reliability report, recovery log.
- Implementer: strong model with repo, CI, and Builder DB access.
- Verifier: independent model with read-only Builder projection access.
- Failure: any recovery path produces fabricated success or silent loss.
- Evidence: `docs/research/` or `docs/audit/` as appropriate.
- Owner: Jacob.
- Status: PENDING, with one named blocker.
- Recovery is proven live and repeatably by `scripts/builder_recovery_proof.py`
  — crash, stale lease, out-of-scope debris, interrupted review, provider
  exhaustion, operator-completed closeout, and clean completion after all of
  them, plus doctor consistency across the run. 8/8
  (`docs/research/phase1-1-builder-recovery-proof.md`).
- Delta calculated 2026-08-01 against `27deef1`, requirement by requirement
  against code rather than packet prose
  (`docs/research/packet-026-027-delta-2026-08-01.md`). Packet 027 is complete.
  Packet 026 is complete except for one reachability gap.
- Remaining blocker: the operator-completed closeout is unreachable through
  `run-packet`, the command Packet 026 tells operators to use. `run-packet`
  spends the whole attempt budget retrying a failing worker, a review cannot
  attach to a closed attempt, and `start-attempt` then answers `operator
  intervention required` — an intervention no CLI verb performs. The workflow
  itself is sound; only the door is shut. Smallest fix: an operator
  `grant-attempt` verb that records one further attempt with a reason.
- This outcome does not close on the recovery evidence alone. Closing it means
  either landing that verb or deciding the manual four-command path is the
  supported workflow and correcting Packet 026's demo section to say so.

1.2 **Create executable work for weak/free models**
- Write at least two real JSON manifest packets meeting
  `docs/FREE_MODEL_PACKET_STANDARD.md`.
- Verify every acceptance gate runs and fails on the unmodified tree.
- Preserve the existing shell adapter's clean-failure and partial-work rules.
- Dependencies: 1.1 (Builder reliability).
- Verification: `./kitty builder packet validate <packet.json>` exits 0;
  acceptance gates exit non-zero on unmodified tree.
- Artifacts: two validated JSON packet manifests.
- Implementer: strong model with repo access.
- Verifier: free/weak model executing the packet against the acceptance gates.
- Failure: acceptance gate passes when it should fail, or packet cannot be
  executed by a free model.
- Evidence: acceptance gate run output, free-model execution log.
- Owner: Jacob (approval), strong-model planner (authoring).
- Status: PENDING.

1.3 **Prove proactive delivery in daylight**
- Run Builder unattended across approved eligible packets.
- Continue after an unrelated packet failure.
- Preserve and resume safely on provider exhaustion.
- Commit, push, open/update PRs, and exercise the correct manual or automatic
  merge policy.
- Read the resulting report and verify it against Git, GitHub, and Builder
  evidence.
- Dependencies: 1.1, 1.2.
- Verification: independent verifier reads the daylight run report and
  cross-references Builder state, Git history, and GitHub PRs.
- Artifacts: daylight run report, Builder state snapshot, Git log.
- Implementer: Builder free worker.
- Verifier: independent model with repo, GitHub, and Builder projection access.
- Failure: any claim in the report that does not match Git/GitHub/Builder evidence.
- Evidence: `docs/research/ktf-004-daylight-run-evidence.md` or similar.
- Owner: Jacob (authorization), Builder (execution).
- Status: PENDING.

1.4 **Prove the actual product loop**
- Choose one real life project already represented by Kitty.
- Refresh and resume its truthful state.
- Produce one concrete next move.
- Deliver it through the supported phone/brief path.
- Record what happened and surface the next action without archaeology.
- Dependencies: 1.3 (daylight proof), phone/brief path operational.
- Verification: Jacob confirms the next move was received on his phone, and an
  independent verifier can reconstruct the sequence from Git/Builder evidence.
- Artifacts: phone delivery log, Git commit showing the next move.
- Implementer: Kitty (production runtime).
- Verifier: Jacob (live verification), strong model (evidence reconstruction).
- Failure: next move not delivered, or cannot be reconstructed from evidence.
- Evidence: phone screenshot or delivery confirmation, Git commit.
- Owner: Jacob (life project selection), Kitty (execution).
- Status: PENDING.

### Exit criteria

Phase 1 exits only when:
- Builder has at least two verified `free-exec` packets.
- One unattended daylight run safely crosses packet failure and provider
  exhaustion boundaries.
- One low-risk packet completes the full approved delivery path.
- One real project completes the resume-loop proof end to end.
- The resulting status can be reconstructed from supported evidence without
  chat history.

---

## Phase 2 — Life-First Daily Driver (KLF-001)

### Objective

Make Kitty's Home surface reliably expose one truthful life-project move,
independently from active chat state or transient startup failures. This phase
contains the KLF-001 mission scope and extends it to the full daily-driver
experience: backup/restore, phone delivery, and the move-in bar.

### Active mission: KLF-001 "Phase 2 Life-First Home Truth"

Scope (from `docs/ACTIVE_MISSION.md`):
1. Keep Home and Chat as separate product surfaces.
2. Recover automatically from a transient Gateway health timeout.
3. Ensure `/repairs` runs blocking checks outside the event loop.
4. Label Builder transition-history defects accurately rather than as leases.
5. Report healthy Kitty-owned listeners as running even when pidfiles are stale.
6. Reconcile mission and checkpoint metadata with live Git state.

Acceptance contract (verified):
- Home renders the life-first dashboard even when the active chat has messages.
- A transient startup health failure retries and reaches the application.
- Live Repairs reports the healthy Gateway and LiteLLM as healthy.
- Builder rows lacking event history are not described as stale leases.
- `./kitty status` reports healthy Kitty-owned listeners as running.
- Focused frontend and backend tests pass.
- The running app shows the same life-first step at desktop and mobile widths,
  with no horizontal mobile overflow.
- `./kitty context --agent` has no continuity failures.

KLF-001 status: RUNNING. Acceptance items delivered via #325. Evidence at
`docs/research/ktf-001-reliability-reconciliation-2026-07-30.md`.

### Ordered outcomes

2.1 **Complete KLF-001 acceptance verification**
- Independently verify every KLF-001 acceptance criterion against a running
  instance from a fresh checkout.
- Dependencies: Gate 0, Phase 1 complete.
- Verification: each acceptance item confirmed by independent verifier with
  browser, runtime, and kitty CLI access.
- Artifacts: verification report.
- Implementer: N/A (already built).
- Verifier: independent model with browser, runtime, and repo access.
- Failure: any acceptance item not independently reproducible.
- Evidence: `docs/research/` or live screenshot/CLI output.
- Owner: independent verifier.
- Status: PENDING verification.

2.2 **Prove backup and restore**
- Backup: Kitty's data directory is archived to a recoverable location without
  manual steps.
- Restore: the archive can be restored to a fresh checkout and Kitty reaches
  the same operational state.
- Verification: run backup, delete data/, restore, run `./kitty doctor --json`
  and confirm identical state (pass/warn/fail counts match within tolerance).
- Dependencies: Gate 0, data directory structure stable.
- Artifacts: backup script, restore script, before/after doctor output.
- Implementer: strong model with repo and filesystem access.
- Verifier: independent model comparing before/after doctor output.
- Failure: backup produces an unrecoverable archive, or restored state differs.
- Evidence: before/after doctor JSON output.
- Owner: Jacob.
- Status: PENDING.

2.3 **Prove the move-in bar**
- The five move-in criteria from `docs/packets/README.md` § "The finish line":
  1. Morning brief on iPhone with real mail and deadlines.
  2. Every active project shows one concrete next step.
  3. Benefits/admin paper is watched: photo a letter, deadline extracted,
     escalated to phone before it bites.
  4. Capture comes back: anything thrown at Kitty from the phone resurfaces
     at the right moment.
  5. Everything Kitty did is an auditable queue row; nothing external ever
     sent without approval.
- Dependencies: 2.1 (KLF-001 verified), 2.2 (backup/restore), Phase 1 complete.
- Verification: Jacob confirms each criterion on his iPhone and desktop.
- Artifacts: Jacob's confirmation, audit log.
- Implementer: Kitty (production runtime).
- Verifier: Jacob (live usage).
- Failure: any criterion not satisfied on a random Tuesday.
- Evidence: Jacob's usage log, queue audit.
- Owner: Jacob.
- Status: PENDING.

### Exit criteria

Phase 2 exits only when:
- All KLF-001 acceptance criteria are independently verified.
- Backup and restore are proven with identical pre/post `./kitty doctor` state.
- Jacob confirms all five move-in criteria on his primary devices.
- No active authority file contradicts the roadmap or active mission.

---

## Phase 3 — Execution Reliability

### Objective

Harden the execution substrate. Worker contracts, runtime projections, process
hardening, and Builder UI — the infrastructure that makes autonomous execution
trustworthy at scale.

### Ordered outcomes

3.1 **Unified worker contracts and model/cost policy**
- Define one WorkerSession contract covering all model types (strong, weak, free).
- Define cost policy with per-model budgets and provider failover.
- Builder enforces contracts at task dispatch time.
- Dependencies: Phase 2 complete.
- Verification: contract violation is rejected at dispatch; cost overrun stops
  execution with audit record.
- Artifacts: WorkerSession contract spec, cost policy config.
- Implementer: strong-model planner.
- Verifier: independent model executing boundary-case contract tests.
- Failure: contract bypassed, or cost overrun not enforced.
- Evidence: contract test suite output.
- Owner: Jacob (policy), strong-model planner (implementation).
- Status: PENDING.

3.2 **Unified runtime projections and Builder UI**
- Builder status, queue, initiative, and evidence projections share one schema.
- Builder UI (cockpit) shows live queue, lease, and evidence state.
- Operator commands work through UI and CLI equivalently.
- Dependencies: 3.1.
- Verification: same operator command produces identical Builder state
  projection via UI and CLI.
- Artifacts: shared projection schema, Builder UI.
- Implementer: strong model with frontend and backend access.
- Verifier: independent model comparing UI and CLI output.
- Failure: UI and CLI show different state for the same query.
- Evidence: side-by-side screenshot and CLI output.
- Owner: Jacob.
- Status: PENDING.

3.3 **Process hardening**
- Reproducible review with durable receipts and enforced state transitions.
- Free-model execution with deterministic acceptance gates.
- Packet validation at authoring time, not at execution time.
- Dependencies: 3.1, 3.2.
- Verification: invalid packet rejected at authoring; valid packet accepted by
  free model; receipt survives process restart.
- Artifacts: process-hardening-v1 manifest, receipt schema.
- Implementer: strong-model planner.
- Verifier: independent model replaying receipts.
- Failure: receipt lost on restart, or invalid packet accepted.
- Evidence: receipt persistence test, authoring-time validation test.
- Owner: Jacob (policy), strong-model planner (implementation).
- Status: PENDING.

3.4 **RunPod/Image Studio worker lane** — SUPERSEDED

- Jacob authorized this lane on 2026-07-31 and opened issue #336 the next day,
  which explicitly names it "an active, Jacob-authorized product slice".
  The authorization this outcome was waiting on has been given, so the lane no
  longer sits behind Phase 3.
- Superseded by the **Conversational Image Agent** lane below. The reviewed
  architecture (`docs/plans/image-studio-character-first-architecture-2026-07-28.md`)
  and the preserved slice on `feat/runpod-image-studio-smoke` (PR #306, draft)
  remain inputs, not authority.
- Status: SUPERSEDED by the Image Agent lane.

### Exit criteria

Phase 3 exits only when:
- Worker contract enforcement is proven across all model types.
- Builder UI and CLI projections are byte-identical for the same queries.
- Process hardening receipts survive restart and are replayable.
- (If authorized) Image Studio lane completes its acceptance contract.

---

## Authorized lane — Conversational Image Agent (issue #336)

Jacob authorized this lane directly, so it runs alongside the gates rather than
behind Phase 3. It is the priority-1 product outcome. It still depends on Gate
0.8, because nothing is verifiable while CI cannot install dependencies.

**Current verified condition (checked against code 2026-08-01, not against
prior documents):** the GenEvolve adaptation stopped halfway. The plan is built
and returned but never persisted (`gateway/image_plan.py:61`,
`gateway/routes/extended.py:606`); `/studio/generate` accepts raw form state
with no `plan_id` (`extended.py:406`), so an approved plan cannot reach
dispatch; `guidance_tags` exist only on the plan request (`extended.py:415`)
and never reach the renderer; there is no `gateway/image_agent.py`; there is no
image-session table (migrations stop at `028`); and the worker hardcodes
`text_to_image_v1` (`workers/comfy_worker/app.py:704`), so a follow-up edit
cannot bind a parent artifact as a real image input.

**User-visible outcome:** from the browser, Jacob selects a reference, types an
ordinary request, gets a real image, then says "keep his face, change his
build" and gets a genuine edit of that image — no terminal, no RunPod console.

**Owner subsystem:** `gateway/image_*`, `workers/comfy_worker/`,
`gateway/kitty-chat/src/components/ImageStudio.tsx`.

**Slices, dependencies and acceptance evidence:** `docs/mission/execution.md`
(A1–A6). A1–A3 are unit-testable anywhere; A4 is partly; A5 needs a browser;
A6 needs RunPod credentials and real GPU spend and is the slice that closes the
lane.

**Acceptance evidence:** issue #336's hard acceptance test in full — browser
proof, job/session records, parent lineage, renderer input, workflow/model
version, duration, artifact hashes, and RunPod cleanup state. Generated
substitutes, mock contact sheets and prompt-only "edits" do not count.

**Status:** NOT STARTED (A1–A6). Blocked on Gate 0.8 landing.

**Stop rule (from issue #336):** do not expand into hosted-provider adapters,
external search, LoRA training, critic loops, masking UI, or multi-character
scenes before the two-turn browser flow is real.

## Authorized lane — Trustworthy KittyBuilder

**Current verified condition:** inventory only. 27 `gateway/builder_*.py`
modules, 7 `gateway/actions/builder_*.py`, 2 route modules, 25 test files.
Which modules are on the live execution path is **not established**, and no
Builder runtime behaviour was exercised. Claims about contradictory launchers
and dead entry points are credible but UNVERIFIED.

**User-visible outcome:** every queued packet has one owner, one state, one
evidence trail and a clear next action; failed checks and merge conflicts
surface as actionable Builder state instead of manual discoveries; UI and CLI
agree on what is running, blocked, failed, completed and next.

**Owner subsystem:** `gateway/builder_*`, `gateway/routes/builder*.py`.

**Dependencies:** Gate 0.8. Then B1 (reconstruct the real execution path)
gates everything else — changing launchers before knowing which one is live is
how the duplicate-launcher problem was created.

**Acceptance evidence:** one complete mission through queue → execution →
branch/commit → PR → checks → review → merge-ready or an honestly classified
terminal failure; plus a restart mid-mission with no duplicated work or lost
state; both from a clean checkout and a real runtime, not unit tests.

**Status:** NOT STARTED. Slices at `docs/mission/execution.md` (B1–B11).

**Conversational Builder** (Jacob, 2026-08-01) is recorded as B11 and lands
after Builder state is deterministic — a conversational surface over
non-deterministic state narrates a lie fluently.

## Phase 4 — Product Deepening

Ordered by Jacob's life value. No outcome in Phase 4 may begin until Phase 3
exits. Internal order within Phase 4 is TBD — the following are named, not
sequenced.

4.1 **Chat experience**
- Reasoning engine (packet 028): complexity classifier, tier budget, execution
  receipts. Makes every chat cheaper and sharper.
- Chat recovery and continuation: thread goals, signal cards, memory visibility,
  model override.
- KX-02 chat execution experience: tool activity, approvals, artifacts, retries.

4.2 **Home and companion**
- KX-01 resume loop and shared work presentation.
- KX-05 companion layer: onboarding import, self-repairs, builder control,
  experts, chat polish.
- KX-06 proactive feed: signals and deadline cards.

4.3 **Specialists and integrations**
- Knowledge library expert retrieval (packet 008, shipped).
- Expert packs: car, body, proactive headlines (packet 018, shipped).
- GitHub connector (packet 020).
- Job search scaffold (packet 019, parked until Jacob activates).

4.4 **Image Studio deepening**
- Persistent fictional character workflow with identity consistency.
- Depends on the authorized Conversational Image Agent lane (issue #336)
  completing its two-turn browser slice first. The architecture note at
  `docs/plans/image-studio-character-first-architecture-2026-07-28.md` is an
  input to that lane, not a separate track.

4.5 **Memory and creative continuity**
- Memory taste and creative continuity (packet 023).
- Chat log idea mine (packet 024).
- Cross-project insight synthesis (packet 022, Magic Kitty).

---

## Explicitly not current work

Until Phase 2 exits, do not create another queue, scheduler, state store,
orchestrator, event system, additional Builder cockpit, memory substrate, or
broad feature lane. Do not use autonomy to compensate for dead gates or
ambiguous authority.

## Related documents

- **Disposition ledger:** `docs/DISPOSITION_LEDGER.md` — every planning file and
  its roadmap assignment.
- **Launcher contract:** `docs/reference/LAUNCHER_CONTRACT.md` — the single
  launcher interface across all modes.
- **Prevention mechanisms:** `docs/reference/PREVENTION_MECHANISMS.md` —
  enforceable gates and policies.
- **Active mission:** `docs/ACTIVE_MISSION.md` — KLF-001, currently running
  within Phase 2.
- **Mission state:** `docs/mission/` — `grounding.md` (verified current state),
  `decisions.md` (binding cross-cutting decisions), `execution.md` (ordered
  slices with branch/PR ownership), `evidence.md` (commands and verdicts),
  `failures.md` (approaches already tried). Read these before starting work;
  they exist so a fresh session resumes from evidence instead of re-deriving it.
