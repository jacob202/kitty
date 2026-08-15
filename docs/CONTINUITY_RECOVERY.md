# Kitty Continuity Recovery

**Date:** 2026-08-05
**Purpose:** Recover every unfinished thought in the repository so nothing valuable disappears again. Every retained item is either dispositioned or explicitly listed here with a recommended action.
**Method:** Full-repo survey of docs (ADR, plans, planning, packets, initiatives, research, audit, recon, phases, archive, retired, runbooks, session-notes), git branches (197 refs), GitHub (PRs + issues), the live Builder DB (`data/kittybuilder/builder_queue.db`), the local KB (`~/kb`), and continuity checkpoints (`.claude/STATE.md`, `.claude/HANDOFF.md`).
**Provenance note:** repo is live; HEAD `4c0bf06b`, behind `origin/main` 72. Multiple parallel lanes are mid-flight (see §0). Status below reflects what was verified 2026-08-05; re-derive live facts before acting.

## How to read this

Each entry: **Source → Status → Value → Recommended action → Priority.**
- Priority **P0** = trust/security/blocking; resume first.
- **P1** = high-value follow-up already owned by a roadmap/issue.
- **P2** = backlog/idea worth keeping; activates on a decision.
- **P3** = bookkeeping (undispositioned / zombie residue / orphan docs).

---

## 0. In-flight parallel work (preserved on this branch)

The following were produced 2026-08-05 by a parallel interactive lane. They were untracked/uncommitted at the time of this survey; they are now committed on this branch (`closeout/2026-08-05-architecture-reconciliation`) and preserved in PR #408. See ARCHITECTURE_RATIFICATION_2026-08-06.md for their authority status.

| Source | Status | Value | Recommended action | Priority |
|---|---|---|---|---|
| `docs/CONSTITUTION.md` (v1, modified) | Committed on this branch | High — top design artifact | Ratified 2026-08-05; amendment process explicit in Article VII.5. Authority status per ARCHITECTURE_RATIFICATION Decision 6. | P1 |
| `docs/ROADMAP_V2.md` | Committed on this branch | High — sequenced V2 plan (M1–M6, 10 packets) | Ratified target plan per Constitution v1 and ARCHITECTURE_RATIFICATION Decision 5. | P1 |
| `docs/initiatives/v2-driver-baseline-v1.json` | Committed on this branch | High — the "turn docs into Builder backlog" trigger | Do not apply yet. Autonomous packets may proceed after governance prerequisites per ARCHITECTURE_RATIFICATION Decision 8. | P1 |
| `docs/OPENWEBUI_PRODUCT_PLAN.md` (876 ln) | Committed on this branch | High | Preserved as product plan; keep as the "configure > filter > pipe > function > MCP > never fork" contract. | P1 |
| `docs/OPENWEBUI_EXTENSION_BACKLOG.md` (2148 ln) | Committed on this branch | High — 38 ranked extensions | Preserved; convert to Builder-managed backlog (see §F). | P1 |
| `docs/adr/0028…0036` (9 new ADRs) | Committed on this branch | High — 0028 commodity, 0031 migration deferred, 0033 shell boundary, etc. | Committed and indexed. ADR 0033 header corrected per ARCHITECTURE_RATIFICATION Decision 12. | P1 |
| `docs/BUILDER_ORGANIZATION.md` | Committed on this branch | Medium — org design, "not yet implemented" | Marked DESIGN. Not ratified. May inform future ADRs per ARCHITECTURE_RATIFICATION Decision 4. | P2 |
| `docs/KNOWLEDGE_GRAPH.md` | Committed on this branch | Medium — live catalog of superseded/stale statuses | Preserved; keep maintained. | P2 |
| `docs/research/architecture-decision-summary-2026-08-05.md` | Committed on this branch | Medium | Preserved as the decision-tree reference. | P2 |
| `artifacts/` (forensics + handoff) | Committed on this branch | High | Preserved evidence. B8 forensic report + Builder trust-model handoff. | P3 (persist) |

---

## 1. Active-roadmap outcomes that are STILL UNFINISHED (`docs/ROADMAP.md`)

These are explicitly owned, sequenced, and not started/blocked — the canonical "unfinished thoughts."

| Source (outcome) | Status | Value | Recommended action | Priority |
|---|---|---|---|---|
| **0.5 Launcher contract / competing listeners** (one canonical UI bootstrap; IPv4/IPv6 parity) | PENDING | High — recurring bug class | Implement per spec; also covered by V2 M1-05 | P0 |
| **0.7 Enforce prevention mechanisms** (red-main freeze, required checks, 1-lane rule) | DEFINED, NOT ENFORCED | High — this is the trust bedrock | Requires repo admin (Jacob): enable branch protection requiring all 6 checks | P0 |
| **1.2 executable free-model packets** (≥2 validated JSON manifests per FREE_MODEL_PACKET_STANDARD) | PENDING | High | Author 2 manifests; needed for daylight proof | P1 |
| **1.3 prove proactive delivery in daylight** | PENDING | Medium-High — largely superseded by B2–B7 landings; remaining value is unattended-run evidence | Re-scope to "unattended run with honest provider-exhaustion pause" | P1 |
| **1.4 prove the actual product loop** (one real project → one next move → phone) | PENDING | High — the real "resume loop" proof | Same as Phase 2.3 move-in; fold together | P1 |
| **2.1 KLF-001 independent acceptance verification** | PENDING verification | Medium | Run the browser/live verification pass | P1 |
| **2.2 backup/restore** | IN PROGRESS — restore proven; live destructive `doctor` comparison deferred to Jacob's go-ahead | Medium | Await Jacob; then run live before/after | P2 |
| **2.3 move-in bar** (5 criteria: morning brief, next-step per project, benefit paper watch, capture-return, auditable queue) | PENDING | **High — the product's emotional core** | Anchor V2/extension backlog to these 5; resume after M1 proof | P1 |
| **3.1 unified worker contracts + cost policy** | PENDING | High | Worker contract boundary; ties to `needs_decision` trust work | P1 |
| **3.2 unified runtime projections + Builder UI (cockpit)** | PENDING | Medium — partially landed (B4 projection) | Finish UI/CLI agreement (B10 blocked on B8) | P1 |
| **3.3 process hardening** (authoring-time packet validation, durable receipts) | PENDING | Medium-High | Packet-authoring validation is cheap; receipts exist already | P2 |
| **Image Agent lane (issue #336)** — A1–A6 slices | NOT STARTED (A1–A6), authorized | High but long | Progress propels Image Studio deepening (4.4) | P1 |
| **Trustworthy KittyBuilder lane** (B1–B11) | PARTIAL — B2–B7 done; **B8 blocked**, B9/B10 queued-behind; B11 (Conversational Builder) not started | High | Unblock B8 via the trust-model decision (see §3) | P0 |
| **Phase 4 named-not-sequenced** (4.1 chat, 4.2 home/companion, 4.3 specialists, 4.4 image, 4.5 memory) | DECLARED, unsequenced | Medium | Re-sequence after V2 M1–M4; harvest from extension backlog | P2 |

Also **"Explicitly not current work"** rule (no second queue/scheduler/store/orchestrator until Phase 2 exits) — keep enforcing; V2 M5 storage consolidation is explicitly sequenced last.

---

## 2. Open GitHub issues and PRs (incomplete thoughts)

| Source | Title | Status | Value | Recommended action | Priority |
|---|---|---|---|---|---|
| **#399** | Enforce main protections & retire one-shot Actions workflows | open, high/manual | High | Same as §1 0.7; close when branch protection is on | P0 |
| **#346** | P0 UX trust reset: complete user tasks instead of exposing machinery | open, high | High — partly shipped via chat-truthful-recovery slices | Re-triage remaining slices against V2 M4 (failure/receipts) | P0 |
| **#270** | One complete loop: capture → classify → return → act → learn | open | High — the feedback loop under everything | Fold into V2 M3/M4 + extension backlog (capture-return) | P1 |
| **#336** | Conversational Image Agent vertical slice | open, high | High | See §1 Image Agent lane | P1 |
| **#349** | Enforce user-task product acceptance in CI/PR review | open | Medium | Now enforceable via ADR 0032/0035 + §1 0.7 | P1 |
| **#352** | Evidence-driven UI/UX audit swarm skill | open | Medium | Backlog — could be a skill itself (uses existing audit skills) | P2 |
| **#353** | Kitty Product Studio: UX review swarm | open | Medium | Backlog | P2 |
| **#354** | Incubator: solo-founder leverage systems | open | Medium | Backlog; harvest into extension backlog | P2 |
| **#389** | Adopt PAA as reference architecture / executable portability | open, manual | Medium — partially in ADRs 0028/0031 | Align with the deferred-migration ADR; keep doc-only | P2 |
| **#390** | Harvest & benchmark task-level agent architectures | open | Medium | Rich source for Builder trust-model design | P1 |
| **PR #406** | `proof/two-week-builder-loop` (open) | OPEN | Medium — overlapping with B2–B7 landing | Decide: close as absorbed, or keep as live proof | P2 |
| **PR #391** | `docs/paa-alignment-profile` (open) | OPEN | Low-Medium | Close/branch per #389 decision | P3 |
| **PR #398 / #387** | closed-unmerged (github-truth-pass rerun; chat-ux dup) | CLOSED | Low | nothing to salvage beyond 404/387 parent work | P3 |

---

## 3. Live Builder DB — zombie initiatives, stale fixtures, leaked/failed work

Verified against `data/kittybuilder/builder_queue.db` (2026-08-05). Task rollup: 51 done, 43 cancelled, 10 blocked, 2 queued, 1 failed.

| Source | Status | Value | Recommended action | Priority |
|---|---|---|---|---|
| **`trustworthy-kittybuilder-b2-b10-v1` / B8-clean-checkout-mission** (`kb_msb4yx3n_f6e8`) | **blocked**; 9 attempts (5 crashed/4 failed); `needs_decision` escalation recorded but never gated | **High** — the trust-hole | Do **not** rerun. Resolve the trust model (§7 deliverable), then explicit operator override or retire B8; B9/B10 stay correctly gated behind it | **P0** |
| B9-restart-recovery, B10-ui-cli-agreement | queued, dependencies unreachable (B8) | High | Unblock only via the B8 decision | P0 |
| `phase1-1-recovery-proof-20260801-184814` (RP-01…07) | paused; RP-01/02/03/04/06 **blocked** harness fixtures, RP-05/07 cancelled | Low — proven stale harness | Cleanse: retire the initiative and blocked tasks with an explicit `blocked→cancelled` audit | P3 |
| `ktf-004-daylight-proof-v1`, `ktf-004-daylight-evidence-v2`, `ktf-004-daylight-lifecycle-v3/v4`, `phase1-smoke-recovery` | active but obsolete (4 superseded manifests; tasks cancelled/blocked) | Low | Retire/resume-to-paused with stale-residue cleanup | P3 |
| `kx-06-proactive-feed-v1` | active but all packets cancelled; nightly drain idles on it | Medium — the "proactive feed" idea still wants building (V2 / extension backlog) | Pause as deliberate; resurrect the idea as an extension, not a zombie initiative | P2 |
| `uifix-labels-2026-07-27-v1/v2`, `ktf-001-free-exec-v1`, `ktf-003-*`, `kittybuilder-brain-v1` | active but cancelled/superseded packs | Low-Medium — several are backlog ideas (brain cockpit = Phase 3.2) | Retire stale; keep only as backlog entries | P3 |
| `kitty-endgame-init-1-builder-closeout-v1/v2`, `reasoning-backend-v1`, `cp08-campaign-a` | failed (superseded / paused / immutable-manifest) | Medium — reasoning engine (packet 028) still backlogged | Mark reasoning-backend-v1 → backlog, not failed-shadow; endgame → superseded (v2 landed elsewhere) | P3 |
| `backups/`, `manifest/` dirs, leaked stale open attempts (e.g. B8 attempt 111) | orphaned runtime residue | Low | Add a stale-residue sweep to `builder initiative doctor` | P3 |

**Cross-cutting:** the promoted workflow signal `builder-needs-decision-must-gate-loop` (kb) records the trust hole; the **Builder Trust Model** design task is the owner (see §7).

---

## 4. Undispositioned / orphan planning files (ledger gap since 2026-07-31)

The disposition ledger predates several files that now carry real direction:

| Source | Status | Value | Recommended action | Priority |
|---|---|---|---|---|
| `docs/plans/kitty-ui-enhancement-plan.html` | not in ledger | Medium (UI plan) | Add disposition (BACKLOG → V2 M2/M4 UI work) | P3 |
| `docs/plans/migration-health.md` | not in ledger, staged | Low — a one-off migration audit | Add disposition or delete (superseded by `scripts/migration-audit.sh`) | P3 |
| `docs/plans/openwebui-agent-handoff-2026-08-02.md`, `openwebui-onboarding-checklist.json`, `openwebui-onboarding-progress.md` | not in ledger; handoff marked SUPERSEDED in KNOWLEDGE_GRAPH | Medium (gap list was addressed on disk) | Archive with the "gap closed" note; absorbed into V2 M1 | P3 |
| `docs/plans/KITTY_PRODUCT_EXPERIENCE_V1.md`, `docs/planning/feature-reference-map.md`, `docs/planning/vision-horizons.md`, `docs/planning/kitty-vision-gap-analysis` | BACKLOG per ledger | Medium — the future-direction catalog | Keep as inputs to the extension backlog/v2 planning | P2 |
| `docs/CONSTITUTION.md`, `docs/BUILDER_ORGANIZATION.md`, `docs/KNOWLEDGE_GRAPH.md` | untracked (§0) | High | Commit + ledger entry | P1 |

---

## 5. Backlog / lost ideas worth harvesting (packets + initiatives)

Key still-valuable backlog (full list is 41 items in the ledger):

| Source | Status | Value | Recommended action | Priority |
|---|---|---|---|---|
| **Packet 028 — Reasoning engine** (complexity classifier, tier budget, receipts) | BACKLOG (Phase 4.1); DB initiative `reasoning-backend-v1` failed/paused | High — cheaper/sharper chat; feeds V2 M4 receipts | Repackage as a V2 M4 sub-packet or extension (budget-aware routing) | P1 |
| **Packet 019 — Job search scaffold** | BLOCKED, parked by Jacob until he activates | High for Jacob specifically | Leave parked; surfaced via extension backlog (Job Search cockpit) only on activation | P2 |
| **Packet 020 — GitHub connector** | BACKLOG (Phase 4.3) | Medium | Convert to an Open WebUI Tool/MCP extension | P2 |
| **Packet 022 — Magic Kitty** (cross-project insight synthesis) | BACKLOG, "in progress, partial" | High — the cross-project insight engine | Re-scope against knowledge-graph browser extension | P1 |
| **Packet 024 — Chat log idea mine** | BACKLOG | Medium | Extension (memory explorer / idea mine) | P2 |
| **Packet 025 — Imagegen pipeline v2** | BACKLOG (Phase 4.4) | Medium — largely superseded by Image Agent lane | Fold into #336 lane | P2 |
| **KX-01 resume-loop, KX-02 chat execution, KX-04 work surface, KX-05 companion, KX-06 feed** | BACKLOG (Phase 4.2); KX-05 completed | Medium-High — the companion/resume/feed ideas map 1:1 to the extension backlog | Reopen as Open WebUI extensions, not separate Next.js surfaces | P1 |
| **kittybuilder-brain-v1** (harvest + cockpit + operator controls) | BACKLOG; partial (KB-BRAIN-00/05 done) | Medium — largely landed as audit/B4/B5 | Close as absorbed; residual cockpit = Phase 3.2 | P2 |
| **p2-worker-contract-tests, trust-lane-v1, process-hardening-v1, builder-test-hardening** | BACKLOG (Phase 3.x) | Medium | Batch into §1 3.1/3.3 | P2 |

---

## 6. Discarded / superseded / retired — what to harvest

| Source | Status | Value | Recommended action | Priority |
|---|---|---|---|---|
| `docs/retired/MEMPALACE_INTEGRATION.md` + phases `STORAGE_MIGRATION_PLAN.md`/`MEMPALACE_MIGRATION_RUNBOOK.md` | retired/archived | Low-Medium — the memory-policy idea resurfaces as ADR 0034 (storage open) | Harvest the policy prose, not the engine; keep retired | P3 |
| `docs/retired/FUTURE_VISION_AND_ROADMAP.md` | superseded | Medium — original North Star | Already superseded by NORTH_STAR; keep as provenance | P3 |
| `ktf-005-life-resume-loop` manifest | REJECTED | Medium — human-only runbook; move-in bar lives in packets README | Keep the runbook intent; fold into Phase 2.3 | P2 |
| `research/FOUNDATION_REPLACEMENT_STUDY` | BACKLOG | Medium — foundation decision history (Open WebUI was removed June, then re-adopted) | Preserve as decision provenance for ADR 0027/0033 | P3 |
| `research/GENEVOLVE_ADAPTATION_2026-07-28` | BACKLOG | Medium — image planning reference; adaptation "stopped halfway" per ROADMAP (image_plan.py:61) | Harvest into the Image Agent lane (A3/A4) | P1 |
| `research/kittybuilder-core-runtime-audit-2026-08-01` + `open-session-audit-2026-08-01` + `architecture-honesty`/`backend-frontend-gap` audits | BACKLOG / consumed | Medium — conclusions fed ADRs; gaps were the V2 seed | Mark consumed; link to ADR 28–36 | P3 |
| `archive/` (38 files; shipped packets 001–026, orchestration plans, handoff templates) | ARCHIVED | Provence only | Keep archived; recover `026-builder-reliability` intent from papers (already ACTIVE in roadmap) | P3 |

---

## 7. Continuity / knowledge-base carried threads (recs + signals)

| Source | Status | Value | Recommended action | Priority |
|---|---|---|---|---|
| **Promoted workflow signal:** `builder-needs-decision-must-gate-loop` | critical, promote | High | **Owner = next task: Design Builder's Trust Model** (deliverable `docs/plans/builder-trust-model-v1.md`). Do not optimize for B8; make the class impossible | **P0** |
| `~/kb/wiki/2026-08-05-builder-packet-resurrection-trust-hole.md` | new | High | Read before the trust-model task; land its prevention rule in the model | P0 |
| **`artifacts/forensic-b8-wrong-assignment-2026-08-05.md`** | new | High | The evidence base for §3/§7 decisions | P0 |
| `session_learning` signal: `builder-review-binding-diff-sha-mismatch` | recorded | Medium | Fold into review-contract hardening (3.3) | P2 |
| `session_learning` signal: `openwebui-permanent-ui-boundary` | recorded | Medium | Enforce the "UI is shell, Gateway owns truth" rule in V2 M2 | P2 |
| `docs/kb` wiki backlog (12+ fiches from 07-28..08-02) | backlogged | Medium | Periodic promotion to canonical (tests/skills/ADRs) | P3 |
| `.claude/STATE.md` recommendation: "present full audit to Jacob" | in-flight | Medium | Superseded by ADR 28–36 + declaration; close on commit | P3 |

---

## 7. Autonomous supervisor and recovery mechanisms

**Status:** Walking skeleton implemented (2026-08-15)
**Purpose:** Periodic autonomous execution of eligible Builder initiatives via a stateless supervisor running on launchd.

### Supervisor

The autonomous campaign supervisor (`gateway/builder_supervisor.py`) runs as a periodic launchd service that:

- Acquires an exclusive OS lock per tick (prevents duplicate concurrent runs)
- Deterministically selects eligible active initiatives (by ID order)
- Picks each initiative's next eligible packet (by `seq` order)
- Launches **at most 2 canonical free worker runs** per tick
- Returns truthful receipts (locked/launched/skipped with reasons)

Duplicate ticks are safe no-ops. The supervisor has no state machine of its own — all initiative/packet/task/lease/attempt/validation/review/publication truth remains in the existing durable Builder machinery.

**Installation:**

```bash
scripts/start_builder_supervisor.sh launchd > ~/Library/LaunchAgents/com.kitty.builder.supervisor.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kitty.builder.supervisor.plist
```

**Manual control:**

```bash
./kitty builder supervisor tick      # run one tick now
./kitty builder supervisor status    # read-only projection
launchctl kickstart -k gui/$(id -u)/com.kitty.builder.supervisor  # force tick
launchctl bootout gui/$(id -u)/com.kitty.builder.supervisor      # stop service
```

### Claude worker adapter

A strict Claude Code worker/reviewer adapter (`scripts/kittybuilder_claude_adapter.py`) provides fixed-model packet execution:

- Worker: Sonnet 4.5 (default, overridable via `KITTYBUILDER_CLAUDE_WORKER_MODEL`)
- Reviewer: Opus 4.6 (default, overridable via `KITTYBUILDER_CLAUDE_REVIEW_MODEL`)
- **No fallback** — a failed model run exits without retrying another model
- **Exit 75** when `claude` binary is unavailable or auth fails (before any work/mutation)
- **Reviewer immutability** — any worktree mutation aborts the review with no publication

Tests use a fake `claude` executable, so no live API requests occur in CI.

### Recovery from supervisor failures

If the supervisor dies mid-tick or launchd crashes:

1. The OS lock releases automatically (file descriptor closed)
2. Next periodic tick (or manual `supervisor tick`) re-evaluates eligibility
3. Already-claimed tasks appear as active runs and are skipped
4. Unclaimed queued tasks are selected normally

If a dispatched worker dies or hangs:

1. Builder's existing run heartbeat/timeout machinery detects it
2. The task becomes eligible for retry (governed by packet `max_attempts`)
3. Next supervisor tick (or manual initiative run) can claim it

**No manual cleanup required.** The supervisor is stateless; Builder's durable task/run state is the single authority.

### Discord integration

Discord Command Center provides a typed read-only projection of Builder state plus control commands. It translates user commands into MCP tool calls or Builder CLI invocations. Discord has:

- **No shell access** or arbitrary command execution
- **No approval/publication/merge** capabilities
- **No file/worktree** manipulation
- **No bypass** of Builder governance/tiering

Discord is a projection and control surface only. Builder remains the single authority for execution truth, initiatives, attempts, leases, and recovery state.

---

## 8. What should NOT be recovered (explicitly dead, with reason)

- **B8 clean-checkout trivia as a runnable packet** — obsolete proof; only its trust lesson matters.
- **ktf-004 / phase1-1 / RP-* / P1S harness fixtures** — proven stale, budget-consuming, zombies.
- **`feat/b8-clean-checkout-trivia`, `research/architecture-migration-analysis-cec062f` (post-ADR-0031), `proof/live-current-*` snapshot branches** — consumed or superseded; leave unmerged or delete after ADR 0031 commitment.
- **Old roadmap/plans superseded by ROADMAP/ROADMAP_V2** — keep as provenance, not direction.
- **MemPalace, external engine migrations (Prefect/Temporal/…)** — ADR 0031 deferred; no resurrection without Jacob.

---

## 9. Top recommendations (ranked)

1. **P0 — Trust Model**: run the handed-off task (`artifacts/handoff-builder-trust-model-v1.md`); deliver `docs/plans/builder-trust-model-v1.md`; enforce `needs_decision` as a gate; then make the B8/B9/B10 + RP/KTF cleanup decision from inside the model.
2. **P0 — Enforce red-main protection** (#399 / ROADMAP 0.7): Jacob enables branch protection requiring all 6 checks.
3. **P1 — Commit & disposition the parallel 08-05 cluster** (§0): Constitution, ROADMAP_V2, ADR 28–36, OPENWEBUI_PRODUCT_PLAN, OPENWEBUI_EXTENSION_BACKLOG, v2-driver-baseline; then apply the initiative and start M1-01/M1-09/M2-04.
4. **P1 — Convert `OPENWEBUI_EXTENSION_BACKLOG.md` into a Builder-managed backlog** (the stated next stage), beginning with the "One Thing / Morning Brief / Resume Loop" Open-every-morning tier.
5. **P1 — Re-scope the open product issues** (#346/#270/#336) against V2 M1–M4 so the move-in bar (2.3) is the milestone, not a separate plan.
6. **P3 — Run a stale-residue sweep** (Builder + branches + ledger) once the trust model lands, so zombie initiatives and orphan docs get explicit disposition entries.

---

## Appendix — sources not surveyed / unavailable

- `~/kb` was available and consulted (NOW, wiki, effectiveness, workflow signals).
- GitHub API reachable (PR/issue lists current as of query).
- Remote `origin/main` ref is local-stale (72 behind); PR #406/#391 read from GitHub directly.
- Runtime (`./kitty`/Gateway health) not probed this session — all Builder state read from the DB, not live processes.
