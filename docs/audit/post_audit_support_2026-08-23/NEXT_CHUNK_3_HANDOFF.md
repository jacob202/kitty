# NEXT HANDOFF — CHUNK 3: KittyBuilder

Use this as the only audit handoff after CHUNK 2. Do not ingest the full historical chat.

## Required first reads

1. `README.md`
2. `AUDIT_CONSUMPTION_MATRIX.md`
3. `LIVE_AUDIT_LEDGER_THROUGH_CHUNK_2.md`
4. `CHUNK_2_SECURITY_TRUST_REPORT.md` only for SEC-001 and the Builder-relevant trust conclusions.

Then verify current repository/GitHub/runtime truth yourself. Current code wins over this handoff.

## Mission

Audit **KittyBuilder only** as CHUNK 3 of the sequential whole-repository audit. This is investigation, not implementation.

### Inspect at minimum

- Builder queue/state machine, initiatives/tasks/attempts/workers.
- leases, heartbeats, retries, cancellation, timeout, restart/recovery/reconciliation.
- supervisor and worker lifecycle.
- worktree/branch creation, ownership, cleanup, stale work recovery.
- runner/adapters/model invocation and subprocess boundaries.
- environment/credential sanitization and network reachability for model-controlled workers.
- exact mutation authority: filesystem, Git, GitHub, publish/merge/push.
- approval and budget/spend enforcement.
- execution receipts/evidence and false-success prevention.
- reviewed-SHA vs published/merged-SHA integrity.
- idempotency around retries and external effects.
- Gateway/Work projection of Builder state only where necessary to verify truthfulness.
- existing Builder tests plus focused hermetic restart/fault-injection tests where safe.

### Mandatory CHUNK 2 carry-forward check

Resolve SEC-001's open question: can a lower-trust Builder/model subprocess reach `127.0.0.1:4000/proxy/*` (or otherwise acquire equivalent Gateway authority) while being intentionally denied Gateway secrets/capabilities? Trace actual sandbox/network/env behavior. Do not assume.

### Collision rules

- PR #593 owns legacy `gateway/task_runner.py` deletion; do not duplicate it.
- Issue #592 owns `agent_runner` restart reconcile; that is not Builder unless a Builder path directly depends on it.
- Issue #545 owns MCP/Skill/plugin convergence; do not turn CHUNK 3 into an MCP project.
- AgentRouter is reported DONE by Jacob; verify only if Builder current truth materially depends on it.
- Check current open PRs/issues/branches before promoting any finding.

## Audit mode

- READ-ONLY for canonical source, Git state, GitHub state, runtime DBs/processes, config, dependencies and provider spend.
- No provider calls that can cost money.
- Temp files/DBs and hermetic tests outside canonical data are allowed.
- Do not stop/restart canonical services merely to prove a failure.
- Label evidence: VERIFIED CURRENT TRUTH / HISTORICAL TRUTH / INFERENCE / UNKNOWN.
- Collision status: NEW / ALREADY TRACKED / IN FLIGHT / FIXED ON CURRENT MAIN / STALE / DUPLICATE / DESIGN QUESTION.
- Performance claims: MEASURED / ESTIMATED / THEORETICAL.
- Prefer DELETE > SIMPLIFY > CONSOLIDATE > FIX > OPTIMIZE > REWRITE.
- No new architecture.

## Finding contract

Use stable IDs beginning `BLD-001`. For every finding include severity, confidence, exact location/functions, evidence/repro, failure path, user/ops/security/cost impact, collision, smallest fix direction and regression test. HIGH/CRITICAL findings require explicit regression-test type.

## Output

Save the complete report exactly to:

`/Users/jacobbrizinnski/Kitty-Audit-Sidecars/CHUNK3_BUILDER_REPORT.md`

Before finishing, verify the file exists and is complete. Do not modify the audit-support worktree or commit anything; a checkpoint coordinator will reconcile the report into the ledger before CHUNK 4 starts.

At the end print only a short completion receipt: repo SHA, finding IDs, high-risk IDs, report path, and `CHUNK 3 COMPLETE`.
