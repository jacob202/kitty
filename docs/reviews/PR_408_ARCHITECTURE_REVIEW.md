# PR #408 Architecture Review — Kitty V2 Architecture and Continuity Reconciliation

**Reviewer:** Independent architectural reviewer
**Date:** 2026-08-06
**Conclusion:** **REJECT** in current form. Four blocking contradictions must be resolved before this branch can serve as the architectural baseline. The remaining 22 artifacts are individually valuable research and should be preserved but must not be treated as settled authority.

---

## Overall Verdict

**REJECT — do not merge as the new architectural baseline.**

PR #408 carries 35 files (12,102 additions) that document a major research session. The ADRs (0028–0036), forensic report, closeout ledger, loose-ends register, and continuity recovery are individually rigorous and useful. However, three categories of artifact actively undermine the architecture:

1. The Constitution v1 claims supremacy authority before ratification and before the existing AUTHORITY_MAP acknowledges it.
2. OPENWEBUI_OS_ARCHITECTURE.md proposes making Open WebUI a "permanent UI component" — flatly contradicting ADR 0027 (replaceable shell), ADR 0033 (shell integration boundary), and the Constitution's own Article I.2 (also "replaceable shell").
3. Three documents claim to be the canonical delivery sequence: ROADMAP.md (ADR 0020), ROADMAP_V2.md, and KITTY_MASTER_PROGRAM.md ("supersedes ROADMAP.md and ROADMAP_V2.md").
4. BUILDER_V2.md proposes a complete engine replacement that contradicts ADR 0036's decision to "preserve" and "refactor" Builder infrastructure.

These are not nuance differences — they are contradictory claims about what Kitty is, who owns what, and what to build next. A PR that enters a four-way authority dispute is not an architectural reconciliation.

---

## Blocking Findings

### B1 [BLOCKING] Open WebUI boundary: replaceable shell vs. permanent UI

**Documents in conflict:**
- `docs/CONSTITUTION.md` Article I.2: "Open WebUI is the primary daily-driver shell. It is integrated through stable Gateway contracts and **may be replaced** without migrating Kitty's state or logic."
- `docs/adr/0027-open-webui-shell-boundary.md`: "Open WebUI May Serve As Kitty's Replaceable Daily-Driver Shell"
- `docs/adr/0033-open-webui-shell-boundary.md`: "The Open WebUI shell boundary is hardened with these specific rules" — reinforces replaceable.
- `docs/OPENWEBUI_OS_ARCHITECTURE.md`: "**To be superseded.** This architecture proposes Open WebUI as the **permanent** UI component, not a replaceable shell." Also proposes moving Notes, Tasks, Memory, Calendar, and chat orchestration **out of Kitty into Open WebUI native features.** Also proposes Builder evolve into "workspace operator" managing Open WebUI plugins and MCP servers.

**Why it blocks:**
These are not shades of emphasis. One architecture says Open WebUI's internal state is irrelevant to Kitty; the other says Kitty should *move its own product concerns into Open WebUI's native features.* One says replaceable; the other says permanent. No intermediate position exists. The CLOSEOUT_LEDGER §3 flags this as C-1 with "Jacob decision: YES — adopt permanent-UI ADR or keep replaceable." Until Jacob resolves it, PR #408 cannot be the architectural baseline — it contains two contradictory baselines.

**Fix required:** Jacob must decide, and whichever document loses must be demoted to `docs/research/` (or equivalent), not carried as a competing authority.

---

### B2 [BLOCKING] Three documents claim canonical delivery sequence

**Documents in conflict:**
- `docs/ROADMAP.md` — ratified by ADR 0020 as "one canonical roadmap."
- `docs/ROADMAP_V2.md` — "Proposed (v2 target architecture)" with M1–M6 milestones.
- `docs/KITTY_MASTER_PROGRAM.md` — "**Supersedes:** `docs/ROADMAP.md` and `docs/ROADMAP_V2.md` as the single canonical delivery sequence."

**Why it blocks:**
ADR 0020 established that there is one roadmap. Now three files claim or imply they are it. The Master Program claims supersession but is itself marked "proposed" (not ratified) in the CLOSEOUT_LEDGER §2 ("proposed / not implemented"). Self-declared supersession without ratification is not authority — it's a claim. The CLOSEOUT_LEDGER §3 C-5 flags this correctly. Until one document is ratified as canon and the others archived or demoted, there is no baseline.

**Fix required:** Jacob picks one. The other two are moved to `docs/research/` or `docs/proposals/`. The winner must be ratified (e.g., an ADR amendment to 0020, or a new ADR explicitly superseding it).

---

### B3 [BLOCKING] Constitution v1 claims supremacy without ratification

**Document:** `docs/CONSTITUTION.md`

The Constitution v1 claims:
- "Highest-level design artifact. Every future Builder packet, ADR, roadmap, feature, worker, reviewer, and planner must justify itself against this document before it is accepted."
- "No other document may contradict it."
- "All future work in this repository is governed by this document."

**Why it blocks:**
The Constitution was written during the 2026-08-05 research session — the same session that produced the documents it governs. It is not a pre-existing authority being codified; it is a synthesis paper. It has not been indexed in `docs/AUTHORITY_MAP.md`, added to the `docs/reference/CODEBASE_MAP.md` reading order, or ratified by any ADR. Its own Amendment Policy (Article VII.5) requires an ADR to amend it — but no ADR created it. It is self-referential authority.

Furthermore, Article I.2 (Open WebUI is replaceable shell) contradicts OPENWEBUI_OS_ARCHITECTURE.md ("permanent UI component") in the same PR. If Jacob chooses permanent-UI, the Constitution's Article I.2 is already wrong.

The CLOSEOUT_LEDGER §3 C-6: "Constitution authority: v1 claims 'no other document may contradict it' but is not in AUTHORITY_MAP / DECISIONS / reading order — not promoted unilaterally; flagged in ledger. **YES — ratify Constitution into AUTHORITY_MAP or demote its supremacy claim.**"

**Fix required:** Either (a) Jacob ratifies the Constitution through a proper ADR that creates it as the authority record, and AUTHORITY_MAP is updated, OR (b) the Constitution is demoted to a proposed research artifact. It cannot sit at the top of the authority hierarchy without ratification.

---

### B4 [BLOCKING] BUILDER_V2.md contradicts ADR 0036

**Documents in conflict:**
- `docs/adr/0036-builder-infrastructure-refactor.md`: "Builder infrastructure is **preserved** — refactored for extraction readiness." Decision: "Builder modules are refactored internally" along execution-infrastructure/product-logic lines. "No migration to external workflow engines is planned."
- `docs/BUILDER_V2.md`: "Builder V2 — Execution Engine Redesign." "This document redesigns the execution engine itself. It keeps the primitives that work (SQLite, worktrees, leases, evidence, review, governance) and **replaces everything else** with an engine designed for the agent landscape of 2026." Proposes: new SQLite schema with 8+ tables, cryptographic identity (Ed25519 keypairs), pull-based workers (not current push), "state is derived from evidence chains not state machines," 13 of 27 modules removed.

**Why it blocks:**
ADR 0036 says preserve and refactor. BUILDER_V2.md says redesign and replace. Both are in the same PR. A refactor reorganizes 27 modules into a subpackage; a redesign replaces the schema, the worker model, the scheduling model, and the trust model. These are not the same operation. If BUILDER_V2.md is the direction, ADR 0036 is already wrong and needs amendment. If ADR 0036 is the decision, BUILDER_V2.md's detailed implementation plan (down to SQL table definitions and module-by-module disposition) is dangerous as "settled architecture" when it contradicts the ratified decision.

**Fix required:** Either BUILDER_V2.md is demoted to a proposal/reference (not architecture), or ADR 0036 is amended to reflect the redesign direction. The two cannot coexist as accepted decisions.

---

## Important Findings

### I1 [IMPORTANT] Unverified claims in OPENWEBUI_OS_ARCHITECTURE.md

OPENWEBUI_OS_ARCHITECTURE.md makes specific capability claims about Open WebUI features that are asserted as "built-in" or "community tool" without browser verification. Examples:
- "Built-in Persistent Memory" (line: "Cross-conversation facts. Already active in current configuration.")
- "Built-in Notes. Rich editor, AI enhance, context injection. Already more capable than Kitty's notes."
- "Built-in Tasks (create_tasks, update_task). Native function calling."
- "iChristGit News Reader community tool. 45 feeds, 11 categories, AI summaries."
- "Official desktop app (Spotlight: Shift+Cmd+I, voice, screenshots)."

None of these claims are browser-verified. ADR 0035 (in the same PR) requires "browser-verified evidence required for UI claims." The companion document `docs/reference/OPENWEBUI_ECOSYSTEM_SURVEY.md` (92 lines) is a survey of *possible* features, not confirmed operational features. The OS architecture document treats community tools and built-in features as settled capabilities without evidence that they work in Kitty's specific configuration.

**Impact:** Making architectural decisions about what to delete from Kitty based on unverified Open WebUI capabilities risks regressing working features. If Open WebUI's "Built-in Persistent Memory" doesn't work or doesn't meet Kitty's needs, the decision to "move Memory (working context) out of Kitty" is premature.

**Fix:** Tag every claimed Open WebUI capability in the OS architecture document with its verification status. Any claim not browser-verified must be labeled PROPOSED.

---

### I2 [IMPORTANT] BUILDER_ORGANIZATION.md: 16-role engineering org as unimplemented design

`docs/BUILDER_ORGANIZATION.md` defines 16 specialized roles (Chief Architect, Planner, Research, Implementer, Reviewer, QA, Browser Verification, Performance, Security, Knowledge Curator, Refactoring Team, Release Manager, Operations, Image Team, UI/UX, Scribe) each with responsibilities, authority, inputs, outputs, escalation rules, required evidence, communication protocols, and serialization rules.

This is 1,113 lines of detailed design, yet:
- Its status is "Design — not yet implemented."
- No ADR ratifies this organization.
- No Builder code implements role-based routing with 16 role definitions.
- The CLOSEOUT_LEDGER §2 lists it as "proposed / not implemented."

**Impact:** The document reads as settled architecture (it uses imperative language: "No worker approves its own work," "Authority is bounded by role," "The org chart is the escalation chart") but is a design proposal. If another document or worker treats these roles as binding, work will deadlock on non-existent roles.

**Fix:** Either ratify through an ADR that establishes the organization as architectural direction, or clearly label every section as "DESIGN PROPOSAL — NOT YET IMPLEMENTED." The document should state which roles have code equivalents today (only Implementer and Reviewer, approximately).

---

### I3 [IMPORTANT] KITTY_MASTER_PROGRAM.md: implementation plans disguised as settled architecture

KITTY_MASTER_PROGRAM.md (931 lines) contains:
- P0–P8 phase definitions with specific packet definitions, acceptance criteria, kill criteria, and parallelization strategies.
- Exact code estimates for extensions (e.g., "~60 lines" for One Thing card).
- A critical path dependency chain.
- A "Builder Execution Order" specifying exactly which packets Builder should select and in what order.
- "Success Criteria — The Destination" with 10 numbered completion conditions.
- A ratification table claiming to synthesize "150+ documents."

Yet its status is "proposed" (per CLOSEOUT_LEDGER §2). The phase definitions prescribe specific Builder behavior ("When Builder selects the next eligible packet, it evaluates in this priority...") that would override ADR 0021's proactive execution rules. P0 packets like P0.3 (launcher parity) and P0.9 (trust model) are defined with acceptance criteria but are not authorized for execution.

**Impact:** If Builder consumes this document as a scheduling directive, it will attempt to execute packets that the LOOSE_ENDS register explicitly says must not run (P0-7: "V2 initiative must NOT be applied yet"). The document's language suggests settled execution order when it needs Jacob's ratification (C-5, C-8, C-10 in the closeout ledger).

**Fix:** The document header must clearly state "PROPOSED — NOT AN EXECUTION DIRECTIVE. Do not use for Builder scheduling decisions until ratified by Jacob." Remove imperative scheduling language ("Builder selects in this priority") and replace with conditional ("If ratified, Builder would...").

---

### I4 [IMPORTANT] ADR 0031 references un-verifiable external projects

ADR 0031 defers migration to Open Brain, Ringer, and Open Engine. The accompanying analysis document (`docs/research/architecture-migration-analysis-2026-08-05.md`, 552 lines on an un-pushed branch) "assumes" these projects exist but notes: "Open Brain / Ringer / Open Engine: Assumed emerging projects. Exact API surfaces, schema, and maturity are UNKNOWN."

The ADR itself is sound (defer until maturity is proven). However:
- The migration analysis maps every current Kitty module to one of the three projects and estimates line-count impact (~11,400 lines). This creates a structural dependency on projects that may not exist.
- OPENWEBUI_OS_ARCHITECTURE.md partially reopens the question by proposing Builder evolve into a "workspace operator" — which overlaps with Ringer's proposed domain (worker orchestration) and Open Engine's domain (durable execution).
- No dedicated investigation was conducted on any of the three projects. The ADR acknowledges this explicitly but the migration analysis reads as if the projects are real.

**Impact:** Future work could be planned against a three-project decomposition for projects that never materialize. The ADR is honest about this risk; the migration analysis less so.

**Fix:** Add a prominent caveat to the migration analysis: "This document maps Kitty's modules against *proposed* project responsibilities. None of Open Brain, Ringer, or Open Engine has been independently verified to exist with stable APIs. This is a code organization guide, not a dependency commitment."

---

### I5 [IMPORTANT] V2 initiative manifest included but marked unsafe to apply

`docs/initiatives/v2-driver-baseline-v1.json` (213 lines) is present in the PR. The LOOSE_ENDS register P0-7 explicitly states: "V2 initiative must NOT be applied yet — its manifest contains live/operator-class packets that must not run autonomously, and P0-1/P0-3 are unsolved."

The file contains packet classes including `human`, `live`, and `operator` — packets that, if Builder's proactive execution (ADR 0021) picked them, would launch operations requiring Jacob's machine, credentials, or approval.

**Impact:** The file's presence on `main` after merge means any invocation of `./kitty builder initiative apply v2-driver-baseline-v1.json` could trigger execution. Including a manifest marked "not safe to apply" in a mergeable PR is risky.

**Fix:** Either (a) remove the manifest from the PR and preserve it in a `proposals/` or `research/` directory that Builder does not scan, or (b) add a `blocked: true` field and a gate in Builder that refuses to apply blocked manifests.

---

### I6 [IMPORTANT] needs_decision fail-closed not fixed

The forensic report (`artifacts/forensic-b8-wrong-assignment-2026-08-05.md`) proves conclusively that `builder_run.py:574-591` records `needs_decision` and then `continue`s with exit code 0 — meaning Builder can re-select the same wrong packet indefinitely. The LOOSE_ENDS register P0-1 says this "Must resolve before Builder runs." The PR body says "Explicitly not included: no product implementation."

**Impact:** The PR documents the trust hole at forensic detail but does not fix it. If the PR is merged as the architectural baseline, the baseline says "Builder has a proven trust hole that must be fixed before any execution" but leaves the hole open. Until P0-1 is fixed, any autonomous Builder run re-selecting B8 (or equivalent) is re-validating the same failure.

**Fix:** This finding does not block the *documentation* merge — the PR is explicitly doc-only. But the review must state: merging this PR without fixing P0-1 does not satisfy the condition that "the Builder trust repair precedes V2 initiative execution." The LOOSE_ENDS register itself says this must happen first. A merged baseline that documents a blocker without resolving it is a baseline with a known open severity-0 defect.

---

## Minor Findings

### M1 [MINOR] CAPABILITY_MANIFEST.md claims supersession without ratification

CAPABILITY_MANIFEST.md (1,340 lines) states: "supersedes the schema described in KITTY_PRODUCT_ARCHITECTURE.md Section 4 and the v1 layout in gateway/runtime_manifest.py."

This is an architectural claim in a document marked "Core specification" but not ratified by an ADR or Jacob. ADR 0029 established the Capability Manifest as single source of runtime truth, but did not bless this specific 1,340-line v2 schema. The schema itself may be correct — but the supersession claim requires ratification.

---

### M2 [MINOR] ADR 0030 references non-existent "repository simplification audit"

ADR 0030's Evidence section cites: "Repository simplification audit (2026-08-05): Complete inventory, dead code graph, dependency graph. 43 dead files proven with rg import tracing."

The CLOSEOUT_LEDGER §9 reports: "repository simplification audit (as a standalone document) — **NOT FOUND as a file/branch anywhere.** Its findings are embodied by ADR 0030 + the dead-code archival commit `4c0bf06b`."

ADR 0030 references evidence that doesn't exist as a retrievable document. The ADR's conclusions may be correct, but the evidence chain cites a phantom.

---

### M3 [MINOR] DECISIONS.md fix had a false-claim chain

The CLOSEOUT_LEDGER §3 C-11 notes that the ADR-indexing worker "claimed 'Updated (2026-08-05)' but file stopped at D25/D26." The closeout branch corrected this. The error is minor (9 missing rows) but the pattern — a worker claiming completion without evidence — is exactly the trust pattern B8 revealed and ADR 0032 forbids.

---

### M4 [MINOR] KNOWLEDGE_GRAPH.md is analysis, not authority

KNOWLEDGE_GRAPH.md (532 lines) documents structural problems (missing links, stale references, superseded claims) across the documentation corpus. It is a diagnostic tool, not an architectural document. Its "recommended actions" section should reference ADRs or ratified authorities, not present directives independently.

---

### M5 [MINOR] OPENWEBUI_EXTENSION_BACKLOG.md: 38 extensions as backlog

The extension backlog (2,148 lines) is thorough. However, several S-Tier and A-Tier extensions assume Open WebUI capabilities from OPENWEBUI_OS_ARCHITECTURE.md that are not browser-verified (see I1). The backlog's value depends on the architecture decision (B1).

---

### M6 [MINOR] CLOSEOUT_LEDGER: evidence of thoroughness but self-reported

The closeout ledger asserts "every file below was confirmed on disk (path + content) or in Git (commit SHA) during this closeout, not taken from a worker summary." This is plausible (specific SHAs, DB queries, file paths) but cannot be independently verified from the PR diff alone — it requires access to the canonical checkout. The ledger is honest about verification methodology (§0).

---

### M7 [MINOR] Multiple documents at same authority level marked "proposed"

The CLOSEOUT_LEDGER §2 shows 12+ artifacts as "proposed / not implemented" or "needs review." Yet several use architectural language:
- OPENWEBUI_OS_ARCHITECTURE.md: "permanent responsibility boundaries"
- BUILDER_V2.md: "This document redesigns the execution engine itself"
- KITTY_MASTER_PROGRAM.md: "Supersedes: docs/ROADMAP.md and docs/ROADMAP_V2.md"

Documents that are "proposed" should not use settled-authority language. This is a presentation issue but contributes to the overall ambiguity.

---

## Files Reviewed

All 35 files in the PR diff were inspected:

| File | Type | Reviewed |
|---|---|---|
| `docs/adr/0028-commodity-software-precedence.md` | ADR | Yes |
| `docs/adr/0029-capability-manifest-single-truth.md` | ADR | Yes |
| `docs/adr/0030-repository-simplification-strategic-priority.md` | ADR | Yes |
| `docs/adr/0031-architecture-migration-deferred.md` | ADR | Yes |
| `docs/adr/0032-evidence-backed-claims.md` | ADR | Yes |
| `docs/adr/0033-open-webui-shell-boundary.md` | ADR | Yes |
| `docs/adr/0034-memory-policy-vs-storage.md` | ADR | Yes |
| `docs/adr/0035-browser-verified-evidence.md` | ADR | Yes |
| `docs/adr/0036-builder-infrastructure-refactor.md` | ADR | Yes |
| `docs/adr/README.md` | Index | Yes |
| `docs/CONSTITUTION.md` | Constitution (modified) | Yes — full 444-line diff |
| `docs/ROADMAP_V2.md` | Roadmap | Yes |
| `docs/KITTY_MASTER_PROGRAM.md` | Master Program | Yes |
| `docs/OPENWEBUI_OS_ARCHITECTURE.md` | Architecture proposal | Yes |
| `docs/OPENWEBUI_PRODUCT_PLAN.md` | Product plan | Yes |
| `docs/OPENWEBUI_EXTENSION_BACKLOG.md` | Extension backlog | Yes — 2,148 lines |
| `docs/BUILDER_ORGANIZATION.md` | Org design | Yes |
| `docs/BUILDER_V2.md` | Engine redesign | Yes |
| `docs/CAPABILITY_MANIFEST.md` | Spec | Yes — 1,340 lines |
| `docs/CLOSEOUT_LEDGER_2026-08-05.md` | Closeout | Yes |
| `docs/LOOSE_ENDS_2026-08-05.md` | Loose ends | Yes |
| `docs/CONTINUITY_RECOVERY.md` | Continuity | Yes |
| `docs/KNOWLEDGE_GRAPH.md` | Knowledge graph | Yes |
| `docs/DECISIONS.md` | Decision index (modified) | Yes — 9 lines added |
| `docs/DISPOSITION_LEDGER.md` | Disposition (modified) | Yes |
| `docs/README.md` | Readme (modified) | Yes |
| `docs/memory-stale.md` | Memory stale (modified) | Yes |
| `docs/skill-improvement-queue.md` | Skill queue (modified) | Yes |
| `docs/reference/OPENWEBUI_ECOSYSTEM_SURVEY.md` | Survey | Yes |
| `docs/research/README.md` | Research index | Yes |
| `docs/research/architecture-decision-summary-2026-08-05.md` | Decision summary | Yes |
| `docs/research/architecture-migration-analysis-2026-08-05.md` | Migration analysis | Yes |
| `docs/initiatives/v2-driver-baseline-v1.json` | Initiative manifest | Yes |
| `artifacts/forensic-b8-wrong-assignment-2026-08-05.md` | Forensic report | Yes |
| `artifacts/handoff-builder-trust-model-v1.md` | Handoff brief | Yes |

---

## Claims Personally Verified

The following claims were verified against git history, the PR diff, and comparison with the origin/main versions:

1. **DECISIONS.md D27–D35** were not present on origin/main — only D1–D26 existed. The closeout branch added them. Verified.

2. **CONSTITUTION.md** was completely rewritten (not incrementally updated). The origin/main version had Articles I–II; the PR version has Articles I–VII with preamble, ratification table, and amendment policy. Verified.

3. **ADR index (README.md)** was modified to add 9 rows and update table formatting. Verified.

4. **ROADMAP.md** on origin/main was not deleted or modified by this PR — it remains the current canonical roadmap per ADR 0020. The PR adds ROADMAP_V2.md and KITTY_MASTER_PROGRAM.md as new files. Verified.

5. **OPENWEBUI_OS_ARCHITECTURE.md explicitly states**: "Supersedes guidance in: ADR 0027 (evolves from 'replaceable shell' to 'permanent UI component')." This is a direct conflict with the same PR's ADR 0033 and Constitution Article I.2. Verified from the document text line 6.

6. **BUILDER_V2.md** contains a complete redesign proposal with new SQLite schema, cryptographic identity, pull-based workers, and 13 modules to be removed. ADR 0036 in the same PR says "Builder infrastructure is preserved — refactored for extraction readiness." Verified from both documents.

7. **KITTY_MASTER_PROGRAM.md line ~900**: "**Supersedes:** `docs/ROADMAP.md` and `docs/ROADMAP_V2.md` as the single canonical delivery sequence." Verified.

8. **The Constitution v1** was written during the 2026-08-05 session (not a pre-existing document). The CLOSEOUT_LEDGER §1 item 19 lists it as "Uncommitted" on the main working tree and "proposed / not implemented." Verified against the commit history — the Constitution rewrite is in commit `32a24e13` on the closeout branch.

9. **The forensic B8 report** cites specific line numbers in `builder_run.py:574-591` for the `needs_decision` continue bug. These line numbers were not independently confirmed in live code (see below).

10. **The closeout ledger §9** explicitly lists "repository simplification audit" as "NOT FOUND" and "Builder Trust Model v1" as "NOT PRODUCED." Verified from the document text.

---

## Claims Not Verifiable

The following claims could not be independently verified from the PR diff alone and require access to the canonical checkout or runtime evidence:

1. **B8 forensic conclusions** — The DB rows, event IDs, commit SHAs, and line numbers in the forensic report are specific and plausible but not verifiable from the diff. The DB file is not in the PR. The branch with the B8 commits is not fetched. The claim that `builder_run.py:574-591` has a `continue` after `needs_decision` cannot be confirmed without reading the live file.

2. **CLOSEOUT_LEDGER file-by-file verification** — The ledger states "every file below was confirmed on disk." This is a self-reported claim. The files exist on the closeout branch, but whether they match what was "on disk" at closeout time is unverifiable.

3. **Continuity recovery §0 claims** about uncommitted files on the main working tree — these describe state on a specific machine, not in git.

4. **Open WebUI capability claims** (OPENWEBUI_OS_ARCHITECTURE.md and OPENWEBUI_EXTENSION_BACKLOG.md) — Claims about built-in features, community tools, and desktop apps are not browser-verified. The ecosystem survey (`docs/reference/OPENWEBUI_ECOSYSTEM_SURVEY.md`, 92 lines) provides a feature inventory but no live verification evidence.

5. **KITTY_MASTER_PROGRAM.md's "150+ documents synthesized" claim** — The ratification table lists 18 source categories. The count cannot be verified without access to all referenced documents.

6. **`./kitty context --agent` results** (CLOSEOUT_LEDGER §4: "PASS 27 / WARN 0 / FAIL 0") — Runtime verification from the canonical checkout, not reproducible from the PR.

---

## Recommended Canonical Authority Hierarchy

If Jacob resolves the blocking contradictions, the following hierarchy is proposed:

1. **Constitution v1** — only after formal ratification (ADR or other binding mechanism) and placement in AUTHORITY_MAP. If not ratified, demote to `docs/research/`.

2. **Ratified ADRs 0001–0036** — the current authority chain. ADRs 0028–0036 are individually sound.

3. **Single Canonical Roadmap** — exactly one of ROADMAP.md, ROADMAP_V2.md, or KITTY_MASTER_PROGRAM.md, with the other two moved to `docs/research/` or `docs/proposals/`. The winner must be ratified per ADR 0020's "one canonical roadmap."

4. **Architecture Documents** — KITTY_PRODUCT_ARCHITECTURE.md, AUTHORITY_MAP.md, CODEBASE_MAP.md, ALIGNMENT_MAP.md. These describe the architecture; they do not prescribe execution.

5. **Design Proposals** — BUILDER_ORGANIZATION.md, BUILDER_V2.md, OPENWEBUI_OS_ARCHITECTURE.md (if permanent-UI is chosen), CAPABILITY_MANIFEST.md (the spec itself, as distinct from ADR 0029's principle). These inform future ADRs but do not govern.

6. **Research and Analysis** — OPENWEBUI_PRODUCT_PLAN.md, OPENWEBUI_EXTENSION_BACKLOG.md, architecture-migration-analysis, decision summary, ecosystem survey, KNOWLEDGE_GRAPH.md, CONTINUITY_RECOVERY.md. Valuable inputs, not authority.

7. **Closeout Artifacts** — CLOSEOUT_LEDGER, LOOSE_ENDS register, forensic report. Historical evidence of what was decided and what remains open.

---

## Recommendation

**REJECT as the new architectural baseline. Preserve as research.**

The PR contains four blocking contradictions that prevent it from serving as a reliable architectural baseline:

1. Open WebUI as replaceable shell vs. permanent UI (B1)
2. Three documents claiming canonical roadmap authority (B2)
3. Constitution supremacy unratified (B3)
4. Builder redesign vs. Builder refactor (B4)

**Recommended path forward:**

1. **Jacob resolves the four blocking contradictions** — each is explicitly flagged in the CLOSEOUT_LEDGER §3 (C-1, C-4, C-5, C-6) and LOOSE_ENDS (P1-1, P1-2). These are Jacob-level decisions; no one else can make them.

2. After resolution, produce a **clean PR** that contains only:
   - The 9 ADRs (0028–0036) — individually ratified and internally consistent.
   - The ratified Constitution (if chosen).
   - The single canonical roadmap (if chosen).
   - The forensic report and closeout/loose-ends as historical evidence.
   - The Capability Manifest spec (if ratified through ADR amendment).
   - Any design proposals explicitly labeled "PROPOSED — NOT ARCHITECTURE."

3. **Exclude from the clean PR** (move to `docs/research/` or `docs/proposals/`):
   - The losing roadmap documents.
   - OPENWEBUI_OS_ARCHITECTURE.md (unless Jacob ratifies permanent-UI).
   - BUILDER_V2.md and BUILDER_ORGANIZATION.md (unless Jacob ratifies redesign over refactor).
   - The V2 initiative manifest (until P0-1 is fixed).

4. **Before any Builder execution:** Fix P0-1 (`needs_decision` fail-closed) as a separate, implementable patch.

The 9 ADRs and the forensic report are the high-value, low-controversy artifacts. They can be merged independently. The remaining documents need Jacob's architectural decisions before they can become authority.

---

*Review conducted 2026-08-06. All 35 files inspected. Evidence citations from PR diff and git comparison against origin/main. No files modified. No merge executed.*
