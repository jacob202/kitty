# Disposition Ledger — 2026-08-08

Every retained planning file in this repository has exactly one roadmap
disposition. Nothing may remain unassigned. This ledger is authoritative; a
file not listed here is either not a planning document or was added after the
ledger date and needs disposition.

**Roadmap authority:** `docs/ROADMAP.md` — the only roadmap. KPROOF-001 is terminal; M1–M6 remain blocked pending shell-authority adjudication and explicit activation.
**Milestone detail:** `docs/ROADMAP_V2.md` — appendix to the above, not a second authority and not a replacement for it.
**Derived synthesis:** `docs/KITTY_MASTER_PROGRAM.md` — merges ROADMAP, ROADMAP_V2, and the extension backlog into a dependency-ordered program. Not an independent authority.
**Governance:** `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` — 12 adjudicated decisions governing all of the above.
**Ledger date:** 2026-08-08
**Base SHA:** `4d4fa5a7` (origin/main)

## Disposition classes

| Disposition | Meaning |
|---|---|
| ACTIVE | Currently in progress within the named roadmap phase/outcome |
| SCHEDULED | Assigned to a specific future roadmap outcome with dependencies |
| BLOCKED | Cannot proceed until a named dependency clears |
| BACKLOG | Preserved idea; no active schedule; activates when Jacob decides |
| SUPERSEDED | Replaced by a newer document or absorbed into shipped work |
| REJECTED | Explicitly not worth carrying; preserved for provenance only |
| ARCHIVED | Retired to `docs/archive/`; narrative record, not active direction |

---

## docs/plans/ (8 files)

| File | Disposition | Roadmap outcome | Notes |
|---|---|---|---|
| `feat-kittybuilder-follow-on-roadmap.md` | SUPERSEDED | — | Absorbed into Gate 0.4 and this ledger. Builder follow-on is now Phase 1/3. |
| `image-studio-character-first-architecture-2026-07-28.md` | SCHEDULED | Phase 4.4 | Primary Image Studio architecture reference. Preserved direction. |
| `image-studio-runpod-vertical-slice-2026-07-30.md` | BLOCKED | Phase 3.4 | Authorized RunPod input. Parked until Phase 3 RunPod authorization. |
| `KITTY_PRODUCT_EXPERIENCE_V1.md` | BACKLOG | — | Draft product experience. Activates when Phase 4 product deepening begins. |
| `kitty-master-architecture-audit.md` | SUPERSEDED | — | Planning input consumed into this roadmap and `docs/ARCHITECTURE.md`. |
| `KITTYBUILDER_DAILY_DRIVER_PLAN.md` | SUPERSEDED | — | Consumed into Phase 1 and Phase 2 outcomes. Execution details in Builder manifests. |
| `KX_COHERENCE_AUDIT.md` | BACKLOG | — | KX coherence findings. Activates during Phase 4 product deepening. |

---

## docs/planning/ (8 files)

| File | Disposition | Roadmap outcome | Notes |
|---|---|---|---|
| `agent-prompts-2026-07-24.md` | SUPERSEDED | — | Historical agent task briefs. Consumed. |
| `feature-reference-map.md` | BACKLOG | — | Long-range reference. Activates as capability catalog during Phase 4. |
| `image-studio-character-system-2026-07-24.md` | SUPERSEDED | — | Explicitly superseded by `docs/plans/image-studio-character-first-architecture-2026-07-28.md`. |
| `kitty-next-evolution-working-notes.md` | ARCHIVED | — | 2026-07-07 working notes. Historical record. |
| `kitty-vision-gap-analysis-2026-07-24.md` | BACKLOG | — | Gap analysis. Activates as input during Phase 4 product deepening. |
| `kittybuilder-redesign-2026-07-24.md` | SUPERSEDED | — | Consumed into Phase 1 and Phase 3 Builder outcomes. |
| `vision-horizons.md` | BACKLOG | — | Canonical future-direction catalog. Activates during Phase 4. |

---

## docs/packets/ (31 entries: 29 .md + example dirs)

### Registry packets (numbered)

| # | File | Disposition | Roadmap outcome | Notes |
|---|---|---|---|---|
| 001 | `001-state-spine.md` | ARCHIVED | — | Shipped. ✅ |
| 002 | `002-inbox-triage.md` | ARCHIVED | — | Shipped. ✅ |
| 003 | `003-action-queue.md` | ARCHIVED | — | Shipped. ✅ |
| 004 | `004-state-home.md` | ARCHIVED | — | Shipped. ✅ |
| 005 | `005-mail-connector.md` | ARCHIVED | — | Shipped. ✅ |
| 006 | `006-project-resume.md` | ARCHIVED | — | Shipped. ✅ |
| 007 | `007-delegation-packet-generator.md` | ARCHIVED | — | Shipped. ✅ |
| 008 | `008-knowledge-library-expert-retrieval.md` | ARCHIVED | — | Shipped. ✅ |
| 014 | `014-make-the-gates-honest.md` | ARCHIVED | — | Shipped. ✅ |
| 015 | `015-phone-channel.md` | ARCHIVED | — | Shipped. ✅ |
| 016 | `016-next-step-navigator.md` | ARCHIVED | — | Shipped. ✅ |
| 017 | `017-benefits-rails-urgent-sweep.md` | ARCHIVED | — | Shipped. ✅ |
| 018 | `018-expert-packs.md` | ARCHIVED | — | Shipped. ✅ |
| 019 | `019-job-search-scaffold.md` | BLOCKED | Phase 4.3 | Parked by Jacob. Activates when he says. |
| 020 | `020-github-connector.md` | BACKLOG | Phase 4.3 | Planned, not built. |
| 021 | `021-memory-taste-and-creative-continuity.md` | SUPERSEDED | — | Ghost file — renumbered to 023. Retained for provenance but not the canonical packet. `023-memory-taste-and-creative-continuity.md` is the active record. |
| 021 | `021-project-registry-and-resume.md` | ARCHIVED | — | Shipped as 021. ✅ |
| 022 | `022-chat-log-idea-mine.md` | SUPERSEDED | — | Ghost file — renumbered to 024. Retained for provenance but not the canonical packet. `024-chat-log-idea-mine.md` is the active record. |
| 022 | `022-magic-kitty.md` | BACKLOG | Phase 4.5 | In progress, partial. |
| 023 | `023-memory-taste-and-creative-continuity.md` | ARCHIVED | — | Shipped. ✅ |
| 024 | `024-chat-log-idea-mine.md` | BACKLOG | Phase 4.5 | Spec authored, after move-in. |
| 025 | `025-imagegen-pipeline-v2.md` | BACKLOG | Phase 4.4 | Imagegen pipeline. |
| 026 | `026-audit-implement-low-risk.md` | SUPERSEDED | — | Consumed into Builder reliability. |
| 026 | `026-builder-reliability.md` | ACTIVE | Phase 1.1 | Builder reliability delta. |
| 028 | `028-reasoning-engine.md` | BACKLOG | Phase 4.1 | Reasoning engine spec. |

### Packet metadata

| File | Disposition | Notes |
|---|---|---|
| `README.md` | ACTIVE | Packet intake rules and registry. Maintained. |
| `TEMPLATE.md` | ACTIVE | Packet authoring template. |
| `DELTA_014_026_2026-07-26.md` | SUPERSEDED | Consumed into 026 Builder reliability. |
| `PACKET_AUDIT_2026-07-26.md` | SUPERSEDED | Consumed into this ledger and packet cleanup. |
| `examples/` | ACTIVE | Packet example directory. |

---

## docs/initiatives/ (45 entries: 38 .json + 7 .md/.sh)

### Builder initiative manifests (.json)

| File | Initiative ID | Disposition | Roadmap outcome | Notes |
|---|---|---|---|---|
| `builder-test-hardening-v1.json` | builder-test-hardening-v1 | BACKLOG | Phase 3.3 | Test hardening sweep. |
| `chat-recovery-continuation-v1.json` | chat-recovery-continuation-v1 | BACKLOG | Phase 4.1 | Chat recovery. |
| `chat-recovery-v1.json` | chat-recovery-v1 | SUPERSEDED | — | Replaced by continuation version. |
| `kitty-endgame-init-1-builder-closeout-v2.json` | kitty-endgame-init-1 | ACTIVE | Phase 1.1 | Builder closeout and operator authority. |
| `kitty-endgame-init-2-daily-driver-v1.json` | kitty-endgame-init-2 | ACTIVE | Phase 2 | Daily driver. |
| `kittybuilder-brain-v1.json` | kittybuilder-brain-v1 | BACKLOG | Phase 3.2 | Builder UI cockpit and autonomy. |
| `phase1-1-recovery-proof-v1.json` | phase1-1-recovery-proof | ACTIVE | Phase 1.1 | Induced-failure recovery proof template; driven by `scripts/builder_recovery_proof.py`, which rewrites the ids per run. |
| `ktf-001-free-exec-v1.json` | ktf-001-free-exec-v1 | SUPERSEDED | — | Original KTF-001 manifest; tasks cancelled. |
| `ktf-001-resume-proof-v2.json` | ktf-001-resume-proof-v2 | ACTIVE | Phase 1.1 | KTF-001 restart: reconcile, author, prove. |
| `ktf-002-acceptance-prose-v1.json` | ktf-002-acceptance-prose-v1 | BACKLOG | Phase 3.3 | Acceptance criteria fix. |
| `ktf-003-outcome6-runtime-v1.json` | ktf-003-outcome6-runtime-v1 | SUPERSEDED | — | Outcome 6 runtime; tasks cancelled. Runtime change on main. |
| `ktf-004-*` (4 files: daylight-*) | ktf-004-daylight-* | SUPERSEDED | — | Daylight proof manifests v1-v4. Replaced by Phase 1.3 outcomes. All four (`daylight-evidence-v2`, `daylight-lifecycle-v3`, `daylight-lifecycle-v4`, `daylight-proof-v1`) are read-only provenance records; current reliability evidence lives in `ktf-004-current-main-reliability-proof-v1.json`. |
| `ktf-004-current-main-reliability-proof-v1.json` | ktf-004-reliability | BACKLOG | Phase 1.1 | Reliability evidence manifest. |
| `ktf-005-life-resume-loop-gate-v1.json` | REJECTED | — | Rejected as Builder manifest; human-only runbook. |
| `ktl-002-measured-learning-boundary-v1.json` | ktl-002-measured-learning-boundary | BACKLOG | Phase 1.1 | KB effectiveness measurement and interactive/Builder lane boundary enforcement. |
| `kx-01-resume-work-presentation.json` | kx-01 | BACKLOG | Phase 4.2 | Resume loop presentation. |
| `kx-02-chat-execution.json` | kx-02 | BACKLOG | Phase 4.1 | Chat execution experience. |
| `kx-03-shell-consolidation-v1.json` | kx-03 | BACKLOG | Phase 4.2 | Shell consolidation. |
| `kx-04-surface-refit-v1.json` | kx-04 | BACKLOG | Phase 4.2 | Surface refit. |
| `kx-05-companion-layer-v1.json` | kx-05 | BACKLOG | Phase 4.2 | Companion layer. |
| `kx-06-proactive-feed-v1.json` | kx-06 | BACKLOG | Phase 4.2 | Proactive feed. |
| `kx-resume-and-chat-execution-v1.json` | kx-resume-and-chat | SUPERSEDED | — | Consolidated into kx-01 + kx-02. |
| `life-first-v1.json` | life-first-v1 | ACTIVE | Phase 2.1 | Life-first: Kitty serves Jacob's life. |
| `life-first-v1-integration.json` | life-first-v1-integration | BACKLOG | Phase 2.1 | Wire select_steps into user-facing paths. |
| `p2-worker-contract-tests.json` | p2-worker-contract-tests | BACKLOG | Phase 3.1 | Worker contract tests. |
| `packet-027-v1.json` | packet-027 | ACTIVE | Phase 1.1 | Builder restart/recovery proof. |
| `phase1-smoke-recovery-v1.json` | phase1-smoke-recovery | BACKLOG | Phase 1.1 | Minimal smoke initiative for full Builder lifecycle proof (validate, apply, run, verify, crash recovery). |
| `process-hardening-v1.json` | process-hardening-v1 | ACTIVE | Phase 3.3 | Reproducible review, durable receipts. |
| `reasoning-backend-v1.json` | reasoning-backend-v1 | BACKLOG | Phase 4.1 | Packet 028 backend slices. |
| `trust-lane-v1.json` | trust-lane-v1 | BACKLOG | Phase 3.3 | Trust lane sweep. |
| `v2-driver-baseline-v1.json` | v2-driver-baseline-v1 | BLOCKED | M1–M6, blocked pending shell-authority adjudication | First V2 initiative: 10 packets for daily-driver baseline, console re-role, and Builder Work integration, on the M1–M6 scheme detailed in `docs/ROADMAP_V2.md`. **Still not ACTIVE after KPROOF ended** — applying it queues dependency-free packets, while M1/M2 currently depend on an unresolved Constitution/ADR 0039 shell decision. Matches the `docs/initiatives/` row below. Live-environment and operator-approval packets remain separately gated behind explicit operator consent. |

### Initiative READMEs and evidence (.md/.sh)

| File | Disposition | Notes |
|---|---|---|
| `B1-preflight-evidence-2026-07-23.md` | ARCHIVED | Historical preflight evidence. |
| `B2-kbs4-gap-register-2026-07-23.md` | ARCHIVED | Historical gap register. |
| `KTF-001-free-exec-gate-evidence.md` | ARCHIVED | Historical gate evidence. |
| `README-kittybuilder-brain-v1.md` | BACKLOG | Retained initiative inputs, not current sequence. |
| `README-ktf-003-outcome6-runtime.md` | SUPERSEDED | Superseded execution input. |
| `README-ktf-005-life-resume-loop-human-gate.md` | BACKLOG | Human runbook reference. |
| `ktf-004-verify-daylight-operator-brief.sh` | ARCHIVED | Verification script, historical. |
| `ktf-004-verify-inspected-head.sh` | ARCHIVED | Verification script, historical. |

---

## docs/research/ (15 files)

| File | Disposition | Notes |
|---|---|---|
| `FOUNDATION_REPLACEMENT_STUDY_2026-07-27.md` | BACKLOG | Foundation replacement study. |
| `GENEVOLVE_ADAPTATION_2026-07-28.md` | BACKLOG | GenEvolve adaptation reference. |
| `KITTY_KITTYBUILDER_ARCHITECTURE_CORRECTION_2026-07-28.md` | SUPERSEDED | Absorbed into `docs/ARCHITECTURE.md` and ADRs. |
| `kittybuilder-brain-v1-harvest.md` | BACKLOG | Builder brain harvest. |
| `ktf-001-reliability-reconciliation-2026-07-30.md` | BACKLOG | KTF-001 reconciliation evidence. |
| `ktf-004-*` (4 files: current-main, daylight-evidence, operator-brief, run-evidence) | BACKLOG | KTF-004 evidence records. Historical proof. |
| `ktf-004-t1-manifest-review-2026-07-29.md` | BACKLOG | KTF-004 manifest review. |
| `packet-026-027-delta-2026-08-01.md` | ACTIVE | Phase 1.1 delta, measured against code at `27deef1`. Names the one remaining 026 blocker. |
| `phase1-1-builder-recovery-proof.md` | ACTIVE | Generated by `scripts/builder_recovery_proof.py`. Regenerated on every proof run. |
| `pr-306-runpod-review-2026-07-31.md` | ACTIVE | RunPod worker review findings. References PR #306. |
| `pr-review-48h-2026-07-31.md` | ACTIVE | 48h PR review findings. References #327, #328, #330. |
| `prompt-fix-main-2026-07-31.md` | SUPERSEDED | Executor prompt consumed by #327, #328, #330. Tasks complete. |

---

## docs/audit/ (3 files)

| File | Disposition | Notes |
|---|---|---|
| `PROGRESS_REVIEW_2026-07-31.md` | SUPERSEDED | Consumed into this roadmap rewrite. Findings actioned. |
| `architecture-honesty-2026-07-24.md` | BACKLOG | Architecture gap analysis. |
| `backend-frontend-gap-2026-07-24.md` | BACKLOG | Backend-frontend gap analysis. |

---

## docs/phases/ (12 files)

All phase documents are historical: ARCHIVED, BACKLOG, or a SUPERSEDED
compatibility pointer. The phases directory contains historical phase plans
(PHASE_B, PHASE_C, etc.) and companion voice charters that predate the current
roadmap structure. None are active execution inputs.
Specific dispositions:

| File | Disposition | Notes |
|---|---|---|
| `COMPANION_VOICE_CHARTER.md` | BACKLOG | Voice direction; activates during Phase 4. |
| `CONTEXT_ENGINEERING.md` | SUPERSEDED | Compatibility pointer only. Current staged context-loading authority is `docs/reference/CONTEXT_ENGINEERING.md`, referenced by `AGENTS.md`. |
| `DESKTOP_SLICE_1_RUNBOOK.md` | ARCHIVED | Historical runbook. |
| `EVALS.md` | BACKLOG | Evaluation framework. |
| `MEMPALACE_MIGRATION_RUNBOOK.md` | ARCHIVED | Historical migration runbook. |
| `PHASE_B_ARCHAEOLOGY_REPORT.md` | ARCHIVED | Historical phase report. |
| `PHASE_B_PLAN.md` | ARCHIVED | Historical phase plan. |
| `PHASE_C_JOURNAL_PLAN.md` | ARCHIVED | Historical journal plan. |
| `PHASE_C_PLAN.md` | ARCHIVED | Historical phase plan. |
| `PHASE_C3_PLAN.md` | ARCHIVED | Historical phase plan. |
| `STORAGE_MIGRATION_PLAN.md` | ARCHIVED | Historical migration plan. |
| `VOICE_CORPUS.md` | BACKLOG | Voice corpus; activates during Phase 4. |

---

## docs/recon/ (2 files)

| File | Disposition | Notes |
|---|---|---|
| `REPO_SCOUTING_2026-07-24.md` | BACKLOG | Repo scouting report. |
| `repo-landscape-2026-07-24.md` | BACKLOG | External landscape comparison. |

---

## docs/ (governance and planning docs since 2026-08-05)

| File | Disposition | Notes |
|---|---|---|
| `CONSTITUTION.md` | ACTIVE | Highest-level design artifact. Ratified 2026-08-05. Consolidates principles from ADRs 003, 017, 027, 028, 029, 032, 034, 036 plus KITTY_PRODUCT_ARCHITECTURE, BLUEPRINT, NORTH_STAR, FREE_MODEL_PACKET_STANDARD, and ROADMAP_V2. |
| `ROADMAP_V2.md` | BLOCKED | Milestone detail behind `ROADMAP.md`'s M1–M6. Ratified by the Constitution v1 as accepted architecture, not an execution schedule. Blocked pending explicit shell-authority adjudication and ROADMAP.md activation. |
| `KITTY_MASTER_PROGRAM.md` | ACTIVE (derived synthesis) | Derived synthesis of ROADMAP, ROADMAP_V2, and the extension backlog into a dependency-ordered program. Not an independent authority. |
| `KNOWLEDGE_GRAPH.md` | ACTIVE | Repository knowledge archaeology. Maps ADR supersession chains, document dependencies, initiative-to-roadmap alignment, structural problems, and the minimum architectural-continuity graph for Builder. |
| `CAPABILITY_MANIFEST.md` | ACTIVE (designed) | Capability Manifest v1 specification. DESIGNED per ADR 0029. Not yet built. |
| `CONTINUITY_RECOVERY.md` | ACTIVE | Live unfinished-work inventory, zombie initiative registry, and prioritized recovery recommendations. References live Builder state and the KB. |
| `OPENWEBUI_OS_ARCHITECTURE.md` | ACTIVE (research) | Open WebUI OS-architecture research for Kitty's integration boundary. |
| `OPENWEBUI_PRODUCT_PLAN.md` | ACTIVE (target) | Open WebUI product plan and extension backlog reference. Implements Constitution v1 and ADR 0027. |
| `OPENWEBUI_EXTENSION_BACKLOG.md` | ACTIVE (target) | 38 ranked extensions (S/A/B tiers). V2 product plan reference. |
| `BUILDER_ORGANIZATION.md` | BACKLOG (design) | Design — not yet implemented. Not ratified. Builder's ratified role is execution control plane (ADR 0017). Organization concepts may inform future ADR amendments per ARCHITECTURE_RATIFICATION Decision 4. |
| `BUILDER_V2.md` | BACKLOG (design) | Replacement blueprint — not yet implemented. Not ratified. Builder's ratified role is execution control plane (ADR 0017) with internal refactoring (ADR 0036). V2 redesign concepts may inform future ADR amendments per ARCHITECTURE_RATIFICATION Decision 4. |
| `decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` | ACTIVE | 12 adjudicated architectural decisions with evidence trails and 18 merge conditions for PR #408. Cross-cutting governance, not a numbered ADR. |
| `CLOSEOUT_LEDGER_2026-08-05.md` | ACTIVE (historical) | Deliverable ledger for the 2026-08-05 closeout. |
| `LOOSE_ENDS_2026-08-05.md` | ACTIVE (historical) | Loose-ends register for the 2026-08-05 closeout. |
| `reference/OPENWEBUI_ECOSYSTEM_SURVEY.md` | ACTIVE (research) | Open WebUI ecosystem survey. |

## docs/plans/ (3 additional since 2026-07-31)

| File | Disposition | Notes |
|---|---|---|
| `openwebui-agent-handoff-2026-08-02.md` | SUPERSEDED | Open WebUI onboarding handoff. Baseline gaps (#1 PYTHONPATH, #2 dup admin) addressed on disk in `scripts/openwebui_tool/`. Absorbed into PR #384. |
| `openwebui-onboarding-checklist.json` | ARCHIVED | Onboarding checklist consumed by PR #384 verification. |
| `openwebui-onboarding-progress.md` | ARCHIVED | Progress tracking consumed by PR #384 merge. |

## docs/runbooks/ (1 file)

| File | Disposition | Notes |
|---|---|---|
| `OPENWEBUI_TOMORROW.md` | ACTIVE | Daily-driver operator runbook. Next-day startup and troubleshooting. |

## docs/initiatives/ (corrected: 1 retired manifest)

| File | Disposition | Notes |
|---|---|---|
| `retired/ktl-001-leverage-and-learning-v1.json.retired` | RETIRED | Retired KTL-001 manifest. Non-applicable planning history preserved for concept reuse. Superseded by `ktl-002-measured-learning-boundary-v1.json`. |

---

## Active recommendations (from .claude/STATE.md and HANDOFF.md)

| Recommendation ID | Disposition | Roadmap outcome | Notes |
|---|---|---|---|
| `runpod-template-containerstartcmd` | BLOCKED | Phase 3.4 | Awaiting Phase 3 RunPod authorization. |
| `runpod-custom-image` | BLOCKED | Phase 3.4 | Awaiting Phase 3 RunPod authorization. |

---

## Open PRs (excluding Dependabot)

| PR | Title | Disposition | Notes |
|---|---|---|---|
| #306 | feat(image): RunPod worker vertical slice | BLOCKED | Draft reference. Parked until Phase 3.4. |
| #311-323 | Dependabot dependency updates | ACTIVE | Mergeable individually as CI allows. |

---

## Summary

The row-level dispositions above are the authority. The old aggregate counts were removed on 2026-08-19 because they had drifted from the rows themselves (for example, `ROADMAP_V2.md` was BLOCKED in its row while the summary counted it as ACTIVE). Do not use hand-maintained totals as execution evidence; derive counts from the canonical rows if a count is needed.

**Unassigned:** no known retained planning file is intentionally left without a row, but new files added after the last complete inventory require disposition before they can become execution input.

---

## Addendum — 2026-08-05 closeout (files added after the ledger date)

The following documents were produced by the 2026-08-05 architecture research
phase and preserved on `closeout/2026-08-05-architecture-reconciliation`. Full
detail and owners are in [`CLOSEOUT_LEDGER_2026-08-05.md`](CLOSEOUT_LEDGER_2026-08-05.md).

| File | Disposition | Roadmap outcome | Notes |
|---|---|---|---|
| `docs/adr/0028-…0036-*.md` | ACTIVE | ADR authority | Accepted; indexed in DECISIONS.md D27–D35 |
| `docs/OPENWEBUI_OS_ARCHITECTURE.md` | BACKLOG | Phase 2 daily-driver | Proposal (would evolve ADR 0027 to permanent shell); awaits Jacob decision |
| `docs/OPENWEBUI_PRODUCT_PLAN.md` | BACKLOG | Phase 2 (M1/M2) | Needs review |
| `docs/OPENWEBUI_EXTENSION_BACKLOG.md` | BACKLOG | Phase 2 (M1/M2) | Needs review → Builder-managed backlog |
| `docs/ROADMAP_V2.md` | BLOCKED | ROADMAP.md M1–M6 | Detail appendix to `ROADMAP.md`, which now names M1–M6 as the single post-proof order. The C-5 authority conflict is resolved: there is one roadmap and this is its detail, not a rival plan. **Still BLOCKED after KPROOF ended** — not SCHEDULED, because the preserved M1/M2 shell assumptions conflict with ADR 0039 and cannot be activated until the Constitution-level conflict is adjudicated. |
| `docs/initiatives/v2-driver-baseline-v1.json` | BLOCKED | Phase 2 | NOT applied; blocked on needs_decision fix + Jacob approval (P0-7) |
| `docs/BUILDER_ORGANIZATION.md` | BACKLOG | Phase 1/3 | Design, not implemented |
| `docs/BUILDER_V2.md` | BACKLOG | Phase 1/3 | Replacement blueprint, not implemented |
| `docs/CAPABILITY_MANIFEST.md` | SCHEDULED | Phase 2 (M1 Home, M2 console) | Core spec implementing ADR 0029; Jacob sign-off (P1-3) |
| `docs/KITTY_MASTER_PROGRAM.md` | BACKLOG | — | Proposed; supersede claim conflicts with ROADMAP.md (C-5) |
| `docs/CONSTITUTION.md` (v1) | ACTIVE (pending ratification) | Top-level design authority | Ratification decision (C-6) |
| `docs/KNOWLEDGE_GRAPH.md` | BACKLOG | — | Analysis catalog |
| `docs/CONTINUITY_RECOVERY.md` | BACKLOG | — | Needs review |
| `docs/research/architecture-decision-summary-2026-08-05.md` | ACTIVE | Research index | Decision-tree reference |
| `docs/research/architecture-migration-analysis-2026-08-05.md` | BACKLOG | — | Migration deferred (ADR 0031) |
| `docs/research/README.md` | ACTIVE | Research index | Research index (new) |
| `docs/CLOSEOUT_LEDGER_2026-08-05.md` | ACTIVE | — | This closeout ledger |
| `docs/LOOSE_ENDS_2026-08-05.md` | ACTIVE | — | P0–P3 register; drives next action |
| `artifacts/forensic-b8-wrong-assignment-2026-08-05.md` | ACTIVE | — | Evidence for P0-1 fix |
| `artifacts/handoff-builder-trust-model-v1.md` | BACKLOG | Phase 1 | Task brief; deliverable not yet produced |

**Carried to origin/main:** awaiting Jacob review/merge of the closeout branch.
