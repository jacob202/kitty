# Sequential Audit Companion Package — 2026-08-23

This directory is a **support package for the current sequential Kitty audit**.
It is deliberately not product authority and it does not contain pre-approved findings.

## Auditor rule

Use repository/runtime/GitHub evidence to decide what is true.
These files help with coverage, collision avoidance, validation, and post-audit execution.
They must never override current code, tests, GitHub state, accepted ADRs, or the audit ledger.

A candidate mentioned here must still be classified by the audit as one of:
`NEW`, `ALREADY TRACKED`, `IN FLIGHT`, `FIXED ON CURRENT MAIN`,
`STALE / NOT REPRODUCIBLE`, `DUPLICATE`, or `DESIGN QUESTION`.

## Mandatory first read for the auditor

Read `AUDIT_CONSUMPTION_MATRIX.md` before using any other file in this directory.
It defines when each artifact is relevant and prevents implementation material from biasing investigative chunks.

## Package contents

- `POST_AUDIT_ACCEPTANCE_AND_FAILURE_INJECTION_SPEC.md` — objective proof that repaired Kitty actually works.
- `POST_AUDIT_COLLISION_AND_OWNERSHIP_PROTOCOL.md` — current-work / PR / branch collision checks.
- `POST_AUDIT_DELETION_AND_CONVERGENCE_CANDIDATES.md` — provisional cleanup candidates only; not a backlog.
- `POST_AUDIT_EXECUTION_RUNBOOK.md` — verification/evidence sequence based on current CI shape.
- `POST_AUDIT_IMPLEMENTATION_PROMPT.md` — implementation-agent contract for after Chunk 11.
- `KITTY_AGENT_EXECUTION_OPERATING_PROCEDURE.md` — lane ownership, review, handoff, and mutation rules.
- `UPSTREAM_REMEDIATION_REFERENCE_NOTES.md` — external technical references to consult only after Kitty evidence warrants them.
- `PACKAGE_MANIFEST.yaml` — machine-readable chunk-to-artifact routing and completion requirements.
- `COVERAGE_CROSSWALK_TEMPLATE.md` — mandatory Chunk 10–11 disposition/coverage ledger; no row may remain TBD at completion.

## Non-interference rule

Chunks 0–9 remain investigative. Do not implement from this package during those chunks.
Do not promote a deletion candidate because it appears here.
Do not copy an upstream pattern into Kitty until the audit verifies that the corresponding Kitty problem is real.

## Completion rule

By the end of Chunk 10, every candidate in the deletion/convergence ledger must have an explicit disposition.
By the end of Chunk 11, every applicable acceptance invariant or failure-injection case must be mapped to:

- one or more verified finding IDs;
- a remediation chunk;
- an existing test that already proves it, or a test/procedure to add;
- a disposition when it is genuinely not applicable.

Nothing in this directory is considered "addressed" merely because it was read.
Coverage is complete only when the crosswalk required by `AUDIT_CONSUMPTION_MATRIX.md` is filled by the final audit.

## Authority

If this package conflicts with current repository truth, repository truth wins and the conflict itself may become audit evidence.
If it conflicts with canonical product/architecture authority, canonical authority wins unless the audit demonstrates that authority is stale or contradictory.
## Live sequential-audit checkpoint

The active audit has completed Chunks 0–2. Use these files instead of historical chat context:

- `LIVE_AUDIT_LEDGER_THROUGH_CHUNK_2.md` — compact cumulative finding/collision ledger.
- `CHUNK_2_SECURITY_TRUST_REPORT.md` — completed Security / Trust Boundaries report.
- `NEXT_CHUNK_3_HANDOFF.md` — minimal sequential handoff for the next Builder-only audit owner.

These are audit evidence/checkpoints, not implementation authorization.

