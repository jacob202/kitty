# Architecture Ratification — 2026-08-06

**Authority:** Jacob-supervised architectural adjudication. Escalated from the
twelve open architectural questions left by PR #408 (branch
`closeout/2026-08-05-architecture-reconciliation`).

**Method:** Each question was decided against live repository authority (ADRs
0001–0036, the Constitution v1, the active roadmap, the closeout branch's
evidence artifacts, the Builder queue state, the knowledge graph, the
continuity recovery ledger, and the disposition ledger), not against proposal
prose, handoff narration, planner preference, or document header claims.

**Evidence cutoff:** HEAD `d3c82748` (2026-08-05), closeout branch at
`a6fa3c3c`.

No proposal was silently promoted into accepted architecture. Every
recommendation names the exact ADR, document change, or investigation required.

---

## Decision 1 — Open WebUI

**Question:** Is Open WebUI a replaceable shell, permanent UI, or primary
supported UI with technically replaceable contracts?

### Recommendation

Open WebUI is **the primary supported UI with technically replaceable
contracts.** It is not a permanent UI (the replaceable-shell boundary is
enforced in code) and is no longer merely "replaceable shell" in the sense of
an optional experiment — it is the daily-driver default.

### Evidence

- **ADR 0027** (2026-08-02): Accepted Open WebUI as Kitty's replaceable
  daily-driver shell. The decision states: "Open WebUI may be installed and
  operated as Kitty's local daily-driver **shell**, subject to these
  boundaries." Boundaries: Kitty remains authority, Open WebUI remains
  replaceable, local single-user by default, no ambient credential inheritance,
  explicit and reversible upgrades, end-to-end success proofs.

- **ADR 0033** (2026-08-05): Hardened the boundary with specific rules:
  environment isolation in code (`sanitized_env()`), auth disabled by
  configuration (not database repair), smoke tests that prove real content,
  version pinning, and "Open WebUI state is not Kitty state."

- **Constitution v1 Article I.2**: "Open WebUI is the primary daily-driver
  shell." Article I.3: "The Console is the operator surface: configuration,
  Builder state, diagnostics, and approvals. It is a thin view over the
  Gateway's query and command API. It is not a competing chat engine."

- **ROADMAP_V2.md M1–M6**: Sequences Open WebUI as primary shell (M1) before
  Console re-roles to operator surface (M2).

- **PR #384** (merged): Onboarding implementation exists on disk.
  `scripts/openwebui_local.py` provides bootstrap, verify, and management
  commands. The PYTHONPATH sanitization and duplicate-account repair are
  addressed in code.

- **Live acceptance gap** (`.claude/STATE.md`): "Live acceptance
  (`bootstrap --accept-charges` on the real Mac) was never recorded run."

### Alternatives rejected

- **Permanent UI**: Rejected. ADR 0027 rule 2 explicitly states Open WebUI
  "remains replaceable." The Next.js Console is the verified rollback target.
- **Bare replaceable shell (no primary status)**: Rejected. The Constitution
  and ADR 0027 both designate it "primary daily-driver shell." The Kitty UI is
  not competitive as a chat surface per the evidence in ADR 0027 context
  ("the existing Kitty UI has not met that bar reliably").

### Consequence

The Next.js Kitty Console becomes the operator surface (M2), not a competing
chat engine. Open WebUI's internal database is the shell's concern per ADR
0033 rule 5. Replaceable-shell contracts (Gateway OpenAI-compatible endpoints,
model discovery) become the stable integration surface.

### Reversibility

High. ADR 0027 rule 5: "preserve a tested rollback to Kitty's own UI." The
Next.js Console code is not deleted — it is re-roled. Rollback is `./kitty up`
without Open WebUI bootstrap.

### Confidence

Very high (0.95). Two ratified ADRs and the Constitution converge on the same
answer. The only open question is live acceptance proof (M1-01/M1-02 packets).

### Document change required

**None.** ADRs 0027 and 0033 plus Constitution Article I.2 already ratify this
decision. The open question is execution, not governance.

---

## Decision 2 — Open Brain

**Question:** Adopt, reject, investigate, or limited pilot as
storage/interoperability layer?

### Recommendation

**Investigate — with a specific annual checkpoint.** Do not adopt. Do not
pilot. Do not reject the architectural decomposition.

### Evidence

- **ADR 0031** (2026-08-05): "The architecture migration analysis is accepted
  as a structural target." But "Migration to Open Brain, Ringer, or Open
  Engine is deferred until each project demonstrates: stable API surface with
  documented contracts, proven maturity (not alpha/pre-release), compatibility
  with Kitty's local-first, single-user, Apple Silicon operating environment,
  clear license terms compatible with Kitty's use."

- **Architecture migration analysis** (closeout branch): Found that Open Brain
  would absorb approximately 60% of Kitty's current infrastructure code. But
  the analysis explicitly states: "Exact API surfaces, schema, and maturity
  are UNKNOWN."

- **ADR 0034**: Separated memory policy (Kitty-owned) from storage
  implementation (replaceable). This is the correct seam regardless of whether
  Open Brain fills the storage role.

- **ADR 0036**: Builder infrastructure is preserved and refactored internally
  along the responsibility map — which makes eventual migration lower-risk
  without depending on vapor.

- **Constitution Article I**: Does not mention Open Brain. The four permanent
  subsystems are Gateway, Open WebUI, Builder, LiteLLM. Open Brain is not a
  subsystem.

### Alternatives rejected

- **Adopt**: Rejected. The project's maturity is unproven. ADR 0031 already
  decided this.
- **Reject entirely**: Rejected. The three-part responsibility map (Open Brain
  = memory storage, Ringer = worker orchestration, Open Engine = durable
  execution) is architecturally correct. Rejecting the map entirely would lose
  a valuable code-organization guide.
- **Limited pilot**: Rejected. Storage migration piloting when the target API
  is unknown risks data loss with no proportional benefit.

### Consequence

Kitty improves storage independently per ADRs 0030 and 0034. The annual
checkpoint (2027-08-05, or upon stable release announcement) re-evaluates Open
Brain maturity. Internal refactoring along the responsibility map makes future
migration lower-risk.

### Reversibility

High. If Open Brain never materializes, Kitty's independent infrastructure
works (ADR 0031: "No impact.").

### Confidence

High (0.90). ADR 0031 is clear. The only unknown is when/if Open Brain
matures.

### Document change required

**None.** ADR 0031 already records this decision. Add an annual checkpoint
event to Builder's calendar. ADR 0031 follow-up work says "Evaluate Open Brain
API maturity annually or when a stable release is announced" — no change
needed.

---

## Decision 3 — Knowledge and Memory

**Question:** Preserve the existing KB, simplify storage, replace storage, and
what must remain Kitty-owned?

### Recommendation

**Simplify storage to 3 stores.** Kitty must own: memory policy, context
assembly, confidence decay, consolidation timing, sensitivity classification,
and relevance decisions. The StorageAdapter pattern must be the sole
abstraction boundary. The existing `~/kb` directory (Jacob's personal
knowledge base) is exempt from this decision — it is not a Kitty storage
subsystem.

### Evidence

- **ADR 0034** (2026-08-05): "Memory policy is a Kitty concern. Storage
  implementation is an open decision." Consolidation target is 3 stores
  (SQLite + single vector + JSONL). The `StoreAdapter` ABC pattern is
  validated as the correct architectural seam. mem0 dependency should be
  removed in favor of direct embedding management.

- **ADR 0030** (2026-08-05): Repository simplification is a strategic
  priority. Target: 9 memory stores → 3; 8 subsystem SQLite databases → 1–3
  consolidated; 27 Builder modules → refactored subpackage. "Simplification
  means removal, consolidation, or retirement — never adding a parallel path."

- **Architecture honesty audit** (2026-07-24): Memory system is "2,800+ lines
  across 7+ files" and "the most architecturally mature subsystem — better
  than the builder queue."

- **KITTY_MASTER_PROGRAM.md P6**: Storage consolidation is explicitly
  sequenced last (P6), gated on P1–P5 being green. "Consolidating before the
  system works consolidates bugs."

### What must remain Kitty-owned

1. **Memory policy** — what surfaces versus what is filtered (privacy gates,
   sensitivity classification).
2. **Context assembly** — what is relevant to the current context (ADR 0004).
3. **Confidence decay and fact correction** — temporal knowledge graph with
   deprecation chains.
4. **Consolidation timing** — when consolidation and dreaming occur (session
   end, nightly cron).
5. **Sensitive-content rewriting** — how sensitive content is rewritten before
   surfacing.

### Alternatives rejected

- **Preserve existing KB unchanged**: Rejected. Nine stores across mem0,
  ChromaDB, 5 SQLite DBs, 2 JSONL files, and mempalace are excessive for a
  local-first single-user assistant. ADR 0030 and ADR 0034 both target
  consolidation.
- **Replace storage with Open Brain**: Rejected per Decision 2 and ADR 0031.
  Open Brain maturity is unproven.
- **Consolidate to a single database**: Rejected per ADR 0034 ("Three stores
  is the minimum practical number.") Different access patterns require
  different storage shapes.

### Consequence

Consolidation proceeds during P6, after P1–P5 are green. mem0 is removed.
Single vector backend chosen (ChromaDB keep or SQLite-vec). The StoreAdapter
pattern is strengthened, not bypassed. The KB simplification is migration work
with data integrity risk — additive migrations, shadow reads, and per-phase
rollback are required per Constitution Article II.6.

### Reversibility

Medium. Additive migrations with shadow reads and documented rollback per
phase make reversal possible, but data migration is inherently the hardest
operation to reverse. The Constitution's migration policy (Article II.6) must
be followed.

### Confidence

High (0.90). ADRs 0030 and 0034 agree on the target. The remaining open
question (SQLite-vec vs ChromaDB) is deferred to implementation evaluation.

### Document change required

**Minor: ADR 0034 follow-up work section already lists all required steps.**
No new ADR needed. Execute the listed follow-up: remove mem0, choose vector
backend, consolidate SQLite stores, preserve StoreAdapter.

---

## Decision 4 — Builder

**Question:** Execution control plane, engineering organization, workspace
operator, or layered combination with explicit boundaries?

### Recommendation

**Layered combination with explicit boundaries.** Builder is the **execution
control plane** (ADR 0017) as its core role, with an **internal refactoring**
along the responsibility map (ADR 0036) that separates generic execution
infrastructure from Kitty-specific product logic. The "engineering
organization" design (BUILDER_ORGANIZATION.md) is an unreviewed proposal, not
an accepted architecture. The "workspace operator" framing is subsumed by the
control plane role.

### Evidence

- **ADR 0017** (2026-07-17, amended 2026-07-26): "KittyBuilder is the
  execution control plane." Owns: initiatives, packets, tasks, attempts,
  leases, runs, reviews, recovery, budgets, publication. Does not invent
  roadmap, make unresolved architecture decisions, own personal stores, or
  permit worker self-approval.

- **ADR 0036** (2026-08-05): Refactoring target: `gateway/builder/` subpackage
  holds execution infrastructure; product logic stays at top level;
  `builder_adapters.py` deleted. "No migration to external workflow engines is
  planned."

- **Constitution Article I.3**: "Builder is the governed execution engine. It
  is a coordinator of replaceable specialist agents, not a coding agent."

- **BUILDER_ORGANIZATION.md** (closeout branch): Marked "Status: Design — not
  yet implemented." Proposes an engineering organization with Chief Architect,
  Reviewer, Implementer, etc. This is an input to Builder's evolution, not an
  accepted architecture. It was uncommitted at the time of the closeout
  branch.

- **BUILDER_V2.md** (closeout branch): "Status: Replacement blueprint — not
  yet implemented." Proposes a redesign with a "coordination kernel" and
  "artifact graph." Also uncommitted, unreviewed.

- **Builder core runtime audit** (2026-08-01): 1000+ passing tests. Proven
  crash recovery, stale lease handling, budget exhaustion with operator grant,
  cancellation, worktree removal. One defect found and fixed (worker
  self-crash retry deadlock).

### The explicit boundaries

1. **Execution infrastructure** (generic, candidate for future extraction):
   task state machine, leases, attempts, events, runtime, worker session,
   runner, loop.
2. **Product logic** (permanently Kitty): contract format, scope, ISC,
   reporting, operator commands, CLI, brief conventions.
3. **Remove**: `builder_adapters.py` as unnecessary wiring.
4. **Not Builder**: product intent, memory policy, routing, personal stores,
   roadmap authority. Never a permanent project-manager agent. Never joins
   Gateway tables into Builder's state machine.

### Alternatives rejected

- **Engineering organization (as primary model)**: Rejected in its current
  form. BUILDER_ORGANIZATION.md is an unreviewed design. Its concepts (Chief
  Architect, Reviewer, Implementer roles) may inform future Builder evolution,
  but Builder's ratified role is execution control plane, not an org chart.
- **Workspace operator only**: Rejected. Builder owns much more: initiatives,
  packets, evidence, review, publication, recovery, budgets. It is the
  execution truth store, not a thin workspace manager.
- **Flat module namespace (no refactoring)**: Rejected per ADR 0036. 27 flat
  modules with `builder_adapters.py` indirection is the problem being fixed.

### Consequence

ADR 0036's refactoring proceeds as designed. BUILDER_ORGANIZATION.md and
BUILDER_V2.md are preserved as design inputs, not accepted architecture.
Builder remains the SQLite-backed control plane the audit proved. The
engineering-organization concepts are valuable for worker role design but must
not replace the ratified control-plane boundary.

### Reversibility

The refactoring is behavior-identical with test-gated moves. Reversibility is
high (revert moves). BUILDER_ORGANIZATION.md and BUILDER_V2.md as proposals
are not reversible — they haven't been implemented.

### Confidence

High (0.92). ADR 0017 and ADR 0036 are clear and ratified. The Constitution
reinforces. The only unknown is whether the organization/V2 proposals should
evolve into ADRs after review.

### Document change required

**ADR 0036 is sufficient.** BUILDER_ORGANIZATION.md and BUILDER_V2.md should
be dispositioned as PROPOSED/DESIGN (added to the disposition ledger) with an
explicit note: "Not ratified. Concepts may inform ADR amendments. Implementation
requires separate ADR."

---

## Decision 5 — Roadmap Authority

**Question:** Which document is authoritative, and what is the exact
relationship between ROADMAP.md, ROADMAP_V2.md, and KITTY_MASTER_PROGRAM.md?

### Recommendation

**ROADMAP.md is the sole ratified active authority.** ROADMAP_V2.md is a
ratified target plan — accepted architecture, not execution schedule.
KITTY_MASTER_PROGRAM.md must be explicitly re-designated as a **derived
synthesis** rather than an authority. The three-document pile is a governance
risk.

### Evidence

- **ADR 0020** (2026-07-26): "One Canonical Roadmap and Planning Ownership."
  Ratified `docs/ROADMAP.md` as the single active authority.

- **AUTHORITY_MAP.md**: Lists `docs/ROADMAP.md` as the roadmap authority.
  Owner: "The one active forward-looking sequence and phase exit criteria."
  Does not list ROADMAP_V2.md or KITTY_MASTER_PROGRAM.md as authorities.

- **ROADMAP_V2.md**: Self-describes as "Proposed (v2 target architecture)" and
  explicitly states "The current `docs/ROADMAP.md` … remain authority; this
  doc sequences their delivery as releasable milestones."

- **KITTY_MASTER_PROGRAM.md**: Claims "Supersedes `docs/ROADMAP.md` and
  `docs/ROADMAP_V2.md` as the single canonical delivery sequence." This claim
  contradicts ADR 0020, AUTHORITY_MAP.md, and the Constitution (which
  references ROADMAP_V2 as a ratified source). A document cannot supersede two
  other documents by self-declaration.

- **Constitution ratification table**: Lists `ROADMAP_V2 (2026-08-05)` as a
  ratified source, specifically for "Small packets, one owner, leave repo
  working." References `ROADMAP_V2` operating principles, not
  KITTY_MASTER_PROGRAM.

- **DISPOSITION_LEDGER.md**: Uses ROADMAP phase scheme (Gate 0, Phase 1–4),
  not KITTY_MASTER_PROGRAM P0–P8 scheme. The ledger was written 2026-07-31
  and predates both ROADMAP_V2 and KITTY_MASTER_PROGRAM.

### The exact relationship

```
ROADMAP.md (ACTIVE authority, per ADR 0020)
  └─ PHASED INTO → ROADMAP_V2.md (ratified target plan, M1–M6 milestones)
                     └─ DERIVED FROM → KITTY_MASTER_PROGRAM.md (synthesis document)
```

- **ROADMAP.md** owns: active outcomes, phase exit criteria, "what is being
  worked on now."
- **ROADMAP_V2.md** owns: the V2 target architecture delivery sequence,
  milestone targets, packet catalog, explicit not-in-V2 scope.
- **KITTY_MASTER_PROGRAM.md** is a synthesis document: it merges ROADMAP,
  ROADMAP_V2, the extension backlog, the product architecture, and continuity
  recovery into a single dependency-ordered program. It is a derived work
  product, not an authority. Its value is the complete picture; its risk is
  self-declared supremacy.

### Alternatives rejected

- **KITTY_MASTER_PROGRAM.md as sole authority**: Rejected. ADR 0020 already
  ratified ROADMAP.md. AUTHORITY_MAP.md already names ROADMAP.md. The
  Constitution references ROADMAP_V2, not MASTER_PROGRAM. A document cannot
  supersede ratified ADRs by self-declaration.
- **ROADMAP_V2.md as sole authority**: Rejected. ROADMAP_V2.md self-describes
  as "Proposed" and defers to ROADMAP.md as authority. It is a target plan,
  not the active schedule.
- **Keep all three as equal authorities**: Rejected. Three competing
  authorities with different numbering schemes and different statuses (one
  ratified, one proposed, one self-declared) is the problem being solved.

### Consequence

Workers and agents consult ROADMAP.md for active priority and phase exit
criteria. They consult ROADMAP_V2.md for the V2 target sequence and packet
catalog. KITTY_MASTER_PROGRAM.md is read for the complete dependency map and
cross-reference, but its authority claims are explicitly bounded by this
decision. The DISPOSITION_LEDGER.md must be updated to reference both
ROADMAP.md (current schedule) and ROADMAP_V2.md (V2 milestones).

### Reversibility

High. If KITTY_MASTER_PROGRAM.md proves more maintainable, an ADR amendment to
ADR 0020 can promote it. The relationship is an explicit link, not a deletion.

### Confidence

High (0.90). ADR 0020 and AUTHORITY_MAP.md agree. KITTY_MASTER_PROGRAM.md's
self-supersession claim is the only contradictory signal, and it is the weaker
source (self-declared document vs ratified ADR).

### Document change required

1. **ROADMAP.md**: Add an explicit note referencing ROADMAP_V2.md as the V2
   target plan (not replacing ROADMAP.md's active authority).
2. **ROADMAP_V2.md**: No change — already correctly describes its relationship
   to ROADMAP.md.
3. **KITTY_MASTER_PROGRAM.md line 5**: Replace "Supersedes `docs/ROADMAP.md`
   and `docs/ROADMAP_V2.md` as the single canonical delivery sequence" with
   "Derived synthesis of `docs/ROADMAP.md` (active authority), `docs/ROADMAP_V2.md`
   (V2 target plan), and the extension backlog into a single dependency-ordered
   program. Authority chain: ROADMAP.md (ADRs 0020, 0028–0036, Constitution)
   defines active priority; ROADMAP_V2.md defines V2 milestone targets; this
   document synthesizes both into one complete reference."
4. **AUTHORITY_MAP.md**: Add `ROADMAP_V2.md` under `planning_inputs` concern
   with owner "V2 milestone targets, per Constitution v1." Add
   `KITTY_MASTER_PROGRAM.md` as "derived synthesis; not an independent
   authority."
5. **DISPOSITION_LEDGER.md**: Update header to reference both ROADMAP.md
   (active) and ROADMAP_V2.md (V2 milestones). Add KITTY_MASTER_PROGRAM.md,
   ROADMAP_V2.md, BUILDER_ORGANIZATION.md, and BUILDER_V2.md to the inventory.

---

## Decision 6 — Constitution Authority vs ADR Authority

**Question:** Which governs when they conflict? Can the Constitution be
amended by ADR, and vice versa?

### Recommendation

**The Constitution is the highest authority.** An ADR may amend the
Constitution only through the Amendment Policy (Article VII.5). A new ADR that
contradicts the Constitution without explicitly amending it is invalid. The
Constitution may not contradict a ratified ADR without explicitly superseding
it. When ambiguity exists, the Constitution governs.

### Evidence

- **Constitution Article VII.5**: "This Constitution may be amended by an
  Architectural Decision Record (ADR) that: 1. Cites the specific Article and
  Section it amends. 2. Demonstrates that the amendment does not create
  contradictory rules. 3. Records the evidence that necessitated the change. A
  Constitution amendment is the highest-severity architectural decision. It
  should be rare, explicit, and backward-compatible with existing rules unless
  the amendment explicitly supersedes them."

- **Constitution preamble**: "Highest-level design artifact. Every future
  Builder packet, ADR, roadmap, feature, worker, reviewer, and planner must
  justify itself against this document before it is accepted. No other
  document may contradict it."

- **Constitution ratification table**: Lists ADRs 0003, 0017, 0027, 0028,
  0029, 0032, 0033, 0034, 0036 as sources. The Constitution was ratified the
  same day as ADRs 0028–0036. All nine new ADRs are listed as sources — none
  contradict.

- **AUTHORITY_MAP.md**: Lists `docs/DECISIONS.md` → ADRs as the authority for
  "decisions." Lists no explicit "constitution" authority (the Constitution
  was uncommitted at the time of AUTHORITY_MAP.md's last update). Conflict
  rule 2: "An accepted ADR beats an older architecture or plan claim."

### The hierarchy

```
Constitution v1 (highest)
  └─ ADRs 0001–0036 (each governs its specific domain)
       └─ ARCHITECTURE.md (current runnable shape, derives from ADRs)
       └─ ROADMAP.md (active sequence, per ADR 0020)
       └─ ROADMAP_V2.md (V2 target plan)
  └─ AUTHORITY_MAP.md (routes to owners, not itself a source of truth)
```

An ADR amends the Constitution by citing the Article and Section (Article
VII.5). A new ADR that contradicts the Constitution without citing an
amendment is a governance defect. An ADR that contradicts an older ADR must
explicitly supersede it (standard ADR practice). The Constitution may not be
amended by a non-ADR document (roadmap, plan, master program, blueprint).

### Alternatives rejected

- **ADRs at the same level as the Constitution**: Rejected. The Constitution
  preamble says "No other document may contradict it." The Amendment Policy
  (VII.5) defines ADRs as the amendment mechanism, not as equals.
- **Constitution is subordinate to ADRs**: Rejected. The Constitution was
  ratified after ADRs 0001–0036 and explicitly references them. It could have
  superseded any that it disagreed with. None were superseded.
- **AUTHORITY_MAP.md resolves conflicts**: Rejected. AUTHORITY_MAP.md is a
  routing document ("routes a clean agent to the owner of each kind of
  truth"), not a governance document. It does not define authority hierarchy.

### Consequence

Future ADRs must check for Constitution consistency. A Constitution amendment
ADR must cite Article + Section. Standard ADRs (non-amendment) may not
contradict the Constitution. The AUTHORITY_MAP.md must be updated to list the
Constitution as the highest authority.

### Reversibility

Low. The Constitution's own Amendment Policy is the mechanism to change this.
Constitutional change is explicitly "the highest-severity architectural
decision." This is by design.

### Confidence

High (0.95). The Constitution's own text is unambiguous. The only gap is that
AUTHORITY_MAP.md doesn't list the Constitution — a routing defect, not a
governance defect.

### Document change required

1. **AUTHORITY_MAP.md**: Add a governance concern: `constitution` with
   authority `docs/CONSTITUTION.md`, owning "Highest architectural authority.
   All ADRs, roadmaps, and plans must be consistent with it. Amended only by
   explicit Constitution-amendment ADRs per Article VII.5."
2. **Constitution v1**: Re-ratify with committed SHA. The current v1 is on the
   closeout branch. It must be committed to `main` with its constitutional
   authority claim intact.

---

## Decision 7 — Phase Numbering

**Question:** What is the single canonical phase-numbering scheme?

### Recommendation

**ROADMAP.md's Gate 0 / Phase 1–4 scheme is the active authority.**
ROADMAP_V2.md's M1–M6 scheme is the V2 milestone scheme and is supplementary.
KITTY_MASTER_PROGRAM.md's P0–P8 scheme is a synthesis convenience and must not
appear in Builder manifests, packet IDs, or the disposition ledger.

### Evidence

- **ROADMAP.md** uses: Gate 0 (Repository Recovery), Phase 1 (Trustworthy
  Proof), Phase 2 (Life-First Daily Driver), Phase 3 (Execution Reliability),
  Phase 4 (Product Deepening). This scheme is ratified by ADR 0020.

- **ROADMAP_V2.md** uses: M1 (Daily-driver shell), M2 (Console operator
  surface), M3 (Builder → Work), M4 (Failure/receipts), M5 (Storage
  consolidation), M6 (Iterate & ship). ROADMAP_V2.md is ratified by the
  Constitution.

- **KITTY_MASTER_PROGRAM.md** uses: P0 (Repository Foundation), P1
  (Trustworthy Shell), P2 (Honest State), P3 (Builder → Work), P4 (Open Every
  Morning), P5 (Daily Workflows), P6 (Storage Consolidation), P7 (Product
  Deepening), P8 (Iterate & Ship), plus parallel Lanes A/B/C. This scheme was
  never ratified by any ADR.

- **DISPOSITION_LEDGER.md** assigns to ROADMAP.md outcomes (e.g., "Phase 1.1,
  Phase 2.1"). Initiatives carry IDs like `ktf-001`, `life-first-v1`, etc.
  The `v2-driver-baseline-v1.json` uses M1-01 style packet IDs.

### Which scheme where

| Context | Scheme | Reason |
|---|---|---|
| Active work status and exit criteria | ROADMAP Phase/Gate | ADR 0020 authority |
| V2 target milestones and packet IDs | ROADMAP_V2 M1–M6 | V2 initiative packets use M<n>-<NN> IDs |
| Full dependency map for reading | KITTY_MASTER_PROGRAM P0–P8 | Convenient synthesis only |
| Disposition ledger assignments | ROADMAP Phase X.Y | Matches current ledger entries |
| Builder initiative IDs | Initiative-specific (ktf-*, v2-*, life-first-*) | Existing practice |
| Builder packet IDs (V2) | M<n>-<NN>-<slug> | From ROADMAP_V2 packet catalog |

### Alternatives rejected

- **P0–P8 as canonical**: Rejected. Not ratified. Self-declared in
  KITTY_MASTER_PROGRAM.md which is a synthesis, not an authority.
- **Single unified scheme**: Rejected. ROADMAP.md and ROADMAP_V2.md serve
  different purposes (active schedule vs target plan). Forcing a single scheme
  would lose the distinction.
- **M1–M6 as canonical for all documents**: Rejected. The DISPOSITION_LEDGER
  uses ROADMAP phase numbers. The existing initiatives use their own IDs.
  Renumbering everything is churn with no proportional benefit.

### Consequence

The KITTY_MASTER_PROGRAM.md P0–P8 mapping table is preserved as a valuable
cross-reference but labeled "derived synthesis — use ROADMAP or ROADMAP_V2
schemes in official contexts." New Builder packets use ROADMAP outcome numbers
(e.g., "Phase 1.2") or V2 M<n> numbers (e.g., "M1-09") depending on which
document they implement. The DISPOSITION_LEDGER uses ROADMAP phase numbers.

### Reversibility

High. A future ADR could ratify a unified scheme. The P0–P8 mapping table in
KITTY_MASTER_PROGRAM.md already provides the translation.

### Confidence

High (0.88). ADR 0020 gives ROADMAP.md authority. The Constitution
ratification table gives ROADMAP_V2.md status. The P0–P8 scheme's only claim
to authority is KITTY_MASTER_PROGRAM.md's self-declaration, which is rejected
per Decision 5.

### Document change required

1. **KITTY_MASTER_PROGRAM.md**: Add a note to the "Phase Numbering — The
   Merge" section: "This P0–P8 scheme is a derived synthesis for reading
   convenience. The authoritative scheme for active work is ROADMAP.md
   (Gate/Phase/Outcome). The V2 target scheme is ROADMAP_V2.md (M1–M6). Do
   not use P<n> in Builder manifests, packet IDs, or the disposition ledger."

---

## Decision 8 — v2-driver-baseline-v1.json

**Question:** May it be applied now?

### Recommendation

**No, not yet.** Apply only after: (1) ROADMAP_V2.md authority is settled per
Decision 5, (2) M3 write-bounds are approved by Jacob, and (3) the
Constitution is committed to `main`.

### Evidence

- **v2-driver-baseline-v1.json**: Contains 10 packets ordered by dependency.
  Classes: autonomous (CI-verifiable), live (needs Jacob's Mac/paid endpoint),
  operator (requires explicit approval). First 4 packets: M1-01 (bootstrap
  clean-checkout), M1-09 (PYTHONPATH regression test), M1-04 (bootstrap
  idempotency), M1-05 (listener parity).

- **ROADMAP_V2.md §5**: "Jacob reviews this roadmap (M numbering/M scope, esp.
  M3 write-bounds). A planner authors the first
  `docs/initiatives/v2-driver-baseline-v1.json` … Builder runs packet M1-01,
  M1-09 first (autonomous, low risk), parallel to Jacob recording a live
  `--accept-charges` run."

- **Live acceptance gap** (`.claude/STATE.md`): PR #384 is merged but the
  paid/live gate for M1-01 is open — never recorded run. M1-01's acceptance
  requires "Live run: requires Jacob's machine and consent; NOT autonomous."
  The initiative cannot be autonomously executed because M1-01 requires
  Jacob's machine.

- **M3 write-bounds** (`ROADMAP_V2.md` §5 step 1): "Jacob reviews this roadmap
  (M numbering/M scope, esp. M3 write-bounds)." The M3 packets
  (chat→Builder propose/recommend, sandboxed write-to-branch lane) involve
  write authority crossing that requires Jacob's explicit approval before the
  initiative proceeds to those packets.

- **Constitution ratification**: The Constitution is an uncommitted artifact on
  the closeout branch. Per AUTHORITY_MAP.md conflict rule 1, "Live Git, the
  current worktree, GitHub, and supported runtime probes beat prose." The
  Constitution is not live on `main` — it cannot be cited as authority until
  committed.

### Acceptable partial application

- **M1-09 (PYTHONPATH regression test)**: Autonomous and CI-verifiable with no
  live-machine requirement. Could be executed now without Jacob's machine.
- **M2-04 (Console reads Gateway truth)**: Autonomous per the initiative
  manifest: "Fully autonomous and CI-verifiable." Depends on M1-09, which is
  also autonomous.
- **M3-03 (Builder read projection)**: Autonomous per the initiative.
- **M5-01 (storage inventory)**: Autonomous per the initiative.

Total autonomous packets in the first 10: M1-09, M2-04, M2-06, M3-03, M3-06,
M5-01, M5-02, M6-01 = 8 of 10 are autonomous.

### Alternatives rejected

- **Apply immediately in full**: Rejected. M1-01 requires Jacob's machine.
  M1-02 requires paid endpoint acceptance. M1-03 requires Jacob's full-day
  validation. The Constitution's uncommitted status means the initiative's
  authority foundation is incomplete.
- **Reject entirely**: Rejected. The autonomous packets are well-defined,
  CI-verifiable, and low-risk. They can proceed once authority is settled.

### Consequence

After the Constitution is committed and ROADMAP_V2 authority is explicit per
Decision 5, the autonomous packets (M1-09, M2-04, M2-06, M3-03, M3-06, M5-01,
M5-02, M6-01) may proceed. The live packets (M1-01, M1-02, M1-03, M1-04,
M1-05) require Jacob's machine. The operator packets (M3-01, M3-09) require
Jacob's M3 write-bounds review per ROADMAP_V2 §5.

### Reversibility

High. No packet has been executed. The initiative is a JSON manifest that can
be modified, split, or re-sequenced.

### Confidence

High (0.92). The initiative's own acceptance criteria distinguish autonomous
vs live vs operator packets. The open questions are governance (Constitution
commit, ROADMAP_V2 authority stance), not technical.

### Document change required

**v2-driver-baseline-v1.json**: Add a preamble note: "This initiative may not
be autonomously applied in full. Autonomous packets (M1-09, M2-04, M2-06,
M3-03, M3-06, M5-01, M5-02, M6-01) may proceed after Constitution commit and
ROADMAP_V2 authority settlement. Live packets (M1-01, M1-02, M1-03, M1-04,
M1-05) require Jacob's machine. Operator packets (M3-01, M3-09) require
Jacob's M3 write-bounds review per ROADMAP_V2 §5 step 1."

---

## Decision 9 — Builder needs_decision Repair

**Question:** Must needs_decision repair precede every other Builder run?

### Recommendation

**No.** needs_decision repair blocks B8/B9/B10 only — not all Builder work.
The trust-model design (continuity recovery §7) must precede B8 resolution,
but unrelated Builder work (autonomous packets from v2-driver-baseline,
existing active initiatives) may proceed in parallel.

### Evidence

- **Continuity Recovery §3**: Documents the B8 trust hole: 9 attempts (5
  crashed/4 failed), `needs_decision` escalation recorded but never gated.
  B9/B10 are "queued, dependencies unreachable (B8)." The recommendation is
  "Do **not** rerun. Resolve the trust model (§7 deliverable), then explicit
  operator override or retire B8."

- **Continuity Recovery §7**: "Promoted workflow signal:
  `builder-needs-decision-must-gate-loop` … Owner = next task: Design Builder's
  Trust Model (deliverable `docs/plans/builder-trust-model-v1.md`). Do not
  optimize for B8; make the class impossible."

- **ADR 0021** (Proactive Builder Execution): "Continue after an unrelated
  packet failure." Builder already has the semantics to continue unrelated
  work. B8's blocked state should not gate the entire queue.

- **Active Builder initiatives** (DISPOSITION_LEDGER): Multiple ACTIVE
  initiatives exist (kitty-endgame-init-1, kitty-endgame-init-2,
  phase1-1-recovery-proof, ktf-001-resume-proof-v2, life-first-v1,
  packet-027, process-hardening-v1). Most are unrelated to B8.

- **KITTY_MASTER_PROGRAM.md P0.9**: "Design Builder Trust Model … No packet
  can be reassigned to a new worker without an explicit `needs_decision` event
  that survives restart. Independent review verifies the model prevents the B8
  resurrection pattern." This is a P0 priority but gates resolution of B8, not
  all Builder work.

### What needs_decision repair blocks

- B8 (the specific blocked initiative)
- B9 (restart recovery, depends on B8)
- B10 (UI/CLI agreement, depends on B8)
- Any new initiative that touches the same trust-hole class

### What needs_decision repair does NOT block

- Existing active initiatives
- Autonomous v2-driver-baseline packets (M1-09, M2-04, etc.)
- P0 non-Builder work (branch protection, launcher parity)
- Parallel lanes (Image Agent, parked Job Search)

### Alternatives rejected

- **Gate every Builder run on trust-model completion**: Rejected. ADR 0021
  explicitly allows unrelated work to continue after packet failure. B8 is one
  blocked packet among 107. Gating the entire queue would violate the
  architecture.
- **Retire B8 without trust-model design**: Rejected. The forensic analysis
  found a trust hole class. The fix is preventing the class, not closing the
  symptom. B8 itself may be obsoleted as KITTY_MASTER_PROGRAM says ("B8
  clean-checkout trivia as runnable packet: Trust hole; only its trust lesson
  matters").

### Consequence

Builder continues running unrelated work. The trust-model design
(`docs/plans/builder-trust-model-v1.md`, continuity recovery P0 #1) proceeds
as a parallel task. When the trust model is designed and the `needs_decision`
gate is enforced, the operator retires or overrides B8, unblocking B9/B10.

### Reversibility

High. If the trust-model design reveals a systemic issue, broader gating can
be applied retroactively. Starting with narrow gating and expanding is safer
than the reverse.

### Confidence

High (0.90). ADR 0021 and continuity recovery §3 agree. The trust hole is
real but contained.

### Document change required

1. **Continuity Recovery §3**: Add an explicit statement: "B8 blocks B9/B10
   only. Unrelated Builder work proceeds per ADR 0021. Trust-model design
   (P0.9) runs as a parallel task."
2. **KITTY_MASTER_PROGRAM.md P0.9**: Clarify scope: "This gates resolution of
   B8/B9/B10 and future initiatives touching the same trust-hole class. It
   does not gate unrelated Builder work per ADR 0021."

---

## Decision 10 — Capability Manifest vs Open WebUI Home/Resume Loop

**Question:** Must Capability Manifest precede Open WebUI Home and Resume Loop
work?

### Recommendation

**Partially.** A minimal runtime truth endpoint (model availability, Gateway
health, Builder status) must exist before the Home/Resume Loop surfaces
consume truth. The full Capability Manifest v1 (all 13 sections, SSE patches,
compact prompt projection) may proceed in parallel with Home/Resume Loop
extension development. The extensions need truth to render; they do not need
every section of the manifest to be useful.

### Evidence

- **ADR 0029** (Capability Manifest): "Kitty exposes exactly one source of
  runtime truth: the Capability Manifest." But it's DESIGNED, NOT BUILT.
  "Implementation effort (Phase 1 of Product Architecture)."

- **ROADMAP_V2.md M1 exit criteria**: The shell pilot does not require the
  Capability Manifest. M1 acceptance: bootstrap, listen, chat, persist,
  listener parity, full-day pilot. No manifest requirement.

- **ROADMAP_V2.md M2**: Console re-role does require truth from Gateway:
  "Console reads all model/provider/connection truth from the Gateway, not a
  hardcoded catalog" (M2-04). M2-06: "stale/degraded render with reason."

- **KITTY_MASTER_PROGRAM.md P2**: Honest State (which includes Capability
  Manifest v1 as P2.4) is sequenced after P1 (Trustworthy Shell). The
  dependency says: get the shell working (P1), then make it honest (P2). P2.4
  depends on P2.2 (Console reads Gateway truth) but is independent of the
  Resume Loop extensions.

- **P4 extensions** (One Thing card, Morning Briefing, Resume Loop): Depend on
  Gateway projections (`/state/next`, `/state/brief`, `/state/resume`), not
  the full Capability Manifest. P4.3 (Honest State Header) depends on P2.4
  (Capability Manifest).

- **ROADMAP_V2.md**: "M1 must be green before M2 starts." M2 (including
  Capability Manifest P2.4) and the Home/Resume Loop extensions (which live
  mostly in the extension backlog → P4) are independent: the shell must be
  trustworthy before either proceeds, but then the manifest and extensions can
  be built in parallel.

### Minimum runtime truth for Home/Resume Loop

1. Model availability (what models exist and are reachable)
2. Gateway health (is the Gateway up)
3. Builder summary (initiative count, queue depth, attention states)

These three are already partially available (`gateway/runtime_manifest.py`
exists, `builder_status.py` exists). The full Capability Manifest v1 is a
larger effort that should not gate the Home/Resume Loop extensions.

### Alternatives rejected

- **Capability Manifest must be complete before any extension work**: Rejected.
  The P4 extensions need truth, not every section of the manifest. The
  Resume Loop and One Thing card need `/state/next` and project state, not
  ChromaDB health or RunPod status.
- **Home/Resume Loop before any manifest work**: Rejected. The Honest State
  Header extension (P4.3) explicitly depends on the Capability Manifest. The
  manifest provides the truth that prevents "fabricated success" in the UI.
- **Both in strict sequence**: Rejected. They're parallelizable per
  KITTY_MASTER_PROGRAM: "P2.1 (Console decouple) and P2.4 (Capability
  Manifest) are independent — run in parallel."

### Consequence

Minimal runtime truth (model list, Gateway health, Builder summary) is
available through existing endpoints and the partial `runtime_manifest.py`.
P4.1–P4.2 and P4.4–P4.7 can proceed using these endpoints. P4.3 (Honest State
Header) waits for Capability Manifest v1. M2-04 (Console reads Gateway truth)
is the bridge: it replaces hardcoded catalogs with live truth, which is a
prerequisite for both the manifest and the extensions.

### Reversibility

High. Extensions built against minimal endpoints can be upgraded to the full
manifest when it ships.

### Confidence

Medium (0.80). The dependency graph in KITTY_MASTER_PROGRAM.md is clear but
the actual readiness of existing endpoints (`/state/next`, `/state/brief`,
`/state/resume`) for extension consumption is UNVERIFIED. The P4 extensions
assume these endpoints exist.

### Document change required

1. **KITTY_MASTER_PROGRAM.md P4**: Add a dependency note: "P4.3 (Honest State
   Header) depends on P2.4 (Capability Manifest v1). P4.1–P4.2 and P4.4–P4.7
   may proceed with minimal runtime truth endpoints (existing
   `/state/next`, `/state/brief`, `/state/resume`). Verify these endpoints are
   ready before starting P4 extension work."
2. **OPENWEBUI_EXTENSION_BACKLOG.md**: Add a "depends on Capability Manifest"
   tag to the Honest State Header extension (#7).

---

## Decision 11 — Suspicious Wired Modules

**Question:** Which require audit before deletion or retention?

### Recommendation

**Audit all eight before any action.** The audit must determine: (a) is it
imported by `app.py` or a live route, (b) does it have tests, (c) does it
touch a live data store, (d) is it referenced by any ratified ADR or the
Constitution. Based on preliminary evidence, recommend: retain 2, delete 4,
investigate 2.

### Evidence

The architecture decision summary (2026-08-05) lists eight modules with "value
unknown":

| Module | Preliminary evidence | Preliminary recommendation |
|---|---|---|
| `prefetcher.py` | Unknown purpose. No ADR or Constitution reference. | **Investigate.** May be launch-time optimization. |
| `inbox_watcher.py` | Inbox/capture subsystem. May be wired to `gateway/desktop_store.py` or the capture flow per BLUEPRINT.md P3. | **Investigate.** Capture is a Constitution-recognized product capability. |
| `insight_loop.py` | "Effectively empty no-op" per BLUEPRINT.md §5. Insights/dream store "disable visibly." | **Delete** (with evidence of no callers). |
| `life_awareness.py` | Life-first ordering is a ratified principle (ADR 0016, Constitution III.1). The module name suggests it serves this principle. | **Investigate before deletion.** Life-first is core differentiation. |
| `telegram_bot.py` | BLUEPRINT.md §6: "Telegram (off)" but "still wired in `app.py`" per architecture decision summary. | **Delete.** Explicitly disabled per BLUEPRINT. Delete the wiring in `app.py` simultaneously. |
| `antigravity_tools.py` | Name suggests a joke/experiment. No ADR reference. | **Delete** (with evidence of no production callers). |
| `web_tracker.py` | Web monitoring exists as a signal source (`gateway/web_monitor.py` emits `web_monitor` signals per ARCHITECTURE.md). May be related. | **Investigate.** If superseded by `web_monitor.py`, delete. If it IS the web monitor, rename. |
| `self_review.py` | The Builder's independent review requirement (ADR 0017, ADR 0036) prohibits worker self-approval. A module named `self_review` is suspect. | **Delete** (with evidence of no active review path dependency). |

### Audit protocol for each module

1. `grep` for import in `gateway/app.py` and all `gateway/routes/*.py`
2. `grep` for import across all `tests/`
3. Check for database table creation or data store writes
4. Check for ADR or Constitution reference
5. Check for live route registration (HTTP endpoint)
6. If no callers, no tests, no route, no ADR reference → delete
7. If callers exist but value is zero → remove callers, then delete
8. If wired and valuable → retain with test coverage

### Alternatives rejected

- **Delete all eight blindly**: Rejected. `inbox_watcher.py` may serve capture
  (a BLUEPRINT.md P3 product lane). `life_awareness.py` may serve life-first
  ordering (ADR 0016). Deletion without evidence risks removing a wired
  feature.
- **Retain all eight**: Rejected. `insight_loop.py` is explicitly "effectively
  empty no-op." `telegram_bot.py` is explicitly "off." `antigravity_tools.py`
  is named like a joke. Retention without value is the problem ADR 0030
  exists to solve.
- **Audit later**: Rejected. The audit was listed as a decision that "requires
  investigation" on 2026-08-05. The evidence exists to make most decisions
  now; only 3 modules need deeper investigation.

### Consequence

An audit packet (free-exec, deterministic gate: count suspicious modules →
 0) is authored. Each module is dispositioned: retain (with test coverage)
 or delete (with evidence of no callers). The audit produces a record in
`docs/research/suspicious-module-audit-2026-08-06.md`.

### Reversibility

Deletions are reversible via Git. The audit record ensures each deletion's
rationale is preserved.

### Confidence

Medium (0.75). The module names and BLUEPRINT.md evidence give strong signals
for 5 of 8 modules. Three modules (`prefetcher.py`, `inbox_watcher.py`,
`life_awareness.py`) need live code inspection before a final decision.

### Document change required

1. **Architecture decision summary**: Update "Suspicious wired modules audit"
   line to reference the audit packet.
2. **New audit record**: `docs/research/suspicious-module-audit-2026-08-06.md`
   documenting findings and dispositions for all 8 modules.
3. **BLUEPRINT.md §6**: Remove Telegram from "Dies / postponed" if deleted, or
   add explicit "deleted on 2026-08-06" to the BLUEPRINT.

---

## Decision 12 — ADR 0027 vs ADR 0033

**Question:** Do they conflict, amend one another, or require supersession?

### Recommendation

**Neither.** ADR 0033 extends ADR 0027. No conflict exists. No supersession is
required. ADR 0033's own header correctly states "Supersedes: Extends ADR 0027
with operational boundary details" — the word "Supersedes" in the header is
imprecise but the body establishes a correct extension relationship. The
ADR 0033 header should be changed from "Supersedes" to "Extends" for precision.

### Evidence

- **ADR 0027** (2026-08-02): Established the policy decision to use Open WebUI
  as replaceable shell. Seven boundaries: Kitty remains authority, Open WebUI
  remains replaceable, local single-user by default, no ambient credential
  inheritance, explicit reversible upgrades, end-to-end success proofs,
  Builder stays read-only from chat.

- **ADR 0033** (2026-08-05): Hardened the boundary with operational rules.
  Five specific rules: environment isolation enforced in code, auth disabled by
  configuration not database repair, smoke tests prove real content, version
  pinning, Open WebUI state is not Kitty state. Evidence: four specific
  defects documented during onboarding (PYTHONPATH shadowing,
  pending-account trap, SSE smoke ambiguity, persistent config conflicts).

- **ADR 0033 header**: "Supersedes: Extends ADR 0027 with operational boundary
  details."

- **Constitution Article I.2**: References both ADR 0027 and 0033 in its
  ratification table: "Open WebUI is the replaceable shell."

- **KNOWLEDGE_GRAPH.md supersession chain**: "ADR 0027 operational detail →
  ADR 0033 (extended with boundary specs)." The KNOWLEDGE_GRAPH correctly
  identifies this as an extension, not a supersession.

### Conflict analysis

| Concern | ADR 0027 | ADR 0033 | Conflict? |
|---|---|---|---|
| Kitty authority over routing, memory, policy | Retained | Retained | No |
| Replaceable shell | Explicit | Implicit (extends) | No |
| Local single-user | By default | Auth disabled by config | No — 0033 operationalizes 0027 |
| Environment isolation | Not addressed | PYTHONPATH/PYTHONHOME sanitized in code | No — 0033 adds specificity |
| Smoke tests | "Health checks must prove success" | "Smoke tests prove real content, not just HTTP 200" | No — 0033 tightens 0027 |
| Version pinning | "Pin the supported version" | "Version pinned in `scripts/openwebui_local.py`" | No — 0033 specifies |
| Open WebUI state | Not addressed | "Not Kitty state. Kitty does not read from webui.db" | No — 0033 adds boundary |
| Auth system | Not addressed | "Auth disabled by configuration, not database repair" | No — 0033 operationalizes |

No conflict found. ADR 0033 adds operational specificity to ADR 0027's policy.
No rule in 0027 is contradicted by 0033. No rule in 0033 contradicts 0027.

### Alternatives rejected

- **ADR 0033 supersedes ADR 0027**: Rejected. ADR 0033 extends, not replaces.
  ADR 0027's seven policy boundaries remain valid. ADR 0033 adds operational
  hardening. The word "Supersedes" in ADR 0033's header is a labeling error.
- **ADR 0033 is redundant; merge into 0027**: Rejected. ADR 0033 records
  specific operational decisions that emerged from real host execution (4
  documented defects). Merging would lose the evidence chain. The extension
  relationship is valuable provenance.
- **The two ADRs conflict on Open WebUI being permanent vs replaceable**:
  Rejected. ADR 0033 rule 5 explicitly says "If the shell is replaced, Kitty's
  Gateway contracts remain unchanged." Both ADRs agree on replaceability.

### Consequence

No change to either ADR's substance. The ADR 0033 header "Supersedes" →
 "Extends." KNOWLEDGE_GRAPH.md is already correct. The Constitution's
 ratification table correctly references both.

### Reversibility

Not applicable — no decision to reverse. This is a labeling clarification.

### Confidence

Very high (0.98). Line-by-line comparison confirms no conflict. The
KNOWLEDGE_GRAPH, Constitution, and both ADRs agree on the relationship.

### Document change required

1. **ADR 0033 line 5**: Change "**Supersedes:** Extends ADR 0027 with
   operational boundary details" to "**Extends:** ADR 0027 with operational
   boundary details."
2. **No other changes required.**

---

## Disposition

### Decisions safe to ratify immediately (11 of 12)

1. Open WebUI — primary supported UI with replaceable contracts. **Ready.**
2. Open Brain — investigate with annual checkpoint. **Ready.**
3. Knowledge and memory — simplify to 3 stores; Kitty owns policy. **Ready.**
4. Builder — layered combination (control plane + internal refactor). **Ready.**
5. Roadmap authority — ROADMAP.md active authority; ROADMAP_V2.md target plan;
   KITTY_MASTER_PROGRAM.md derived synthesis. **Ready.**
6. Constitution vs ADR authority — Constitution highest; ADR amends via
   Article VII.5. **Ready.**
7. Phase numbering — ROADMAP Gate/Phase scheme canonical; V2 M1–M6
   supplementary; P0–P8 synthesis. **Ready.**
9. Builder needs_decision — blocks B8/B9/B10 only; unrelated work proceeds.
   **Ready.**
10. Capability Manifest vs Home/Resume Loop — minimal truth first; full
    manifest and extensions parallelizable. **Ready.**
11. Suspicious wired modules — audit all eight. **Ready** (audit task is
    well-scoped, decisions await evidence per module).
12. ADR 0027 vs ADR 0033 — extension, no conflict. **Ready.**

### Decisions requiring a short experiment (1 of 12)

8. v2-driver-baseline-v1.json — apply autonomous packets only after governance
   prerequisites (Constitution commit, ROADMAP_V2 authority settlement, Jacob
   M3 write-bounds review). The experiment is: execute M1-09 (autonomous
   regression test) as a proof that the V2 packet pipeline works, while Jacob
   completes the live M1-01/M1-02 runs. Partial application is possible —
   autonomous packets first.

### Decisions that remain unknown

**None.** All twelve questions have sufficient evidence for a recommendation.
The remaining unknowns are execution tasks, not architectural decisions:
- SQLite-vec vs ChromaDB benchmark (Decision 3 follow-up)
- Live acceptance of Open WebUI bootstrap (Decision 1 follow-up)
- Three of eight suspicious modules need live code inspection (Decision 11
  follow-up)
- Jacob's M3 write-bounds review (Decision 8 prerequisite)

### Exact merge conditions for PR #408 (branch `closeout/2026-08-05-architecture-reconciliation`)

Before the closeout branch may merge:

1. **Governance prerequisites (blocking):**
   - [ ] This ratification document is committed to `main` as
     `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md`
   - [ ] The Constitution (`docs/CONSTITUTION.md`) is committed to `main` with
     its constitutional authority claim intact and its ratification date
     updated to 2026-08-06

2. **Document amendments required before or simultaneously with the merge:**
   - [ ] ADR 0033 line 5: "Supersedes" → "Extends" (Decision 12)
   - [ ] KITTY_MASTER_PROGRAM.md line 5: "Supersedes ROADMAP.md and
     ROADMAP_V2.md" → "Derived synthesis" (Decision 5)
   - [ ] KITTY_MASTER_PROGRAM.md Phase Numbering section: add "derived
     synthesis" note (Decision 7)
   - [ ] KITTY_MASTER_PROGRAM.md P0.9: clarify scope (Decision 9)
   - [ ] KITTY_MASTER_PROGRAM.md P4: add dependency note (Decision 10)
   - [ ] AUTHORITY_MAP.md: add Constitution as highest authority (Decision 6)
   - [ ] AUTHORITY_MAP.md: add ROADMAP_V2.md and KITTY_MASTER_PROGRAM.md
     entries (Decision 5)
   - [ ] v2-driver-baseline-v1.json: add preamble limiting autonomous
     application (Decision 8)
   - [ ] DISPOSITION_LEDGER.md: update header for V2 documents; add new
     documents (Decisions 5, 7)

3. **Design document disposition (must be labeled before merge):**
   - [ ] BUILDER_ORGANIZATION.md: add "Status: DESIGN — not ratified.
     Implementation requires separate ADR." (Decision 4)
   - [ ] BUILDER_V2.md: add "Status: DESIGN — not ratified. Implementation
     requires separate ADR." (Decision 4)

4. **Document index updates:**
   - [ ] `docs/adr/README.md`: add ARCHITECTURE_RATIFICATION_2026-08-06.md
     as a cross-cutting decision artifact (not a numbered ADR)
   - [ ] `docs/DECISIONS.md`: add reference to this ratification
   - [ ] `docs/DISPOSITION_LEDGER.md`: inventory all new closeout-branch
     documents (ROADMAP_V2.md, KITTY_MASTER_PROGRAM.md, CONSTITUTION.md,
     BUILDER_ORGANIZATION.md, BUILDER_V2.md, CAPABILITY_MANIFEST.md,
     KNOWLEDGE_GRAPH.md, CONTINUITY_RECOVERY.md, OPENWEBUI_PRODUCT_PLAN.md,
     OPENWEBUI_EXTENSION_BACKLOG.md, OPENWEBUI_OS_ARCHITECTURE.md,
     v2-driver-baseline-v1.json, 9 new ADRs, artifacts/)

5. **Runtime truth alignment:**
   - [ ] `docs/ROADMAP.md`: add reference to ROADMAP_V2.md as V2 target plan
     (Decision 5)
   - [ ] `docs/BLUEPRINT.md`: update Telegram status if `telegram_bot.py` is
     deleted (Decision 11 follow-up)

6. **No deletions or rewrites of existing ratified documents.** No ADR,
   roadmap, or Constitution deletion. The closeout branch is additive —
   preserve all artifact provenance including B8 forensic report and handoff
   artifacts under `artifacts/`.

---

## Appendix — Authority chain for this ratification

```
Jacob (decision owner)
  → AGENTS.md + CLAUDE.md (repository operating rules)
    → AUTHORITY_MAP.md (truth routing)
      → ADRs 0001–0036 (ratified decisions)
      → ROADMAP.md (active authority, per ADR 0020)
      → ROADMAP_V2.md (ratified target plan)
      → Constitution v1 (highest authority)
      → DISPOSITION_LEDGER.md (file dispositions)
      → CONTINUITY_RECOVERY.md (live Builder + KB state)
      → KNOWLEDGE_GRAPH.md (relationship archaeology)
      → Architecture decision summary (open decisions)
      → closeout branch evidence artifacts
        → This ratification document
```

No handoff note, planner prose, Builder worker narration, or document header
self-declaration was treated as authority. Where two sources disagreed, the
higher authority in this chain was used and the contradiction is recorded
above (Decisions 5 and 6).
