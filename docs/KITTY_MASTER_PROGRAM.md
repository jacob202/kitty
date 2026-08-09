# Kitty Master Program — Builder's North Star

**Date:** 2026-08-05
**Authority:** Derived synthesis of `docs/ROADMAP.md` (active authority), `docs/ROADMAP_V2.md` (V2 target plan), and the extension backlog into a single dependency-ordered program. Authority chain: ROADMAP.md (ADRs 0020, 0028–0036, Constitution) defines active priority; ROADMAP_V2.md defines V2 milestone targets; this document synthesizes both into one complete reference. It is not an independent authority. ARCHITECTURE_RATIFICATION_2026-08-06.md Decision 5 governs the relationship.
**Question answered:** If Jacob disappeared for six months, exactly what order should Builder execute everything?

This document is the merged, deduplicated, dependency-ordered program. Every piece of work from the roadmap (Gate 0 + Phases 1–4), the V2 milestones (M1–M6), the extension backlog (38 extensions ranked), the product architecture (Phases 0–6), the open issues, the active missions, the Builder initiatives, the disposition ledger's backlog, the knowledge graph's recommendations, and the continuity recovery's priorities — everything — is sequenced here exactly once.

No phase, milestone, or outcome from any source document is lost. Conflicts between numbering schemes are resolved. Duplicates are merged. Superseded work is explicitly excluded.

---

## Phase Numbering — Derived Synthesis

This P0–P8 scheme is a derived synthesis for reading convenience. The authoritative scheme for active work is ROADMAP.md (Gate/Phase/Outcome). The V2 target scheme is ROADMAP_V2.md (M1–M6). Do not use P<n> in Builder manifests, packet IDs, or the disposition ledger.

Three schemes existed: `ROADMAP.md` (Gate/Phase/Outcome), `ROADMAP_V2.md` (M1–M6), and `KITTY_PRODUCT_ARCHITECTURE.md` (Phase 0–6). This document maps all three into a single unified scheme for cross-reference convenience.

```
P0 — Repository Foundation
P1 — Trustworthy Shell
P2 — Honest State
P3 — Builder → Work
P4 — Open Every Morning
P5 — Daily Workflows
P6 — Storage Consolidation
P7 — Product Deepening
P8 — Iterate & Ship

Parallel Lane A — Conversational Image Agent
Parallel Lane B — Conversational Builder
Parallel Lane C — Job Search (parked)
```

Every prior scheme maps here:
- ROADMAP Gate 0 → P0
- ROADMAP Phase 1 → P0 outcomes 1.1–1.4 (absorbed into P0 exit criteria)
- ROADMAP Phase 2 → P1 + P2
- ROADMAP Phase 3 → P3
- ROADMAP Phase 4 → P7
- ROADMAP_V2 M1 → P1
- ROADMAP_V2 M2 → P2
- ROADMAP_V2 M3 → P3
- ROADMAP_V2 M4 → P2
- ROADMAP_V2 M5 → P6
- ROADMAP_V2 M6 → P8
- Product Architecture Phase 1 (runtime truth) → P2
- Product Architecture Phase 2 (durable chat) → implied by P1 + P2
- Product Architecture Phase 3 (artifact/evidence) → P3 + P6
- Product Architecture Phase 4 (product state) → P4 + P5
- Product Architecture Phase 5 (governed Builder) → P3
- Product Architecture Phase 6 (consolidation) → P8

---

## Operating Rules

These apply to every packet in every phase:

1. **Leave the repo working after every merge.** No "we'll total it later."
2. **Fail loud — never mask.** A packet that can't prove an outcome reports the honest blocker.
3. **Small packets, small PRs, one execution owner each.** No two lanes on the same work.
4. **Gate decides.** For autonomous packets, acceptance must be decidable by exit code. A gate that passes on unmodified tree is < failing.
5. **Evidence before claims.** Every claim of "done" requires a verified execution receipt.
6. **Life-first ordering.** Job search, benefits, education outrank code projects in every surface.
7. **No new queue, scheduler, state store, orchestrator, event system, or Builder cockpit** until P6 exits.
8. **Builder owns execution state. Gateway owns product truth. Open WebUI owns the shell.**

---

## P0 — Repository Foundation

**Objective:** Green main, enforced gates, resolved PR queue, truthful planning surface, no competing listeners, one launcher contract. The trust bedrock that every subsequent phase depends on.

### P0.1 — Keep dependency tree resolvable
**Status:** VERIFIED (CI run 1145, 2026-08-01)
**Source:** ROADMAP 0.8, Slice 0
**Kill criteria:** CI cannot run; no merge can leave the tree unresolvable.
**Deliverable:** `requirements.txt` installs clean; `tests.yml` passes.
**Evidence:** `tests.yml` run 1145 on `origin/main` @ `8c58f52` completed `success`.

### P0.2 — Enforce required checks on `main`
**Status:** BLOCKED (needs Jacob — repo admin required)
**Source:** ROADMAP 0.7, Slice 0b, GitHub issue #399
**Dependencies:** None.
**Deliverable:** Branch protection on `main` requiring `pytest`, `lint`, `typecheck`, `hygiene`, `kitty-chat`, `browser-smoke`.
**Acceptance:** PR with deliberately failing test whose merge button is blocked.
**Owner:** Jacob (repo admin). Cannot be executed by Builder.
**Kill criteria:** Any red PR mergeable on `main`.
**Implementation:** GitHub repository settings → branch protection rules → require status checks.

### P0.3 — Fix competing launcher paths (IPv4/IPv6 parity)
**Status:** PENDING
**Source:** ROADMAP 0.5, ROADMAP_V2 M1-05
**Dependencies:** P0.2 (should be enforced before launcher work).
**Deliverable:** One canonical UI bootstrap. `./kitty up` from two worktrees → second refuses to start. `./kitty down` cleans all Kitty listeners. `:3000` health probe and browser open point to same process. `./kitty status` reports source SHA, build SHA, checkout path, PID, freshness.
**Acceptance:** `curl http://127.0.0.1:4000/health` and `curl http://[::1]:4000/health` return same response from same process.
**Owner:** strong model. Verifier: independent model with browser + shell access.
**Kill criteria:** Any listener from non-canonical worktree survives `./kitty down`.
**Packet class:** `paid-author` (shell scripting + process management).

### P0.4 — Define one launcher contract
**Status:** COMPLETE as document. Implementation blocked on P0.3.
**Source:** ROADMAP 0.6
**Deliverable:** One launcher contract across `launchd` and `./kitty up` modes. Both delegate to shared bootstrap + health logic. No silent alternate path serves unknown build.
**Acceptance:** `./kitty up` and LaunchAgent use identical bootstrap path.
**Evidence:** `docs/reference/LAUNCHER_CONTRACT.md`.

### P0.5 — Repair PR automation
**Status:** COMPLETE
**Source:** ROADMAP 0.2
**Deliverable:** Labeler v5 schema, PR description comment permissions, risk-guardrails Dependabot exemption, pr-review-routing deletion.
**Evidence:** Merged via #327, #330. Dependabot waiver verified on PR #314.

### P0.6 — Reconcile open PR queue
**Status:** COMPLETE
**Source:** ROADMAP 0.3
**Deliverable:** No open non-Dependabot PR older than 7 days without activity. Disposition ledger covers every retained planning file.
**Outstanding:** 13 Dependabot PRs (#311–323) — merge individually as CI allows.

### P0.7 — Establish one truthful planning surface
**Status:** This document is the deliverable.
**Source:** ROADMAP 0.4
**Deliverable:** One canonical roadmap (this file). Complete disposition ledger. Resolved Phase 1/2 contradiction. Clean workers determine current priority from this file + runtime evidence.
**Acceptance:** No two active documents claim different next priorities.

### P0.8 — Add prevention mechanism enforcement
**Status:** DEFINED, NOT ENFORCED. Blocked on P0.2.
**Source:** ROADMAP 0.7, `docs/reference/PREVENTION_MECHANISMS.md`
**Required mechanisms once P0.2 lands:**
- Red-main freeze (CI status check on `main` push required)
- One active implementation lane (at most one non-Dependabot feature PR open at once)
- Branch freshness/conflict checks (CI gate)
- Open-PR overlap detection (CI comment when two PRs touch same files)
- Required checks: all 6 CI jobs must pass before merge
- Independent review: every PR must pass review by model other than author
- Stale-draft policy: drafts unchanged 7 days auto-closed
- Roadmap inventory coverage: every planning file in disposition ledger
- Active mission phase must exist in roadmap

### P0.9 — Design Builder Trust Model
**Status:** NOT STARTED (P0 priority per continuity recovery §7)
**Source:** Continuity recovery §7, KB signal `builder-needs-decision-must-gate-loop`, forensic B8 analysis
**Dependencies:** None.
**Scope:** This gates resolution of B8/B9/B10 and future initiatives touching the same trust-hole class. It does not gate unrelated Builder work per ADR 0021. ARCHITECTURE_RATIFICATION_2026-08-06.md Decision 9 clarifies the boundary.
**Deliverable:** `docs/plans/builder-trust-model-v1.md`. Enforce `needs_decision` as a gating state. Make the B8 class of trust-hole impossible.
**Acceptance:** No packet can be reassigned to a new worker without an explicit `needs_decision` event that survives restart. Independent review verifies the model prevents the B8 resurrection pattern.
**Owner:** Chief Architect role. Verifier: independent Reviewer.

### P0.10 — Cleanse stale Builder initiatives
**Status:** PENDING
**Source:** Continuity recovery §3, §8
**Dependencies:** P0.9 (trust model must gate the cleanup).
**Deliverable:** Retire zombie initiatives (ktf-004-*, phase1-1-recovery-proof, phase1-smoke-recovery, kx-06-proactive-feed). Cancel B8 as obsolete (only its trust lesson matters). Retire stale harness fixtures. Unblock B9/B10 after trust model is enforced.
**Acceptance:** `./kitty builder initiative doctor --json` reports 0 blocked initiatives caused by zombie tasks.

### P0 exit criteria
- CI green on `origin/main` with all 6 required jobs passing
- Branch protection enforcing required checks (Jacob)
- `./kitty down` cleans all Kitty listeners across all worktrees
- `./kitty status` reports source SHA, build SHA, checkout path, PID, freshness
- Builder Trust Model documented and enforced
- Disposition ledger contains every retained planning file
- No zombie Builder initiatives
- `./kitty context --agent` has no continuity failures

### P0 parallelizable work
- P0.3 (launcher parity) and P0.9 (trust model) are independent — run in parallel with different worktrees
- P0.10 (stale initiative cleanup) depends on P0.9
- P0.2 (branch protection) is Jacob-only, not parallelizable by Builder

---

## P1 — Trustworthy Shell

**Objective:** Open WebUI is the primary daily-driver shell. Chat is real, streaming works, persistence works, identity is honest. Jacob can use it for a full normal day.

**Dependencies:** P0 complete (repository foundation).

### P1.1 — Bootstrap clean-checkout to three listeners
**Status:** CODE MERGED (#384). Live verification pending.
**Source:** ROADMAP_V2 M1-01, M1-02
**Deliverable:** `python3 scripts/openwebui_local.py bootstrap --accept-charges` from clean checkout starts exactly one listener each for LiteLLM, Gateway, Open WebUI. Login never hits "account activation pending." `kitty-default` is the deliberate default model. Normal message streams with `[DONE]` and terminal event.
**Acceptance:** Live bootstrap on Jacob's Mac produces three listeners, no errors, one chat round-trip.
**Packet class:** `human` (requires Jacob's machine, credentials, bounded paid endpoint).
**Kill criteria:** Bootstrap fails on clean checkout. Login trap re-occurs.

### P1.2 — PYTHONPATH regression test
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M1-09
**Dependencies:** None (autonomous).
**Deliverable:** Regression test proving the shell subprocess cannot inherit `PYTHONPATH`/`PYTHONHOME`. Guards the existing `sanitized_env()` in `scripts/openwebui_tool/common.py`.
**Acceptance:** Test passes clean; test with un-sanitized env exits non-zero.
**Packet class:** `free-exec` (deterministic gate).

### P1.3 — Chats and settings persist across restart
**Status:** PENDING live verification
**Source:** ROADMAP_V2 M1 acceptance criteria #3
**Deliverable:** Chat history, agent configuration, settings survive full service restart (`./kitty down && ./kitty up`).
**Acceptance:** Browser: start chat, send message, restart services, reload browser — chat and settings identical.
**Packet class:** `human` (requires live browser verification).

### P1.4 — Make bootstrap idempotent across shutdown/restart
**Status:** PENDING
**Source:** ROADMAP_V2 M1-04
**Deliverable:** Bootstrap survives unclean shutdown. Duplicate-account behavior (already present) has smoke test and operator sign-off.
**Acceptance:** Bootstrap → kill -9 Gateway → bootstrap again → no duplicate admin row, no login trap.
**Packet class:** `paid-author` (process management + verification).

### P1.5 — Full-day pilot
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M1-03
**Deliverable:** Jacob uses Open WebUI as daily driver for one full normal day: chats, captures, model switching, tool calls, persistence across suspend/resume.
**Acceptance:** Jacob confirms. Independent verifier reproduces bootstrap + basic chat from fresh clone.
**Packet class:** `human` (Jacob's live acceptance).
**Kill criteria:** Any failure that requires leaving the shell to fix.

### P1 exit criteria
- Bootstrap from clean checkout produces 3 healthy listeners
- Chats and settings survive full restart
- PYTHONPATH/PYTHONHOME regression test passes
- Bootstrap is idempotent across unclean shutdown
- Jacob completes one full day of real use with no shell escapes
- `./kitty doctor --json` returns 0 `fail`
- Independent verifier reproduces from fresh clone

### P1 parallelizable work
- P1.1 (live bootstrap) and P1.2 (regression test) are independent
- P1.3 (persistence) and P1.4 (idempotent bootstrap) are independent
- P1.5 (full-day pilot) gates the exit — run after P1.1–P1.4

---

## P2 — Honest State

**Objective:** Every surface renders truth from the Gateway. The Console becomes the operator surface. The Capability Manifest owns runtime truth. Failures, interruptions, and receipts are honest. Nothing fabricates success.

**Dependencies:** P1 complete (shell is real — now make it honest).

### P2.1 — Console launch and route decouple from :3000
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M2-01
**Dependencies:** P1 complete.
**Deliverable:** `kitty-chat` renders as the operator/console surface. Does not probe/claim `:3000` on startup. Open WebUI owns `:3000`. Console runs on explicit operator request only.
**Acceptance:** Starting the Console does not kill or conflict with Open WebUI. Console route is distinct from chat.
**Packet class:** `paid-author` (UI routing + Next.js config change).

### P2.2 — Console reads all truth from Gateway
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M2-04
**Dependencies:** P2.1.
**Deliverable:** All Console reads go through Gateway `/state` and Builder projection endpoints. Nothing in Console hardcodes the model/provider catalog.
**Acceptance:** Console model list matches Gateway manifest. Changing a provider in Gateway updates Console without code change.
**Packet class:** `free-exec` (replace hardcoded reads with API calls; deterministic gate: count hardcoded references → 0).

### P2.3 — Stale/degraded render with reason
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M2-06
**Dependencies:** P2.2.
**Deliverable:** Console renders `available | unavailable | degraded | stale | unknown` states with a specific reason. Failed probe → `unknown` with probe error. Expired manifest → `stale` with expiry time. Never fabricates a default.
**Acceptance:** Kill Gateway → Console shows "Gateway unavailable — last seen 14:32" not a frozen last-known-good state or error page.
**Packet class:** `free-exec` (deterministic render logic; gate: snapshot test with seeded manifest states).

### P2.4 — Capability Manifest v1
**Status:** DESIGNED, NOT BUILT
**Source:** ADR 0029, Product Architecture Phase 1, ROADMAP_V2 M2 acceptance criteria
**Dependencies:** P2.2.
**Deliverable:** `CapabilityManifest` composed from live subsystem probes. Exposes: app identity, clock, project context, Builder summary, model/provider availability, tools, connections, health, approval policy. Every field carries: state, observed_at, valid_until, source, evidence_ref.
**Acceptance:** Single HTTP GET returns complete runtime truth. Expired probe → `stale` with reason. Failed probe → `unknown` with error. Full snapshot, SSE patch, and compact prompt projection all working.
**Packet class:** `paid-author` (Gateway backend — significant new code).
**Kill criteria:** Any client hardcodes model identity after manifest ships.

### P2.5 — Honest chat turn lifecycle
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M4, Product Architecture §6
**Dependencies:** P2.4 (manifest must exist before turns can bind to it).
**Deliverable:** Turn states: `draft → queued → sending → streaming → complete | interrupted | failed | stopped`. Persist before dispatch. Create attempt before contacting provider. `[DONE]` required for `complete`. Interruption preserves partial content. Retry creates new attempt, never overwrites failed one.
**Acceptance:** Kill Gateway mid-stream → message shows `interrupted` with partial content, not silently dropped. Retry creates new attempt with new route/cost, old attempt preserved.
**Packet class:** `paid-author` (Gateway backend — chat model normalization).

### P2.6 — Attachment artifacts with ingestion receipts
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M4 acceptance criteria #4, Product Architecture §6
**Dependencies:** P2.5.
**Deliverable:** Attachments become artifacts immediately on upload with hash, type, size, source. Ingestion is explicit run with receipt. Citation points to artifact-local spans. Composer may only claim understanding when ingestion receipt exists.
**Acceptance:** Upload PDF → artifact card shows "ingesting..." → completes → "ready" with citation capability. Model cannot claim understanding before ingestion completes.
**Packet class:** `paid-author` (Gateway backend + artifact registry).

### P2.7 — Evidence-backed claim enforcement
**Status:** NOT STARTED (ADR 0032 defines the rule; enforcement not built)
**Source:** ADR 0032, ROADMAP_V2 M4 acceptance criteria #5
**Dependencies:** P2.5.
**Deliverable:** Every claim of "complete/fixed/saved/sent" requires the evidence receipt for that action kind. No evidence → explicit failure state rendered, not silent success.
**Acceptance:** Generate an image without ComfyUI running → card shows "failed: ComfyUI unavailable at 127.0.0.1:8188" not a fabricated "image ready" or silent error.
**Packet class:** `paid-author` (Gateway enforcement layer across all tool actions).

### P2 exit criteria
- Console is separate from chat shell; reads all truth from Gateway
- Capability Manifest is live, versioned, and the single source of runtime truth
- Chat turns have durable states: `interrupted` ≠ `failed` ≠ `complete`
- Attachments become artifacts; model cannot claim understanding without ingestion receipt
- Every claim of "done" has its required evidence; absence = explicit failure
- Console renders `degraded`/`stale`/`unknown` with specific reasons, never defaults
- Builder state in Console matches CLI for identical queries

### P2 parallelizable work
- P2.1 (Console decouple) and P2.4 (Capability Manifest) are independent — run in parallel
- P2.2 (Console reads from Gateway) depends on P2.1
- P2.5 (chat turn lifecycle) depends on P2.4
- P2.6 (attachment artifacts) and P2.7 (evidence enforcement) depend on P2.5
- P2.3 (stale/degraded render) depends on P2.2 + P2.4
- P2.6 and P2.7 are parallel after P2.5 lands

---

## P3 — Builder → Work

**Objective:** Builder execution is visible and actionable from chat and Console. Proposals flow from chat to Builder with safe approval boundaries. Work surface shows initiative graph, run status, review, and evidence.

**Dependencies:** P2 complete (truth must exist before we build Work on top of it).

### P3.1 — Builder read projection for Console/Work
**Status:** PARTIAL — `builder_status.py` exists as bounded read-only projection
**Source:** ROADMAP_V2 M3-03, ROADMAP 3.2, ADR 0017
**Dependencies:** P2.2 (Console reads Gateway truth).
**Deliverable:** Console Work panel shows: active initiatives, packet graph, run status, review outcomes, open approvals, evidence references. All from `builder_status.py` bounded projection. No direct Builder table access.
**Acceptance:** Console and `./kitty builder` CLI show identical state for same queries. Builder unavailable → Work panel shows "Builder unavailable" not error.
**Packet class:** `free-exec` (read-only projection extension; gate: snapshot test with seeded Builder state).

### P3.2 — Chat → Builder propose/recommend
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M3-01, ROADMAP_V2 M3-09, Product Architecture §7
**Dependencies:** P3.1.
**Deliverable:** From Open WebUI chat, Action "Send to Builder" creates bounded initiative proposal with: objective, allowed paths, validation commands, budget, acceptance criteria. Gateway validates against approval policy. Builder queues. Proposal card renders with scope, budget, and expected evidence.
**Acceptance:** Jacob types "Fix the streaming smoke test" → Kitty diagnoses + plans → "Send to Builder" → packet appears in Builder queue → Builder leases worker → Work panel updates live.
**Packet class:** `paid-author` (bridge between chat and Builder queue — new code in both surfaces).
**Kill criteria:** Any Builder mutation from chat without explicit operator approval record that survives restart.

### P3.3 — Evidence projection for Work
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M3-06, Product Architecture §7
**Dependencies:** P3.1.
**Deliverable:** Execution receipts bind to initiatives, packets, runs. Work panel shows: current packet → run status → review outcome → evidence chain. Completion requires validated + independently reviewed receipts. Process exit code alone is NOT "complete."
**Acceptance:** Builder run completes but independent review finds a scope violation → Work shows "failed: rejected by Reviewer (scope violation in gateway/streaming.py:142)." Not "complete."
**Packet class:** `free-exec` (read-only evidence projection; gate: seeded receipt fixtures).

### P3.4 — Builder Infrastructure Refactor
**Status:** DESIGNED (ADR 0036), NOT BUILT
**Source:** ADR 0036, ADR 0030
**Dependencies:** P3.1 (must not break the read projection).
**Deliverable:** 27 Builder modules internally refactored. `gateway/builder/` subpackage holds execution infrastructure (task state machine, leases, attempts, events, runtime, worker session, runner, loop). Product logic stays at top level (contract, scope, ISC, reporting, operator commands, CLI, brief). `builder_adapters.py` deleted.
**Acceptance:** Full 1000+ Builder test suite passes. CLI surface unchanged. No import breakage.
**Packet class:** `paid-author` (refactoring — behavior-identical, test-gated).

### P3.5 — Work panel completion gate enforcement
**Status:** NOT STARTED
**Source:** ROADMAP_V2 M3 acceptance criteria #3
**Dependencies:** P3.1, P3.3.
**Deliverable:** Work surface enforces: no packet marked complete without validation receipt + independent review outcome. Worker assertion alone is insufficient. Exit code alone is insufficient.
**Acceptance:** Mock packet run: worker claims "done" but no review → Work shows "awaiting review" not "complete."
**Packet class:** `free-exec` (deterministic gate logic).

### P3 exit criteria
- Console Work panel and CLI show identical Builder state
- Chat → Builder proposal flow works end to end with approval gating
- Evidence receipts bind to every completed packet run
- Builder infrastructure refactored: 27 → subpackage + product logic; no `builder_adapters.py`
- No packet marked complete without validated + independently reviewed receipts
- Builder unavailable → Work surface shows "Builder unavailable" honestly

### P3 parallelizable work
- P3.1 (read projection) and P3.4 (infrastructure refactor) are independent — run in parallel
- P3.2 (chat → Builder) and P3.3 (evidence projection) depend on P3.1
- P3.5 (completion gate) depends on P3.1 + P3.3

---

## P4 — Open Every Morning

**Objective:** The S-Tier extensions from the extension backlog. Jacob opens Kitty and sees the One Thing card, not a blank chat. Morning Briefing, Resume Loop, Activity River, Builder Mission Center, Capture Inbox, and Honest State Header are all real.

**Dependencies:** P3 complete (Builder → Work must exist before Builder Mission Center. Honest State must exist before Honest State Header).

### P4.1 — One Thing card (extension #1)
**Source:** `docs/OPENWEBUI_EXTENSION_BACKLOG.md` #1
**Dependencies:** Gateway `/state/next` projection (P2 must provide the underlying truth).
**Deliverable:** Event Function on first chat of session renders one Rich UI card: "Good morning, Jacob" + single next action with context + [Let's do it] / [Not now] / [Skip]. Card also shows material changes since last visit.
**Acceptance:** Open Kitty → One Thing card appears, not blank chat. Life-first item is always first.
**Packet class:** `free-exec` (thin Event Function + Rich UI card over Gateway endpoint).
**Estimated code:** ~60 lines.

### P4.2 — Morning Briefing (extension #2)
**Source:** Extension backlog #2
**Dependencies:** Gateway `/state/brief` projection.
**Deliverable:** Event Function detects first chat of day, queries Gateway brief, injects narrative into system prompt: "Here's what happened since yesterday: ..."
**Acceptance:** First chat of day contains auto-injected briefing. Brief never fabricates content when sources are absent.
**Packet class:** `free-exec` (thin Event Function over Gateway brief projection).
**Estimated code:** ~50 lines.

### P4.3 — Honest State Header (extension #7)
**Source:** Extension backlog #7
**Dependencies:** P2.4 (Capability Manifest).
**Deliverable:** Filter injects persistent state bar into every conversation: model, connection, project, cost, Builder status. States change honestly: unavailable → error message, degraded → reason, stale → expiry time.
**Acceptance:** Every chat response shows honest state header. Changing models updates the header. Gateway down → header shows "unavailable — last seen 14:32."
**Packet class:** `free-exec` (Filter over manifest snapshot).
**Estimated code:** ~60 lines.

### P4.4 — Resume Loop (extension #3)
**Source:** Extension backlog #3
**Dependencies:** Gateway `/state/resume` projection.
**Deliverable:** Tool `kitty_resume_project` returns Rich UI card with: last active project, last action, open items, [Continue where you left off] button.
**Acceptance:** "What were we doing on X?" → card with project context, last action, open items. One tap resumes.
**Packet class:** `free-exec` (Tool + Rich UI card).
**Estimated code:** ~80 lines.

### P4.5 — Activity River (extension #4)
**Source:** Extension backlog #4
**Dependencies:** Gateway activity events (exist), P2.1 (Console decoupled).
**Deliverable:** Rich UI widget showing scrollable timeline of everything that happened: captures, Builder runs, memory writes, decisions, deadlines. Grouped by day. Each entry links to evidence.
**Acceptance:** Activity River conversation channel shows today's activity. "No activity yet today — last was yesterday at 10:42 PM" when empty. Never shows empty timeline as blank.
**Packet class:** `free-exec` (Tool + Rich UI card with polling).
**Estimated code:** ~120 lines.

### P4.6 — Builder Mission Center (extension #5)
**Source:** Extension backlog #5
**Dependencies:** P3.1 (Builder read projection).
**Deliverable:** Rich UI widget showing live Builder state: active run with worker/model/worktree/runtime, queued packets, completed today, failed with recovery options.
**Acceptance:** Builder running → Mission Center shows live state with SSE updates. Builder idle → "Builder is idle — ready for work." Builder unavailable → "Builder unavailable" not broken card.
**Packet class:** `free-exec` (Tool + Rich UI card + SSE).
**Estimated code:** ~180 lines.

### P4.7 — Capture Inbox Widget (extension #6)
**Source:** Extension backlog #6
**Dependencies:** Gateway inbox endpoint (exists).
**Deliverable:** Rich UI card showing unprocessed captures with inline actions: [Make a task], [Remember], [Dismiss]. "Process all" button. Each item resolves in place.
**Acceptance:** 3 captures in inbox → card shows all 3 → process one → 2 remaining. Empty inbox → "Inbox empty — captured thoughts appear here."
**Packet class:** `free-exec` (Tool + Rich UI card with inline actions).
**Estimated code:** ~90 lines.

### P4 exit criteria
- Opening Kitty shows One Thing card, not blank chat
- Morning Briefing injects "what happened while you were away" on first chat of day
- Honest State Header visible in every conversation; changes with live state
- Resume Loop reconstructs any project's last state
- Activity River shows everything that happened, with empty-state honesty
- Builder Mission Center shows live execution state with SSE updates
- Capture Inbox shows unprocessed captures with inline resolution

### P4 parallelizable work
- All seven P4 extensions are independent of each other (they share Gateway endpoints but don't depend on each other's Open WebUI code)
- P4.1–P4.7 can all be built in parallel by different workers
- P4.3 (Honest State Header) depends on P2.4 (Capability Manifest v1)
- P4.1–P4.2 and P4.4–P4.7 may proceed with minimal runtime truth endpoints (existing `/state/next`, `/state/brief`, `/state/resume`). Verify these endpoints are ready before starting P4 extension work. ARCHITECTURE_RATIFICATION_2026-08-06.md Decision 10 clarifies the dependency.
- P4.6 (Builder Mission Center) depends on P3.1 being complete

---

## P5 — Daily Workflows

**Objective:** A-Tier extensions from the extension backlog. Project Cockpit, Memory Browser, Deadline Radar, Quick Commands, Weekly Retrospective, Session Insights, Daily Review, Delegate to Builder, Image Studio, Cost Monitor, System Health, Signal Feed, Expert Swarm, Notifications, Voice Capture.

**Dependencies:** P4 complete (daily home must exist before daily workflows).

### P5.1 — Project Cockpit (extension #8)
**Source:** Extension backlog #8
**Est. code:** ~130 lines
**Deliverable:** Per-project dashboard: status, open items, recent activity, deadlines, [Switch to this project].

### P5.2 — Memory Browser (extension #9)
**Source:** Extension backlog #9
**Est. code:** ~150 lines
**Deliverable:** Browse/search/correct memories. Inline [Correct] and [Forget] actions. Stale memory review queue.

### P5.3 — Deadline Radar (extension #10)
**Source:** Extension backlog #10
**Est. code:** ~80 lines
**Deliverable:** Consolidated deadline view: overdue (red), this week (yellow), next week (green). Extracted from calendar, tasks, captures, memory.

### P5.4 — Quick Command Bar (extension #11)
**Source:** Extension backlog #11
**Est. code:** ~60 lines
**Deliverable:** `/project`, `/brief`, `/capture`, `/builder`, etc. Client-side command routing to Gateway endpoints. No model interpretation.

### P5.5 — Weekly Retrospective (extension #12)
**Source:** Extension backlog #12
**Est. code:** ~120 lines
**Deliverable:** Auto-generated Saturday summary: applications, Builder completions, learning, captures, deadlines. Every claim links to evidence.

### P5.6 — Session Insight Prompt (extension #13)
**Source:** Extension backlog #13
**Est. code:** ~80 lines
**Deliverable:** End-of-session Action extracts candidate insights from conversation. User confirms → saved to memory.

### P5.7 — Daily Review (extension #14)
**Source:** Extension backlog #14
**Est. code:** ~120 lines
**Deliverable:** Interactive end-of-day form: what got done, what's open, what was learned, vibe check, tomorrow's one thing. Saved to journal.

### P5.8 — Delegate to Builder (extension #15)
**Source:** Extension backlog #15
**Est. code:** ~100 lines
**Deliverable:** Action packages chat context into Builder proposal. Rich UI card shows scope, budget, expected evidence. [Send to Builder] → queues. Builder completion → notification card.

### P5.9 — Image Studio Command (extension #16)
**Source:** Extension backlog #16
**Dependencies:** Parallel Lane A (Image Agent) must be at least A4 (browser-proven two-turn flow).
**Est. code:** ~150 lines
**Deliverable:** MCP server for image generation. Chat → "Draw me X" → generation card with progress → result with [Variations] / [Edit] / [Favorites].

### P5.10 — Cost Monitor (extension #17)
**Source:** Extension backlog #17
**Est. code:** ~80 lines
**Deliverable:** Today/month cost by model. Projected monthly. Provider balances. Budget warnings.

### P5.11 — System Health Dashboard (extension #18)
**Source:** Extension backlog #18
**Est. code:** ~100 lines
**Deliverable:** Live health grid: Gateway, LiteLLM, Open WebUI, Builder, ChromaDB, mem0, MCP servers, providers, storage. Warnings for stale backups.

### P5.12 — Signal Feed (extension #19)
**Source:** Extension backlog #19
**Est. code:** ~70 lines
**Deliverable:** Web monitor matches, nudge triggers, deadline signals. Inline actions: [Read summary], [Snooze].

### P5.13 — Expert Swarm Panel (extension #20)
**Source:** Extension backlog #20
**Est. code:** ~120 lines
**Deliverable:** Action launches 8-expert review. SSE streams progress. Rich UI card shows consensus, concerns, isolated findings, cost.

### P5.14 — Notification Center (extension #21)
**Source:** Extension backlog #21
**Est. code:** ~90 lines
**Deliverable:** Consolidated "needs you" surface: Builder reviews pending, captures unprocessed, deadlines approaching, approvals needed. Appears in morning brief and on-demand.

### P5.15 — Voice Memo Capture (extension #23)
**Source:** Extension backlog #23
**Est. code:** ~70 lines
**Deliverable:** Open WebUI mobile PWA voice input → Gateway Quick Capture. Auto-extracts deadlines/tasks.

### P5 exit criteria
- All 15 A-Tier extensions shipped and browser-verified
- Project Cockpit shows per-project state matching Gateway truth
- Memory Browser supports correct/forget with 24-hour undo
- Deadline Radar catches the W-2 benefits form overdue
- Weekly Retrospective generates evidence-linked summaries
- Delegate-to-Builder flow works end-to-end with approval gating
- Image Studio generates real images through stable pipeline (after Lane A)
- Expert Swarm reviews launchable from chat

### P5 parallelizable work
- All 15 P5 extensions are mostly independent (they share Gateway endpoints but don't depend on each other)
- P5.9 (Image Studio) depends on Parallel Lane A
- P5.8 (Delegate to Builder) depends on P3.2
- P5.5 (Weekly Retrospective) depends on activity events (exist)
- Build in any order; launch as independent packets

---

## P6 — Storage Consolidation

**Objective:** Reduce mixed storage sprawl to one authoritative SQLite store plus one derived vector index. Per ADR 0030: 9 memory stores → 3; 8 subsystem SQLite DBs → 1–3 consolidated; Builder module refactor. Per ADR 0031: migration deferred until stable, but internal simplification proceeds.

**Dependencies:** P1–P5 complete (value must be proven before consolidation — consolidating before the system works consolidates bugs).

### P6.1 — Storage inventory (read-only)
**Source:** ROADMAP_V2 M5-01, ADR 0030
**Deliverable:** Count/hash of all store types per location. Every record in every store accounted for with: store type, table/file, record count, sample hashes, access patterns.
**Acceptance:** Inventory report: exact counts, no unknowns, every store classified as authoritative or derived.
**Packet class:** `free-exec` (read-only analysis).

### P6.2 — Dual-write shadow harness
**Source:** ROADMAP_V2 M5-02, Product Architecture §16
**Deliverable:** Every write to a legacy store is shadowed to the consolidated store. Shadow reads compare old and new paths. Mismatch log with exact record identification.
**Acceptance:** Zero mismatches over 7-day soak window under normal usage.
**Packet class:** `paid-author` (dual-write infrastructure + reconciliation).

### P6.3 — 9 memory stores → 3
**Source:** ADR 0030 target 1, ADR 0034
**Deliverable:** Retain SQLite (structured state), single vector store (embeddings), JSONL (capture/log). Remove mem0 and ChromaDB dependencies. Adopt one embedding backend.
**Acceptance:** Memory graph reads return identical results before/after. All existing memory tests pass. Deleted dependencies produce clean `pip install`.
**Packet class:** `paid-author` (storage migration — high risk, requires soak + rollback).
**Kill criteria:** Any memory retrieval regression. Any data loss in migration.

### P6.4 — 8 subsystem SQLite DBs → 1–3 consolidated
**Source:** ADR 0030 target 3
**Deliverable:** Each subsystem DB either consolidated into main Kitty DB or justified as independently necessary. All tables have clear ownership. No module manages its own connection outside the consolidated pool.
**Acceptance:** `./kitty doctor` green after migration. All subsystem functionality verified.
**Packet class:** `paid-author` (database migration — high risk, require backup before + restore proof after).

### P6.5 — Builder module consolidation
**Source:** ADR 0030 target 2, ADR 0036
**Dependencies:** P3.4 (Builder infrastructure refactor — does the same work; deduplicate).
**Note:** If P3.4 was completed in P3, this is verification-only. If P3.4 was deferred, execute here.
**Acceptance:** 27 modules → subpackage + product logic. No `builder_adapters.py`. 1000+ Builder tests pass.

### P6.6 — Retire legacy stores
**Source:** Product Architecture §16 (migration step 9)
**Deliverable:** After soak period with zero mismatches, remove shadow-write paths. Retire legacy store files. Document what was retired, when, with what evidence.
**Acceptance:** Store count matches target. No code path references retired stores. `./kitty doctor` green.
**Packet class:** `paid-author` (deletion — requires rollback window + Jacob approval).

### P6 exit criteria
- One authoritative SQLite store + one derived vector index + one JSONL capture log
- No subsystem manages its own SQLite connection outside the consolidated pool
- Dual-write shadow reads show 0 mismatches over 7 days
- Full restore test from backup: `./kitty doctor` produces identical pass/warn/fail counts
- All retired stores documented with evidence of non-use
- Zero functionality regression across all P5-verified surfaces

### P6 parallelizable work
- P6.1 (inventory) is prerequisite for P6.3–P6.5
- P6.3 (memory stores) and P6.4 (SQLite DBs) are independent — run in parallel
- P6.5 (Builder modules) is independent of memory/SQLite work
- P6.6 (retire legacy) gates exit — run last, after soak

---

## P7 — Product Deepening

**Objective:** B-Tier extensions from the extension backlog plus Phase 4 named outcomes from the original roadmap. Quality-of-life improvements, polish, and deepening of existing workflows.

**Dependencies:** P6 complete (consolidated foundation makes deepening safe).

### P7.1 — Rich Tool Call Display (extension #28)
**Source:** Extension backlog #28
**Est. code:** ~100 lines
**Deliverable:** Tool calls rendered as inline Rich UI cards: tool name, elapsed time, result summary. Expandable to full arguments (secrets redacted) and full result.

### P7.2 — Input Sanitizer (extension #29)
**Source:** Extension backlog #29
**Est. code:** ~60 lines
**Deliverable:** Filter detects PII (API keys, credit cards, SSNs, tokens) in user messages. Redacts before model sees. Warns user.

### P7.3 — Model Routing Card (extension #30)
**Source:** Extension backlog #30
**Est. code:** ~70 lines
**Deliverable:** Every response shows: requested route → resolved model, token count, cost, time-to-first-token. Distinguishes explicit pin from Auto classification.

### P7.4 — Recovery Mode Indicator (extension #31)
**Source:** Extension backlog #31
**Est. code:** ~80 lines
**Deliverable:** Gateway errors → user-friendly recovery cards with retry state. Provider exhaustion → "retrying automatically in 30s." Not raw JSON.

### P7.5 — Evidence Browser (extension #22)
**Source:** Extension backlog #22
**Est. code:** ~100 lines
**Deliverable:** Every Builder result → [Show Evidence] button → full execution receipt chain: diff, tests, review, merge.

### P7.6 — Knowledge Graph Browser (extension #25)
**Source:** Extension backlog #25
**Est. code:** ~180 lines
**Deliverable:** Browse connected facts as structured tree/network. "Show me how React connects to everything I know."

### P7.7 — Learning Board (extension #26)
**Source:** Extension backlog #26
**Est. code:** ~120 lines
**Deliverable:** All active learning goals with progress. Completed topics. "Tutor me on..." quick-start.

### P7.8 — Life Dashboard (extension #27)
**Source:** Extension backlog #27
**Est. code:** ~150 lines
**Deliverable:** Unified view: job search pipeline, benefits status, education progress, code projects, health (if connected). Week's focus areas.

### P7.9 — Image Feed (extension #35)
**Source:** Extension backlog #35
**Dependencies:** Parallel Lane A complete.
**Est. code:** ~100 lines
**Deliverable:** Scrollable gallery of recent images. Generations in progress. Favorited images.

### P7.10 — Search Across Everything (extension #36)
**Source:** Extension backlog #36
**Est. code:** ~100 lines
**Deliverable:** Unified search across memory, chats, captures, journal, Builder, artifacts. Results grouped by type.

### P7.11 — Session Bookmarks (extension #37)
**Source:** Extension backlog #37
**Est. code:** ~70 lines
**Deliverable:** Bookmark any message. Browse bookmarks. Jump to bookmarked moment in chat.

### P7.12 — Learning from chat (Roadmap 4.1)
**Source:** ROADMAP Phase 4.1 (reasoning engine + chat recovery)
**Deliverable:** Complexity classifier for model routing (packet 028). Chat recovery with thread goals and signal cards.
**Packet class:** `paid-author`.

### P7.13 — Specialists (Roadmap 4.3)
**Source:** ROADMAP Phase 4.3 (expert packs, GitHub connector)
**Deliverable:** GitHub connector as Open WebUI Tool/MCP (packet 020). Expert packs enhanced.

### P7.14 — Memory and creative continuity (Roadmap 4.5)
**Source:** ROADMAP Phase 4.5 (memory taste, chat log mining, cross-project insight)
**Deliverable:** Magic Kitty cross-project insight synthesis (packet 022). Chat log idea mine (packet 024).

### P7 exit criteria
- All B-Tier extensions shipped and browser-verified
- Rich tool calls, input sanitizer, model routing cards, recovery indicators all working
- Evidence for every claim is browsable from chat
- Knowledge graph is explorable
- Unified search works across all stores
- Learning board shows active topics with progress
- GitHub connector and expert packs operational

### P7 parallelizable work
- All P7 extensions are independent — build in any order
- P7.12 (reasoning engine) is the only item with architectural impact; plan first
- Roadmap-derived items (P7.12–P7.14) can run in parallel with extension items

---

## P8 — Iterate & Ship

**Objective:** Console becomes the official operator experience. Backup/restore proven. End-to-end journey runbook. Onboarding one-command. All docs aligned.

**Dependencies:** P7 complete.

### P8.1 — Backup/restore proof (extended)
**Source:** ROADMAP 2.2 (backup/restore), ROADMAP_V2 M6
**Deliverable:** Backup → destroy data/ → restore → `./kitty doctor --json` identical before/after (within tolerance). Non-destructive proof extended to destructive live test.
**Acceptance:** Before and after doctor output match exactly. Restore successful on clean checkout.
**Packet class:** `human` (destructive test requires Jacob's go-ahead).

### P8.2 — Console official release
**Source:** ROADMAP_V2 M6
**Deliverable:** Console documented as supported operator surface. Screenshots, runbook, onboarding flow. Rollback one-step to classic UI.
**Acceptance:** New user can install Kitty from one command (`bootstrap`), open Open WebUI for chat, open Console for configuration/diagnostics.
**Packet class:** `paid-author` (documentation + polish + release).

### P8.3 — End-to-end journey runbook
**Source:** ROADMAP_V2 M6, ROADMAP 2.3 (move-in bar)
**Deliverable:** Documented runbook: select real life project → resume truthful state → one concrete next move → deliver to phone. Move-in bar's 5 criteria verified.
**Acceptance:** Jacob confirms all 5 move-in criteria on primary devices. Runbook is reproducible by any strong model.
**Packet class:** `human` (requires Jacob's live verification).

### P8.4 — Doc alignment
**Source:** KNOWLEDGE_GRAPH.md recommended actions, Product Architecture Phase 6
**Deliverable:** AUTHORITY_MAP.md includes CONSTITUTION.md and this document. DISPOSITION_LEDGER.md updated to this program's phase scheme. BLUEPRINT.md updated to acknowledge ADRs 0027–0036. Orphan initiatives accounted for. Stale superseded docs marked.
**Acceptance:** No document in the authority set is unmapped. No initiative is un-dispositioned. Phase scheme is consistent across all documents.
**Packet class:** `free-exec` (documentation updates — deterministic: count unmapped docs → 0).

### P8.5 — Complexity budget audit
**Source:** Constitution VII.4
**Deliverable:** Count modules, stores, UI surfaces, redundant code paths. Verify direction is down from P0 baseline. Any violation → deferral is explicit.
**Acceptance:** Module count < P0 module count. Store count = target (from P6). Redundant code paths = 0.
**Packet class:** `free-exec` (counting — deterministic gate).

### P8 exit criteria
- Backup/restore proven destructive: delete data/ → restore → identical doctor output
- Console is documented, screenshot-backed, one-command install
- End-to-end journey runbook: real project → next move → phone delivery
- Move-in bar: all 5 criteria confirmed by Jacob
- All docs aligned to this program. No duplicated phase schemes. No orphan initiatives.
- Complexity budget: direction is down.

### P8 parallelizable work
- P8.4 (doc alignment) and P8.5 (complexity audit) are independent
- P8.1 (backup/restore), P8.2 (Console release), and P8.3 (journey runbook) are largely independent

---

## Parallel Lanes

These run alongside the main phases. Each has its own stop rule, dependencies, and exit criteria. They do not block the main phase progression.

### Parallel Lane A — Conversational Image Agent
**Source:** issue #336, ROADMAP authorized lane, mission execution slices A1–A6
**Status:** NOT STARTED (A1–A6). A1 partially verified.
**Dependencies:** P0 complete. Can proceed in parallel with P1+.
**Stop rule:** Do not expand into hosted providers, LoRA training, multi-character scenes, critic loops, or masking before the two-turn browser flow is real.
**Slices:**
- A1: Durable image-agent sessions (VERIFIED against A1 acceptance)
- A2: Plan persistence (NOT STARTED — `image_plan.py:61` never persists the plan; `guidance_tags` don't reach renderer)
- A3: Dispatch binding (NOT STARTED — `/studio/generate` accepts raw form state with no `plan_id`)
- A4: Character-first conversational turn (NOT STARTED — "keep his face, change his build" → real edit)
- A5: Browser verification (NOT STARTED)
- A6: RunPod live pipeline (NOT STARTED — requires credentials + real GPU spend)
**Acceptance:** From browser: select reference → type request → get real image → "keep his face, change his build" → genuine edit. No terminal, no RunPod console.
**Packet class:** A1–A3: `free-exec` (unit-testable). A4: `paid-author` (backend integration). A5: `human` (browser). A6: `human` (credentials + spend).
**Exit:** A6 runway evidence: browser proof, job/session records, parent lineage, renderer input, workflow/model version, duration, artifact hashes, RunPod cleanup state.

### Parallel Lane B — Conversational Builder
**Source:** ROADMAP authorized lane (B11), ROADMAP_V2 "trustworthy kittybuilder" initiative
**Status:** BLOCKED. B2–B7 done. B8 blocked (trust hole). B9/B10 queued behind B8. B11 not started.
**Dependencies:** P0.9 (Builder Trust Model) must land first. Then B8 is obsoleted. Then B9/B10 unblocked. Then B11.
**Slices:**
- B1: Reconstruct real execution path (PENDING)
- B2–B7: Merged (projection, PR lifecycle, breadcrumb durability, review-binding, stale-state hardening, repair)
- B8: Clean-checkout trivia (BLOCKED — trust hole; will be obsoleted by P0.9)
- B9: Restart recovery (QUEUED behind B8)
- B10: UI/CLI agreement (QUEUED behind B8)
- B11: Conversational Builder (NOT STARTED — "conversational surface over deterministic state")
**Stop rule:** B11 lands only after Builder state is deterministic — a conversational surface over non-deterministic state narrates a lie fluently.
**Exit:** One complete mission through queue → execution → branch/commit → PR → checks → review → merge-ready or honest terminal failure; plus restart mid-mission with no duplicated work or lost state. B11 provides chat-native Builder control.

### Parallel Lane C — Job Search
**Source:** packet 019, extension backlog
**Status:** PARKED by Jacob until he activates.
**Dependencies:** P4+ (job search project cockpit should exist first).
**Deliverable:** Job search scaffold: application tracker, outreach log, interview prep, status pipeline.
**Activation:** Jacob explicitly unpacks this. Do not start autonomously.

---

## Deferred Work — Explicitly Not Current

Work that is valuable but explicitly deferred past P8. Preserved here so nothing is lost.

| Item | Source | Reason deferred |
|---|---|---|
| Migration to Open Brain/Ringer/Open Engine | ADR 0031 | Projects unproven; maturity unknown. Deferred until stable API + proven maturity + Apple Silicon compatibility. |
| RunPod/Image Studio expansion beyond A6 | ROADMAP 3.4 (superseded), issue #336 stop rule | Hosted providers, LoRA, multi-character scenes, critic loops — deferred past two-turn browser flow. |
| New feature lanes (expanded connectors, integrations) | ROADMAP "explicitly not current work" rule | No new lane until P8 exits. |
| Phase 4.4 Image Studio deepening (beyond Lane A) | ROADMAP Phase 4.4 | Persistent fictional character workflow — depends on Lane A completing. |
| Health MCP, Finance MCP, Home Automation MCP | Extension backlog Tiers 2–3, product plan Appendix | Privacy evaluation needed. Deferred. |
| Calendar integration, Email assistant, Todoist/Things/Linear sync | Product plan Tier 3 plugins | Risk of second source of truth for Kitty-owned concerns. |
| Browser MCP, Notes MCP, Notion/Obsidian MCP | Product plan Tier 2 MCP servers | Deferred until daily workflows (P5) prove which integrations earn their keep. |
| Image Lab dedicated surface (beyond Image Feed) | ROADMAP Phase 4.4 | Depends on Lane A + P5.9 + P7.9. |

---

## Definitively Dead Work

Explicitly not recoverable. Listed so no worker resurrects it.

| Item | Reason |
|---|---|
| B8 clean-checkout trivia as runnable packet | Trust hole; only its trust lesson matters. Superseded by P0.9 (Builder Trust Model). |
| ktf-004 daylight proof manifests (4 manifests) | Superseded by P1–P3 builder-work proof. Harness fixtures proven stale. |
| phase1-1-recovery-proof initiative (RP-01–07) | Harness broke; recovery proven in live system. Retired. |
| phase1-smoke-recovery initiative | Consumed. Retired. |
| kx-06-proactive-feed initiative | Idea resurrected in P4/P5 extensions. Zombie initiative retired. |
| MemPalace integration | Retired via ADR 0034. Harvested policy prose only. |
| Prefect/Temporal/Hatchet/Dagster migration | Rejected via ADR 0036 and architecture correction. KittyBuilder stays. |
| GenEvolve adaptation (stopped halfway) | Absorbed into Lane A (Conversational Image Agent). Old code retired. |
| reasoning-backend-v1 initiative | Idea harvested into P7.12. Failed/paused initiative retired. |
| Duplicate packets 021/023, 022/024 | Old numbers retired. Only 023/024 carry forward. |
| Fal, Telegram, Honcho mirror, speculative expert-pack expansion | Dead or disabled. Removed from UI. BLUEPRINT §6. |

---

## Critical Path

The longest chain of dependencies from now to done:

```
P0.2 (Jacob: branch protection)
  → P0.3 (launcher parity)
    → P0.9 (trust model)
      → P1 (trustworthy shell)
        → P2.4 (capability manifest)
          → P2.5 (honest chat turns)
            → P3 (Builder → Work)
              → P4 (Open Every Morning)
                → P5 (Daily Workflows)
                  → P6 (Storage Consolidation)
                    → P7 (Product Deepening)
                      → P8 (Iterate & Ship)
```

P0.2 is the single choke point — it requires Jacob's repo admin action. Everything downstream depends on it. The critical path is roughly P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8.

Parallel work (Lane A, Lane B, and independent packets within each phase) can shorten wall-clock time but not the dependency chain.

---

## Builder Execution Order

When Builder selects the next eligible packet, it evaluates in this priority:

1. **P0 unblocked:** P0.3 (launcher), P0.9 (trust model), P0.10 (stale cleanup) — all autonomous or paid-author packets that can proceed without Jacob. P0.2 is gated on Jacob.
2. **Parallel Lane A eligible slices:** A1 (verified), A2 (plan persistence), A3 (dispatch binding) — all free-exec or paid-author.
3. **P1 autonomous:** P1.2 (PYTHONPATH regression test) — free-exec, can run immediately.
4. **Phase progression:** P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8, always selecting the highest-priority eligible packet.
5. **Within each phase:** build independent packets in parallel where worktrees and allowed paths don't conflict.
6. **Paused/exhausted packet:** does not block unrelated eligible work (ADR 0021).
7. **Every completed packet:** run through independent review before merge.

---

## Success Criteria — The Destination

Kitty is complete when:

1. **Jacob opens it every morning** to the One Thing card, not a blank chat.
2. **Every surface shows honest runtime truth** from the Capability Manifest. No client hardcodes capability.
3. **Chat is a durable work surface** — messages persist before dispatch, interruptions are preserved, retries are new attempts, attachments are artifacts with ingestion receipts.
4. **Builder executes autonomously** — proposals flow from chat, packets run in isolated worktrees, independent review verifies, merge is policy-gated. Work surface shows live evidence.
5. **The Resume Loop works** — open Kitty, see what changed, resume exactly where you left off, next action is always one tap away.
6. **Life-first ordering is enforced** — job search, benefits, education outrank code projects in every surface.
7. **Evidence backs every claim** — no fabricated success, no silent fallbacks, no `$0` when cost is unknown.
8. **Storage is consolidated** — one authoritative store + one derived index. No duplicate truth paths.
9. **The Console is the operator surface** — configuration, Builder state, diagnostics, approvals. Not a competing chat shell.
10. **The shell is replaceable** — Open WebUI is the daily driver. If it changes license or is abandoned, Gateway contracts survive. Replacement takes a weekend, not a rewrite.

---

## Authority and Supersession

This document:
- **Is:** A derived synthesis of `docs/ROADMAP.md` (active authority, per ADR 0020), `docs/ROADMAP_V2.md` (V2 target plan), and the extension backlog into a single dependency-ordered program. ARCHITECTURE_RATIFICATION_2026-08-06.md Decision 5 governs the relationship.
- **Implements:** Constitution v1, all ratified ADRs 0001–0036, KITTY_PRODUCT_ARCHITECTURE.md, OPENWEBUI_PRODUCT_PLAN.md, OPENWEBUI_EXTENSION_BACKLOG.md, CONTINUITY_RECOVERY.md, KNOWLEDGE_GRAPH.md, BUILDER_ORGANIZATION.md, BLUEPRINT.md, ALIGNMENT_MAP.md, all active missions, and all Builder initiatives.
- **Is superseded by:** A future ADR that explicitly revises the program. Routine amendments may be made by updating this document with a dated revision note.
- **Does not override:** The Constitution, any ratified ADR, or live Gateway/Builder/runtime evidence. If this document and the running system disagree, the running system wins — then this document must be updated.
- **Phase numbering:** This document's P0–P8 scheme is a derived synthesis for reading convenience. The authoritative scheme for active work is ROADMAP.md (Gate/Phase/Outcome). The V2 target scheme is ROADMAP_V2.md (M1–M6). Do not use P<n> in Builder manifests, packet IDs, or the disposition ledger. All references to ROADMAP.md Gate/Phase/Outcome, ROADMAP_V2 M1–M6, or Product Architecture Phase 0–6 are mapped in the Phase Numbering section above.
- **Builder's role:** Builder executes packets within the phase order and dependency constraints defined here. It does not re-prioritize, re-interpret phases, or autonomously select work from P5 when P1 is incomplete. The proactive execution rule (ADR 0021) applies within the current phase — Builder selects the highest-priority eligible packet within the active phase, not across phases.

---

## Ratification

This Master Program consolidates every planning artifact in the repository as of 2026-08-05:

| Source | Document count | What was merged |
|---|---|---|
| ROADMAP.md | 1 | Gates 0–4, Phases 1–4, authorized lanes, exit criteria |
| ROADMAP_V2.md | 1 | M1–M6 milestones, 10-packet catalog, V2 governance |
| CONSTITUTION.md | 1 | 7 Articles, 30+ principles, ownership boundaries |
| KITTY_PRODUCT_ARCHITECTURE.md | 1 | 4-spine architecture, Phases 0–6, approval classes |
| OPENWEBUI_PRODUCT_PLAN.md | 1 | Extension model, MVPs, MCP servers, product rules |
| OPENWEBUI_EXTENSION_BACKLOG.md | 1 | 38 ranked extensions, S/A/B tiers, build order |
| ADR 0001–0036 | 36 | All ratified decisions, supersession chains, amendments |
| BLUEPRINT.md | 1 | Product direction, UX direction, honesty ledger |
| ALIGNMENT_MAP.md | 1 | Authority order, architectural layers, delivery phases |
| CONTINUITY_RECOVERY.md | 1 | Unfinished work, zombie initiatives, top recommendations |
| KNOWLEDGE_GRAPH.md | 1 | Structural problems, missing links, continuity rules |
| BUILDER_ORGANIZATION.md | 1 | 16 roles, coordination model, artifact ownership |
| DISPOSITION_LEDGER.md | 1 | 136+ planning files, disposition classes |
| Active missions | 2 | KLF-001, Image Agent Lane |
| Open issues (#) | 10+ | #270, #336, #346, #349, #352–#354, #389–#390, #399 |
| Builder initiatives (45) | 45 JSON/manifests | 28 distinct IDs, 7 active, 17 backlog, 8 superseded, 1 rejected |
| Research (19) | 19 docs | All investigations, findings, evidence |
| Plans (12) | 12 docs | All planned work, absorbed or scheduled |
| Mission docs (6) | 6 docs | Execution slices, decisions, evidence, failures, grounding |

Total sources synthesized: **150+ documents**.

No important decision, backlog item, deferred idea, or dead-work boundary was lost. Every item has exactly one disposition in this program.
