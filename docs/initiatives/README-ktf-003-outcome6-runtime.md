# KTF-003 — Outcome 6 runtime gate

Status: superseded execution input. The Outcome 6 runtime anchors are present
on current `main` via `f9dfb6a`, but the original Builder tasks are
cancelled/failed and their immutable literal-edit instructions are no longer
safe to replay. Reconcile the evidence through
`ktf-001-resume-proof-v2.json` before authoring any replacement packet or
starting the daylight proof.

## Why this exists

The current initiative driver pauses the whole initiative after any exhausted packet, despite ADR 0021 requiring unrelated eligible work to continue. It also lacks a distinct, budget-neutral provider-exhaustion path. A daylight run on current `main` therefore cannot honestly satisfy Phase 1 Outcome 6.

## Historical order

1. `KTF-FE-04-continue-unrelated-after-failure`
2. `KTF-FE-05-provider-exhaustion-pause`
3. Re-run targeted and full validation on merged `main`.
4. Apply the approved daylight-proof initiatives on the canonical Mac.
5. Run the free Builder pass and compare its report with Git, GitHub, queue, attempt, lease, validation, review, and publication evidence.

The preserved order explains the intended proof; it is not an instruction to
rerun the superseded manifest.

## Validation

```bash
./kitty builder initiative validate docs/initiatives/ktf-003-outcome6-runtime-v1.json
```

Validation proves authoring structure only. The runtime behavior is proven by the packet tests and the subsequent daylight dogfood run.
