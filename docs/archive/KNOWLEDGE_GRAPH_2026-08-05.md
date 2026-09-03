# Kitty Knowledge Graph

**Date:** 2026-08-05
**Status:** Analysis. No implementation proposals.
**Scope:** Relationship archaeology — what the repository knows, what it connects
to, and where the graph is broken.

This document is a map of the knowledge, not a plan for the code.

---

## 1. Inventory

The repository contains 217 knowledge-bearing artifacts across 9 categories.

### 1.1 — Architectural Decision Records (36 active + 1 template)

Every durable decision has one file under `docs/adr/`. Four supersession chains exist:

| Chain | From | Via | To |
|---|---|---|---|
| D10 privacy boundary | ADR 0011 | — | ADR 0022 (retired) |
| D10 partial clause | ADR 0012 (local-only) | — | ADR 0022 (retired) |
| ADR 0019 decision 7 | ADR 0019 (study-only Open WebUI) | — | ADR 0027 (shell accepted) |
| ADR 0027 operational detail | ADR 0027 | — | ADR 0033 (extended with boundary specs) |

Eight ADRs carry explicit amendments:

| ADR | Amended by | What changed |
|---|---|---|
| 0010 | 2026-07-26 | Personal operating layer redefined |
| 0013 | 2026-07-26 | Phone-first delivery updated |
| 0015 | 2026-07-26 | Resume loop boundary refined |
| 0017 | 0020, 0024 | Packet decomposition moved; independent operator app |
| 0018 | 0021 | Campaign-only → proactive execution scope |
| 0023 | 0025 | Session-end procedure refined |
| 0025 | 2026-08-01 | Session learning boundary tightened |

One ADR is fulfilled/historical: 0006 (Phase B consolidation completed).

All 36 ADRs from 0001–0036 are ratified. None are open, draft, or proposed.

### 1.2 — Top-Level Architecture & Governance (23 documents)

| Document | Role | Dated |
|---|---|---|
| `CONSTITUTION.md` | Highest design authority | 2026-08-05 |
| `NORTH_STAR.md` | Product purpose | 2026-07-11 |
| `BLUEPRINT.md` | Product direction at a moment | 2026-07-11 |
| `KITTY_PRODUCT_ARCHITECTURE.md` | Formal 4-spine architecture | 2026-07-10 |
| `ARCHITECTURE.md` | Current runnable system shape | 2026-07-17 |
| `ALIGNMENT_MAP.md` | Kitty/Builder layering and authority order | 2026-07-26 |
| `AUTHORITY_MAP.md` | Which document owns which truth | current |
| `ROADMAP.md` | Active forward-looking sequence | current |
| `ROADMAP_V2.md` | V2 master roadmap | 2026-08-05 |
| `DECISIONS.md` | Decision index → ADRs | 2026-08-01 |
| `DISPOSITION_LEDGER.md` | Canonical disposition of all planning files | 2026-07-31 |
| `PROJECT_STATUS.md` | Verified shipped capabilities | SHA-tracked |
| `ACTIVE_MISSION.md` | Current approved mission | current |
| `LEARNINGS.md` | Reusable engineering patterns | 2026-07-26 |
| `OPERATOR_STRATEGY.md` | Session orchestration rules | current |
| `FREE_MODEL_PACKET_STANDARD.md` | Packet contract for free-model workers | 2026-07-26 |
| `FREE_WORKERS.md` | Free worker configuration | current |
| `CAMPAIGN_PLAYBOOK.md` | Builder campaign execution rules | current |
| `CODEBASE_MAP.md` | Entry points, data flows, state ownership | current |
| `UX_RULES.md` | UI conventions | current |
| `JOURNEY.md` | User journey reference | current |
| `FEATURE_REALITY_2026-07-28.md` | What was real vs fake at that date | 2026-07-28 |
| `INITIATIVES_OPTIMIZED_2026-07-24.md` | Initiative optimization rules | 2026-07-24 |
| `DECISION_REVIEW_2026-07-26.md` | Decision audit | 2026-07-26 |
| `PRODUCT_ACCEPTANCE.md` | Product acceptance criteria | current |
| `memory-stale.md` | Stale memory notes | uncommitted |
| `skill-improvement-queue.md` | Skill improvement tracking | uncommitted |

### 1.3 — Roadmaps (2 active, 1 superseded)

| Document | Status | Notes |
|---|---|---|
| `ROADMAP.md` | ACTIVE | One canonical roadmap (ADR 0020). Gate/Outcome scheme. |
| `ROADMAP_V2.md` | PROPOSED | V2 master roadmap. M1–M6 milestone scheme. Supersedes most of ROADMAP.md. |
| `docs/retired/FUTURE_VISION_AND_ROADMAP.md` | SUPERSEDED | Original vision doc. |

### 1.4 — Research (19 investigations)

| Document | Dated | Key concern |
|---|---|---|
| `FOUNDATION_REPLACEMENT_STUDY_2026-07-27.md` | 2026-07-27 | Replace or keep foundation infrastructure |
| `GENEVOLVE_ADAPTATION_2026-07-28.md` | 2026-07-28 | GenEvolve image pipeline reference |
| `KITTY_KITTYBUILDER_ARCHITECTURE_CORRECTION_2026-07-28.md` | 2026-07-28 | Kitty/Builder boundary correction |
| `kittybuilder-brain-v1-harvest.md` | 2026-07-28 | Builder brain harvest findings |
| `ktf-001-reliability-reconciliation-2026-07-30.md` | 2026-07-30 | KTF-001 evidence reconciliation |
| `ktf-004-t1-manifest-review-2026-07-29.md` | 2026-07-29 | KTF-004 manifest review |
| `ktf-004-daylight-evidence-v2.md` | 2026-07 | Daylight proof evidence |
| `ktf-004-daylight-operator-brief.md` | 2026-07 | Daylight operator brief |
| `ktf-004-daylight-run-evidence.md` | 2026-07 | Daylight run evidence |
| `ktf-004-current-main-runtime-proof.md` | 2026-08 | Current main runtime proof |
| `open-session-audit-2026-08-01.md` | 2026-08-01 | Open session audit — references 30+ issues |
| `packet-026-027-delta-2026-08-01.md` | 2026-08-01 | Builder reliability delta |
| `phase1-1-builder-recovery-proof.md` | generated | Builder recovery evidence |
| `pr-306-runpod-review-2026-07-31.md` | 2026-07-31 | RunPod PR #306 review |
| `pr-review-48h-2026-07-31.md` | 2026-07-31 | 48h PR review sweep |
| `prompt-fix-main-2026-07-31.md` | 2026-07-31 | Executor prompt fixes (consumed) |
| `chat-reuse-trust-slice.md` | current | Chat trust slice |
| `backup-restore-proof-2026-08-02.md` | 2026-08-02 | Backup/restore evidence |
| `kittybuilder-core-runtime-audit-2026-08-01.md` | 2026-08-01 | Core runtime audit |

### 1.5 — Plans (12 documents)

| Document | Dated | Disposition |
|---|---|---|
| `openwebui-agent-handoff-2026-08-02.md` | 2026-08-02 | SUPERSEDED — gaps addressed, absorbed |
| `openwebui-onboarding-progress.md` | current | ACTIVE — tracking |
| `openwebui-onboarding-checklist.json` | current | ACTIVE |
| `feat-kittybuilder-follow-on-roadmap.md` | earlier | SUPERSEDED — absorbed into Gate 0.4 |
| `image-studio-character-first-architecture-2026-07-28.md` | 2026-07-28 | SCHEDULED Phase 4.4 |
| `image-studio-runpod-vertical-slice-2026-07-30.md` | 2026-07-30 | BLOCKED until Phase 3.4 |
| `KITTY_PRODUCT_EXPERIENCE_V1.md` | earlier | BACKLOG |
| `kitty-master-architecture-audit.md` | earlier | SUPERSEDED |
| `KITTYBUILDER_DAILY_DRIVER_PLAN.md` | earlier | SUPERSEDED |
| `KX_COHERENCE_AUDIT.md` | earlier | BACKLOG |
| `kitty-ui-enhancement-plan.html` | earlier | BACKLOG |
| `migration-health.md` | earlier | BACKLOG |

### 1.6 — Mission Documents (6)

`docs/mission/`: `builder-map.md`, `decisions.md`, `evidence.md`, `execution.md`,
`failures.md`, `grounding.md`. These define the current approved Mission's
constraints, evidence requirements, and failure boundaries. They reference
issues #322, #331, #336, #339, #355 extensively.

### 1.7 — Builder Initiatives (41 JSON manifests, 7 supporting docs)

28 distinct initiative IDs. Seven are ACTIVE, seventeen are BACKLOG, eight are
SUPERSEDED, one is REJECTED. The initiative-to-roadmap mapping lives in
`DISPOSITION_LEDGER.md` (using the Phase X.Y scheme).

Orphan initiatives (JSON manifests not in the disposition ledger):
- `ktf-004-daylight-evidence-v2.json`
- `ktf-004-daylight-lifecycle-v3.json`
- `ktf-004-daylight-lifecycle-v4.json`
- `ktf-004-daylight-proof-v1.json`
- `ktl-002-measured-learning-boundary-v1.json`
- `phase1-smoke-recovery-v1.json`
- `v2-driver-baseline-v1.json`

### 1.8 — Packets (30 .md files under docs/packets/)

Numbered 001–028 with gaps. Twelve shipped (ARCHIVED). Two are duplicate
pairs (021/023 and 022/024 due to renumbering). Free worker guidance in
packet 014 documents the `npm run` silent-194-exit defect.

### 1.9 — Issues and PRs

GitHub auth unavailable at analysis time. From git log and document references,
the active knowledge-bearing items include:

**PRs (known state):**
- #384 — MERGED (Open WebUI daily driver baseline, `5e25235c`)
- #388 — MERGED (backup/restore)
- #392 — MERGED (AIM42 skill)
- #394 — MERGED (Builder adapter seam)
- #395 — MERGED (Trust harness)
- #306 — DRAFT (RunPod worker, blocked until Phase 3.4)
- #406 — DRAFT (Builder proof)
- #391 — DRAFT (PAA alignment profile)

**Issues (referenced in docs, open per last known state):**
#270, #336, #346 (P0), #349, #353, #354, #389, #390, #352, #399

---

## 2. Relationship Graph

### 2.1 — Supersession Chains

```
BLUEPRINT.md (2026-07-11)
  └─ PARTIALLY SUPERSEDED BY → ADR 0017 (control-plane boundary)
  └─ SUPERSEDED BY → KITTY_PRODUCT_ARCHITECTURE.md (formal architecture)

FOUNDATION_REPLACEMENT_STUDY (2026-07-27)
  └─ SUPERSEDED BY → ADR 0028 (commodity software precedence)
  └─ SUPERSEDED BY → ADR 0031 (architecture migration deferred)

KITTY_KITTYBUILDER_ARCHITECTURE_CORRECTION (2026-07-28)
  └─ ABSORBED BY → ARCHITECTURE.md + ADRs 0017, 0021

ROADMAP.md (current)
  └─ PROPOSED REPLACEMENT → ROADMAP_V2.md (2026-08-05)

ROADMAP_V2.md
  └─ REFERENCES → ROADMAP.md (as authority)
  └─ REFERENCES → KITTY_PRODUCT_ARCHITECTURE.md (as authority)
  └─ REFERENCES → ADR 0027 (Open WebUI shell)

KITTY_PRODUCT_ARCHITECTURE.md
  └─ DOCUMENTS → Phase 0-6 architecture delivery sequence
  └─ REFERENCED BY → ROADMAP_V2.md, DISPOSITION_LEDGER.md

DISPOSITION_LEDGER.md
  └─ INDEXES → all planning files (plans, initiatives, research, audit)
  └─ MAPS TO → ROADMAP.md Phase scheme
  └─ DOES NOT INCLUDE → CONSTITUTION.md, ROADMAP_V2.md, v2-driver-baseline-v1.json

CONSTITUTION.md
  └─ CONSOLIDATES → ADRs 003, 017, 027, 028, 029, 032, 034, 036
  └─ CONSOLIDATES → KITTY_PRODUCT_ARCHITECTURE, BLUEPRINT, NORTH_STAR
  └─ CONSOLIDATES → FREE_MODEL_PACKET_STANDARD, ROADMAP_V2
  └─ NOT REFERENCED BY → AUTHORITY_MAP.md, DISPOSITION_LEDGER.md

AUTHORITY_MAP.md
  └─ DEFINES OWNERSHIP FOR → 20+ documents
  └─ DOES NOT INCLUDE → CONSTITUTION.md, ROADMAP_V2.md
```

### 2.2 — ADR Amendment / Extension Graph

```
ADR-0011 ──SUPERSEDED BY──→ ADR-0022
ADR-0012 ──PARTIALLY RETIRED BY──→ ADR-0022
ADR-0019(d7) ──SUPERSEDED BY──→ ADR-0027
ADR-0027 ──EXTENDED BY──→ ADR-0033
ADR-0017 ──AMENDED BY──→ ADR-0020, ADR-0024
ADR-0018 ──AMENDED BY──→ ADR-0021
ADR-0010 ──AMENDED BY──→ (2026-07-26)
ADR-0013 ──AMENDED BY──→ (2026-07-26)
ADR-0015 ──AMENDED BY──→ (2026-07-26)
ADR-0023 ──AMENDED BY──→ ADR-0025
ADR-0025 ──AMENDED BY──→ (2026-08-01)
ADR-0030 ──REFERENCES──→ ADR-0001, ADR-0004, ADR-0028
ADR-0031 ──REFERENCES──→ ADR-0017, ADR-0021, ADR-0028, ADR-0030
ADR-0034 ──REFERENCES──→ ADR-0004, ADR-0030, ADR-0031
ADR-0036 ──REFERENCES──→ ADR-0017, ADR-0021, ADR-0030, ADR-0031
ADR-0026 ──REFERENCES──→ ADR-0017, ADR-0021, ADR-0023, ADR-0025
```

### 2.3 — Initiative → Roadmap Mapping

```
ACTIVE (7):
  kitty-endgame-init-1 ──ALIGNED TO──→ ROADMAP Phase 1.1
  kitty-endgame-init-2 ──ALIGNED TO──→ ROADMAP Phase 2
  phase1-1-recovery-proof ──ALIGNED TO──→ ROADMAP Phase 1.1
  ktf-001-resume-proof-v2 ──ALIGNED TO──→ ROADMAP Phase 1.1
  life-first-v1 ──ALIGNED TO──→ ROADMAP Phase 2.1
  packet-027 ──ALIGNED TO──→ ROADMAP Phase 1.1
  process-hardening-v1 ──ALIGNED TO──→ ROADMAP Phase 3.3

BACKLOG (17):
  kx-01 through kx-06 ──ALIGNED TO──→ ROADMAP Phase 4.2 (Resume/chat/feed)
  ktf-002-acceptance-prose ──ALIGNED TO──→ Phase 3.3
  ktf-004-reliability ──ALIGNED TO──→ Phase 1.1
  builder-test-hardening ──ALIGNED TO──→ Phase 3.3
  chat-recovery-continuation ──ALIGNED TO──→ Phase 4.1
  kittybuilder-brain ──ALIGNED TO──→ Phase 3.2
  life-first-v1-integration ──ALIGNED TO──→ Phase 2.1
  p2-worker-contract-tests ──ALIGNED TO──→ Phase 3.1
  reasoning-backend ──ALIGNED TO──→ Phase 4.1
  trust-lane ──ALIGNED TO──→ Phase 3.3

UNMAPPED (7 orphans from ledger):
  ktf-004-daylight-* (4 manifests) ── all SUPERSEDED
  ktl-002-measured-learning-boundary ── no roadmap outcome
  phase1-smoke-recovery ── no roadmap outcome
  v2-driver-baseline-v1 ── NEW, uses M1-M6 scheme
```

### 2.4 — Top Document Dependency Graph

```
CONSTITUTION.md
├── depends on ADR-003, ADR-017, ADR-027, ADR-028, ADR-029, ADR-032, ADR-034, ADR-036
├── documents KITTY_PRODUCT_ARCHITECTURE
├── implements NORTH_STAR
└── referenced by (nothing yet)

ROADMAP_V2.md
├── depends on ROADMAP.md
├── depends on ADR-027
├── depends on KITTY_PRODUCT_ARCHITECTURE
└── enables v2-driver-baseline-v1.json

ROADMAP.md
├── depends on DISPOSITION_LEDGER.md
├── references issues #306, #314, #322, #326, #327, #328, #330, #336, #339
└── OUTGOING → ROADMAP_V2.md (proposed replacement)

KITTY_PRODUCT_ARCHITECTURE.md
├── depends on ADR-017
├── documents Phase 0-6 delivery
├── referenced by ROADMAP_V2.md, DISPOSITION_LEDGER.md
└── supercedes BLUEPRINT.md (partial)

AUTHORITY_MAP.md
├── defines ownership for all active documents
├── MISSING: CONSTITUTION.md, ROADMAP_V2.md
└── CONFLICT RULES: live Git > ADR > ROADMAP > prose

DISPOSITION_LEDGER.md
├── indexes 136 planning files
├── MISSING: 7 initiative JSONs (orphans)
├── MISSING: CONSTITUTION.md, ROADMAP_V2.md
└── dated 2026-07-31 at SHA 59f598c5
```

---

## 3. Structural Problems

### 3.1 — Orphaned Documents

Seven initiative JSON manifests exist on disk but are not recorded in
`DISPOSITION_LEDGER.md`:

| Manifest | Status | Concern |
|---|---|---|
| `ktf-004-daylight-evidence-v2.json` | SUPERSEDED | Daylight proof, superseded by Phase 1.3 |
| `ktf-004-daylight-lifecycle-v3.json` | SUPERSEDED | Earlier iteration |
| `ktf-004-daylight-lifecycle-v4.json` | SUPERSEDED | Earlier iteration |
| `ktf-004-daylight-proof-v1.json` | SUPERSEDED | Original daylight proof |
| `ktl-002-measured-learning-boundary-v1.json` | UNKNOWN | Not referenced by any doc |
| `phase1-smoke-recovery-v1.json` | UNKNOWN | Not in ledger, not in any roadmap |
| `v2-driver-baseline-v1.json` | NEW | Created 2026-08-05, uses M1-M6 scheme |

Two top-level docs are uncommitted and not in any ledger:
- `docs/CONSTITUTION.md` (new)
- `docs/ROADMAP_V2.md` (new, untracked)

Two docs exist on disk uncommitted and untracked:
- `docs/memory-stale.md`
- `docs/skill-improvement-queue.md`

### 3.2 — Duplicated Research / Redundant Artifacts

**KTF-004 cluster:** Four initiative manifests and four research docs cover the
same daylight proof. All four manifests are SUPERSEDED. The research docs are
BACKLOG. No single artifact is the canonical owner of "is the daylight proof
passing?"

**Renumbered packets:** Packet 021 was renamed to 023. Packet 022 was renamed
to 024. Both old and new files exist on disk with SUPERSEDED/ARCHIVED
dispositions. The `packets/` directory carries 30 files covering 26 distinct
packet numbers.

**Double-phase plans:** The `docs/plans/` and `docs/initiatives/` directories
both contain delivery tracking for the same work (Builder closeout, daily
driver, RunPod, Image Studio). Disposition ledger assigns them to roadmap
outcomes, but the planning prose and initiative manifests compete for authority
over what "done" means.

### 3.3 — Three Incompatible Phase Numbering Schemes

Three different documents define the delivery sequence using different
identifiers, and documents cross-reference freely between them:

| Document | Scheme | Example |
|---|---|---|
| `KITTY_PRODUCT_ARCHITECTURE.md` | Phase 0–6 | "Phase 1 = runtime truth + honest identity" |
| `ROADMAP.md` | Gate / Phase / Outcome | "Phase 1.1", "Outcome 0.5" |
| `ROADMAP_V2.md` | Milestones M1–M6 | "M1 = daily-driver shell is real" |
| `DISPOSITION_LEDGER.md` | Hybrid | References "Phase 1.1", "Phase 4.2" |

The DISPOSITION_LEDGER uses the ROADMAP.md's Phase X.Y scheme, but
ROADMAP_V2.md proposes replacing ROADMAP.md. If adopted, every initiative's
roadmap alignment becomes stale.

ROADMAP_V2 references "product-architecture Phase 1 honesty norm" while using
milestone M2. The two schemes coexist in a single document.

### 3.4 — Stale References

**DISPOSITION_LEDGER.md** is dated 2026-07-31 at SHA `59f598c5`. The current
main HEAD is `5dd1e881`. Between those two points:
- 9 ADRs were ratified (0028–0036)
- PRs #384, #388, #392, #394, #395 were merged
- CONSTITUTION.md and ROADMAP_V2.md were authored
- The ledger claims 0 unassigned files, but 7 initiatives (above) are not in it

**AUTHORITY_MAP.md** does not include CONSTITUTION.md or ROADMAP_V2.md. The
highest-level design artifact is not yet recognized by the authority system.

**BLUEPRINT.md** predates ADR 0017, ADRs 0027–0036, CONSTITUTION.md, and
ROADMAP_V2.md. Its honesty ledger section lists "ComfyUI not running" — the
RunPod PR (#306) represents a different architectural direction, but BLUEPRINT
has not been updated.

### 3.5 — Contradictory Decisions (Potential)

| Claim A | Claim B | Resolution |
|---|---|---|
| ADR 0019: "Open WebUI study-only" | ADR 0027: "Open WebUI is daily-driver shell" | RESOLVED — 0027 supersedes 0019(d7) |
| BLUEPRINT: "Image Studio waits for ComfyUI" | #306 RunPod PR: "RunPod as image worker" | UNRESOLVED — #306 is DRAFT/BLOCKED; BLUEPRINT not updated |
| ROADMAP.md: Phase/Gate numbering | ROADMAP_V2.md: M1-M6 milestones | UNRESOLVED — V2 proposed but ROADMAP.md still canonical per ADR 0020 |

### 3.6 — Concepts Referenced But Never Defined

| Term | Used in | Defined? |
|---|---|---|
| "Resume Loop" (capitalized, as product) | CONSTITUTION, BLUEPRINT, NORTH_STAR, ROADMAP_V2, multiple ADRs | PARTIAL — BLUEPRINT defines it; no formal specification |
| "Kitty Console" (capitalized, as product surface) | ROADMAP_V2, CONSTITUTION | DEFINED — ROADMAP_V2 Section 0, CONSTITUTION I.5 |
| "Builder Work projection" | ROADMAP_V2, multiple ADRs | IMPLIED — no formal schema |
| "Execution receipt" | CONSTITUTION, KITTY_PRODUCT_ARCHITECTURE, ADR 0032 | DEFINED — KITTY_PRODUCT_ARCHITECTURE Section 10 |
| "Honest state" (five-value capability) | CONSTITUTION, KITTY_PRODUCT_ARCHITECTURE, ADR 0029 | DEFINED — ADR 0029, KITTY_PRODUCT_ARCHITECTURE Section 4 |
| "Capability Manifest" | CONSTITUTION, ADR 0029, KITTY_PRODUCT_ARCHITECTURE | DEFINED — ADR 0029, KITTY_PRODUCT_ARCHITECTURE Section 4 |

### 3.7 — Implementation With No Governing Decision

| Implementation | Concern |
|---|---|
| `sanitized_env()` in `scripts/openwebui_tool/common.py` | No ADR for environment isolation; ADR 0033 references it but the sanitization was implemented before the ADR |
| `builder_queue.db` recovery semantics | Proven in `phase1-1-builder-recovery-proof.md` but no ADR defines the durability contract (ADR 0021 covers proactive execution, not crash recovery) |
| `gateway/builder_adapters.py` | ADR 0036 calls for its removal as "unnecessary wiring" — removal documented but not yet executed |

### 3.8 — Decisions With No Implementation

| Decision | Implementation status |
|---|---|
| ADR 0028 (commodity software precedence) | Applied (Open WebUI, LiteLLM, assistant-ui) but legacy shell scripts not yet retired per ADR 0030 |
| ADR 0030 (repository simplification) | 43 files archived in commit `4c0bf06b`; full simplification deferred |
| ADR 0029 (capability manifest single truth) | `runtime_manifest.py` exists; not yet adopted by all consumers |
| ADR 0032 (evidence-backed claims, full) | Evidence requirements defined; not fully enforced across all claim types |
| ADR 0034 (memory consolidation to 3 stores) | Policy defined; storage consolidation deferred past M5 |

### 3.9 — Circular References

- `CODEBASE_MAP.md` references itself (minor formatting artifact)
- `ROADMAP.md` → `DISPOSITION_LEDGER.md` → `ROADMAP.md` (bidirectional reference: ledger maps to roadmap, roadmap references ledger). This is valid mutual dependency for now but means both must be updated atomically when phases change.

### 3.10 — Missing Links

| From | To | Why it matters |
|---|---|---|
| `AUTHORITY_MAP.md` | `CONSTITUTION.md` | Highest design artifact has no assigned authority slot |
| `AUTHORITY_MAP.md` | `ROADMAP_V2.md` | V2 roadmap not recognized in authority system |
| `DISPOSITION_LEDGER.md` | `v2-driver-baseline-v1.json` | First V2 initiative not in disposition ledger |
| `DISPOSITION_LEDGER.md` | `ktl-002-measured-learning-boundary-v1.json` | Initiative exists, unaccounted for |
| `DISPOSITION_LEDGER.md` | `phase1-smoke-recovery-v1.json` | Initiative exists, unaccounted for |
| `ROADMAP.md` | `ROADMAP_V2.md` | ROADMAP.md should acknowledge V2 as proposed successor |
| `ADRs 0028–0036` | `BLUEPRINT.md` | BLUEPRINT predates these ADRs; their ratifications invalidate some BLUEPRINT claims |
| `BLUEPRINT.md` | ADR 0027, 0033 | Open WebUI shell acceptance postdates BLUEPRINT's chat-is-the-spine assumption |

---

## 4. Knowledge Density Map

Which documents are most densely connected? (In-degree + out-degree from
cross-reference analysis.)

| Rank | Document | Connections | Role |
|---|---|---|---|
| 1 | `DISPOSITION_LEDGER.md` | 136+ items indexed | Universal index |
| 2 | `AUTHORITY_MAP.md` | 20+ authorities defined | Ownership router |
| 3 | `ROADMAP.md` | 30+ issue/PR/doc refs | Forward-looking sequence |
| 4 | `open-session-audit-2026-08-01.md` | 30+ issue refs | Issue landscape snapshot |
| 5 | `KITTY_PRODUCT_ARCHITECTURE.md` | 15+ ADR/doc refs | Formal architecture |
| 6 | `BLUEPRINT.md` | 12+ ADR/doc refs | Product direction |
| 7 | `CONSTITUTION.md` | 12 source documents consolidated | Unified principles |
| 8 | `ROADMAP_V2.md` | 8 doc refs | Proposed V2 sequence |
| 9 | `ARCHITECTURE.md` | 7 subsystem refs | Current system shape |
| 10 | `ALIGNMENT_MAP.md` | 5 doc/phase refs | Layering rules |

---

## 5. Minimum Architectural-Continuity Graph

Builder must maintain a bounded set of node types and relationships to preserve
architectural memory. The minimum graph is:

### 5.1 — Node Types (7)

1. **ADR** — one file per durable decision. Carries: number, status, date,
   supersedes, amends.
2. **ROADMAP** — one active roadmap. Carries: milestones/phases, acceptance
   criteria, dependencies.
3. **INITIATIVE** — one manifest per bounded deliverable. Carries: id, packets,
   roadmap alignment, autonomy class.
4. **DOCUMENT** — one top-level architecture or governance doc. Carries: role,
   authority scope, date, SHA.
5. **RESEARCH** — one investigation per bounded question. Carries: date, findings,
   absorbed-by reference.
6. **ISSUE** — one GitHub issue. Carries: number, title, state, labels.
7. **PR** — one GitHub pull request. Carries: number, title, state, base/head SHA,
   linked issues.

### 5.2 — Relationship Types (10)

| Relation | Direction | Meaning |
|---|---|---|
| `supersedes` | A → B | A replaces B as authority |
| `amends` | A → B | A modifies specific clauses of B |
| `extends` | A → B | A adds detail to B without changing B |
| `documents` | DOC → CONCEPT | DOC provides the canonical definition |
| `implements` | PACKET/PR → ADR/ROADMAP | PACKET/PR realizes a decision |
| `verifies` | RESEARCH → IMPLEMENTATION | RESEARCH proves correctness |
| `depends-on` | A → B | A cannot be resolved without B |
| `blocks` | A → B | A prevents B from proceeding |
| `enables` | A → B | A unblocks B's dependency |
| `aligns-to` | INITIATIVE → ROADMAP | INITIATIVE maps to a specific milestone/phase |

### 5.3 — Continuity Rules

1. Every ADR must declare its `supersedes`/`amends`/`extends` relationships in
   its header. No implicit supersession.
2. Every INITIATIVE must declare its `aligns-to` roadmap milestone. No unmapped
   initiative may be executed.
3. Every DOCUMENT in the authority set must appear in `AUTHORITY_MAP.md`.
4. `DISPOSITION_LEDGER.md` must be updated at every ADR ratification, roadmap
   update, or initiative creation.
5. RESEARCH findings that become architectural decisions must produce an ADR.
   Research that does not must be explicitly marked as BACKLOG or SUPERSEDED.
6. When a phase scheme changes (e.g., ROADMAP.md → ROADMAP_V2.md), every
   initiative's `aligns-to` reference must be re-evaluated.
7. An ADR may not be accepted until all ADRs it `supersedes` or `amends` are
   explicitly cited in its header.

### 5.4 — Recommended Immediate Actions

These are not implementation tasks. They are knowledge-graph repair operations
that the next packet author or reviewer must perform before the graph can be
trusted for autonomous routing.

| Priority | Action | Why |
|---|---|---|
| P0 | Add CONSTITUTION.md to AUTHORITY_MAP.md | Highest artifact has no authority slot |
| P0 | Add ROADMAP_V2.md to AUTHORITY_MAP.md | Proposed roadmap unrecognized |
| P1 | Update DISPOSITION_LEDGER.md to include all 7 orphan initiatives | Ledger claims 0 unassigned |
| P1 | Resolve ROADMAP.md vs ROADMAP_V2.md phase scheme | Builder cannot align to two schemes |
| P1 | Align DISPOSITION_LEDGER phase references to whichever scheme survives | Initiatives become unmapped |
| P2 | Update BLUEPRINT.md to acknowledge ADRs 0027–0036 and RunPod direction | BLUEPRINT claims are stale |
| P2 | Verify which KTF-004 artifacts are canonical | Four manifests + four research docs for one concern |
| P3 | Add formal ADR for Builder crash-recovery durability contract | Implementation exists; no governing decision |
| P3 | Mark packet 021 and 022 as retired (not just SUPERSEDED) since 023/024 exist | Duplicate files confuse the registry |
