# Audit Consumption Matrix

Purpose: make this companion package useful **at the right time** without letting it pre-bias the sequential investigation.

## Global rule

The auditor should discover facts from current Kitty evidence first, then use this package as a coverage/checking aid.
Never cite a companion-package statement as proof of a Kitty defect.

## Chunk-by-chunk use

### Chunk 0 — Establish Repository Truth
Read:
- this file;
- package `README.md`;
- `POST_AUDIT_COLLISION_AND_OWNERSHIP_PROTOCOL.md`.

Use them only to:
- avoid colliding with active work;
- record that this support package exists;
- distinguish support material from authority.

Do **not** import provisional findings from the cleanup ledger into the audit ledger without independent verification.

### Chunk 1 — Runtime + Core Correctness
Primary evidence remains runtime/code/tests.
After findings are independently established, compare relevant cases in the acceptance/failure-injection spec to check test coverage gaps.
Do not use the implementation prompt.

### Chunk 2 — Security + Trust Boundaries
Use acceptance cases concerning approval identity, argument integrity, stale authority, duplicate side effects, and ambiguous remote outcomes only as adversarial prompts.
Every security conclusion still requires Kitty-specific threat actor, boundary, precondition, failure path, impact, likelihood, and mitigation.

### Chunk 3 — Durable Execution + Builder
Use:
- collision protocol for ownership checks;
- acceptance/failure-injection spec for crash/retry/stale-worker scenarios.

Do not treat the candidate ledger as proof that a duplicate execution surface still exists.

### Chunk 4 — Memory + Context + Research
Use the acceptance spec only after current cache/retrieval behavior has been inspected.
The immediate-write/read, correction, conflict, stale-cache, retention, and growing-file cases are coverage prompts, not findings.

### Chunk 5 — Image Lab
The companion package must not override the active Image Lab audit/work lane.
Only use generic invariants such as truthful state, durable recovery, explicit cost, no uncontrolled paid retry, and artifact integrity.
Do not import non-current provider assumptions from these notes.

### Chunk 6 — Automations + Background Work
Use automation restart/overlap/disabled-state failure cases after current scheduler ownership is independently mapped.

### Chunk 7 — Native Frontend + Product Surface
Use the acceptance spec for refresh/reconnect/backend-truth journeys.
Use cleanup candidates only to ask whether apparently obsolete UI is `CONFIRMED DEAD`, `LIKELY DEAD`, `LEGACY BUT STILL REACHABLE`, `COMPATIBILITY SHIM`, or `ACTIVE`.

### Chunk 8 — Performance + Cost + Dependencies + Build
Use:
- `POST_AUDIT_EXECUTION_RUNBOOK.md` to compare the actual current CI gates;
- `UPSTREAM_REMEDIATION_REFERENCE_NOTES.md` only after a corresponding finding is verified;
- acceptance measurements as suggestions for evidence, not predetermined budgets.

### Chunk 9 — Architecture + Language + Simplification
Now read the full deletion/convergence candidate ledger.
For **every candidate**, independently classify it:
`PROMOTE TO VERIFIED FINDING`, `ALREADY TRACKED`, `IN FLIGHT`, `FIXED`, `DISPROVED`, `DUPLICATE`, `DESIGN QUESTION`, or `DEFERRED WITH REASON`.
No candidate may disappear without a disposition.

### Chunk 10 — Cross-Pass Reconciliation
Mandatory full-package reconciliation begins here.
Re-check collisions against current GitHub/main before finalizing recommendations.
Group candidate symptoms under verified root causes where justified.
Create the required candidate-disposition crosswalk described below.

### Chunk 11 — Final Execution Plan
Read the entire companion package.
Use `POST_AUDIT_IMPLEMENTATION_PROMPT.md`, `POST_AUDIT_EXECUTION_RUNBOOK.md`, and `KITTY_AGENT_EXECUTION_OPERATING_PROCEDURE.md` to shape execution only after findings and ordering are final.
Map applicable acceptance/failure cases to remediation chunks.

## Required final crosswalks

### A. Candidate disposition crosswalk
For every item in `POST_AUDIT_DELETION_AND_CONVERGENCE_CANDIDATES.md`, record:
- candidate name/ID;
- final disposition;
- verified finding ID(s), if any;
- current issue/PR/branch collision status;
- rationale/evidence location;
- implementation-plan chunk or `NO ACTION`.

### B. Acceptance coverage crosswalk
For every applicable invariant, acceptance case, or failure-injection case in `POST_AUDIT_ACCEPTANCE_AND_FAILURE_INJECTION_SPEC.md`, record:
- acceptance/failure ID;
- finding ID(s) addressed;
- existing test/proof, if adequate;
- new test/procedure required, if any;
- remediation chunk;
- `NOT APPLICABLE` with reason where genuine.

### C. External-reference crosswalk
For every upstream pattern actually recommended, record the Kitty finding that justified consulting it.
Do not include upstream changes that solve no verified current problem.

## Required working artifact

During Chunk 10, copy or fill `COVERAGE_CROSSWALK_TEMPLATE.md` as part of the active audit ledger.
Do not postpone all mapping until the final prose response; maintain it while reconciling findings.
At Chunk 11 completion, no candidate, acceptance case, failure-injection case, or actually-used upstream reference may remain without a disposition.
