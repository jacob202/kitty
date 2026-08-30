# Builder Agent Operability Design

**Approved:** Jacob, 2026-08-30, via explicit instruction to implement the reliability research recommendations.

## Goal

Make KittyBuilder materially safer and more measurable without adding a second queue, scheduler, model registry, or learning store.

## Existing rails we reuse

- Builder queue SQLite remains execution authority.
- ADR 0038 remains the crash/recovery contract.
- Compute Governor remains spend authority and durable model-work receipt store.
- `builder_contract` remains the packet/acceptance contract seam.
- `builder_paid_routing` remains the paid model policy seam.
- `session_learning` remains the durable workflow-learning signal store and promotion gate.

## Decisions

### 1. Agent-operable side effects

Add a Builder-owned operation receipt in the existing Builder SQLite database. Each operation has a stable `invocation_id`, `idempotency_key`, request fingerprint, effect class, and durable lifecycle:

`requested -> accepted -> running -> succeeded | failed | unknown`

Effect classes are `none`, `idempotent`, `reconcilable`, and `at_most_once`. An `unknown` outcome is never retried until a postcondition verifier resolves whether the effect happened. Reusing an idempotency key with different request content fails closed.

### 2. Explicit workflow compilation

Extend Builder contracts with optional explicit steps. Compilation normalizes artifact inputs/outputs, validation commands, and control transfer. Legacy contracts compile to one explicit execution step, so callers can adopt the representation incrementally.

### 3. Model handoff and harness policy

Keep model/provider choice in the existing paid-routing seam. Add deterministic handoff policy:

- same tier: continue;
- cheaper/weaker -> stronger: pass durable artifacts plus compact context, not the full weak trajectory;
- stronger -> cheaper/weaker: preserve the stronger trajectory.

Select one of four bounded harness profiles: `coding`, `research`, `review`, `recovery`. Do not build a harness-generating model.

### 4. Paired capability evaluation

Use matched task keys to compare baseline and candidate capability scores. Unmatched comparisons fail rather than pretending causality. The result records pair count, baseline/candidate means, absolute lift, and whether the configured minimum lift was met.

### 5. Persistent learning without a new store

Convert positive paired-evaluation evidence into the existing workflow-signal format. Repeated evidence promotes through `session_learning`'s existing conservative promotion rule. Raw execution history stays separate from distilled learning signals; skill/packet changes remain explicit code/versioned work.

### 6. Routing/spend trace

Compute Governor work receipts gain an optional JSON policy snapshot recording the selected harness, handoff policy, candidate/fallback order, and budget context. Existing per-attempt paid-route ceilings plus the CAD 6/week governor remain the hierarchical spend limits. No silent paid fallback is introduced.

## Non-goals

- No automatic PR merge, paid execution, credentials, or environment changes.
- No new distributed system, event bus, scheduler, or second Builder state machine.
- No automatic skill rewriting.
- No changes to active PR #677 Work/supervisor implementation.
- No changes to the concurrently owned retry-base-fence files.
