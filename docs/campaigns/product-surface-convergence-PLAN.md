# Product Surface Convergence — execution plan

Branch: `feat/product-surface-convergence-20260817`
ADR: `docs/adr/0039-kitty-native-product-surface.md`

## Goal

Make Kitty's native UI the one coherent product surface, with frontend and backend describing the same durable reality. Preserve strong commodity patterns from Open WebUI without maintaining two overlapping primary shells.

## Recovery note

The original local campaign branch was lost with the 2026-08-17 Mac wipe before it was pushed. This remote branch was recreated from GitHub `main` at `37d3a4eb1f7bdcb7cc84b19dadea519003933cd6`. Prior local verification results are historical evidence only; every restored phase must be reimplemented and reverified from GitHub/CI.

## Product requirements that must survive simplification

### Model picker

Curate aggressively, inform sufficiently. Keep a narrow current shortlist of best serious choices while showing decision-relevant model/provider/capability/cost/availability information. Preserve manual model control. Do not claim quality or latency without evidence.

### Image Lab

Dedicated first-class workspace. Conversational control inside the workspace, persistent visual history, easy image/reference selection and combination, 1/2/4 output batching, durable queue, cost estimate before dispatch, honest duration estimate when grounded, and reattachment after navigation/reload.

### State truth

Backend is the durable source of truth. Home, Builder/Activity, model availability, and Image Lab must not invent local states that disagree with server state. Browser reload is a correctness test.

## Phases

1. **Decision recorded** — ADR 0039 exists and explicitly chooses Kitty native UI as canonical while preserving the model-picker and dedicated Image Lab requirements.
2. **Runtime truth covered** — `/runtime/manifest` exposes the user-facing capability/state facts required by the shell without pretending to own unrelated domain data.
3. **Presets tell the truth** — curated model presets resolve to configured/discovered models and never silently alias unavailable choices.
4. **Shortlist carries decision info** — picker payload includes the small set of decision-relevant facts and clearly distinguishes measured facts from heuristics/unknowns.
5. **Picker exposed over HTTP** — frontend consumes one canonical backend picker contract with explicit stale/missing discovery behavior.
6. **Home dashboard converged** — coherent bento/dashboard hierarchy; one global runtime outage explanation; no overlapping mascot/composer/cards; page scroll ownership is correct.
7. **Image cost estimate + durable batches** — observed/provider-grounded cost facts, honest duration estimates, 1/2/4 durable batch jobs, queue/restart/cancel semantics, persistent Studio session.
8. **Frontend/backend contract parity** — every important Home and Image Lab network control maps to a real registered endpoint/method and matching request enum/schema.
9. **Live proof + independent evaluation** — real user journeys against the running product, cheap-agent synthetic users from different perspectives, then stronger adversarial product/frontend/backend/reliability review.

## Verification philosophy

A phase is not complete because code looks right. Prefer tests that prove the boundary most likely to lie: schema/route parity, durable state, reload/reconcile behavior, paid-spend boundaries, and live user-visible journeys. Re-run verification on the environment that will actually ship.

## Deliberately not doing

- A second model registry.
- A second primary frontend merely to preserve sunk cost.
- Open WebUI extensions unless a concrete surviving product requirement needs them.
- Static marketing-style quality rankings presented as measurements.
- Provider-specific image prompt syntax exposed as the normal user workflow.
- A decorative dashboard that duplicates backend telemetry instead of answering user questions.

## Single next action

Restore phase 1 verification on GitHub, then rebuild the runtime/model contract in small CI-verified commits. Do not jump directly to visual polish while the truth contracts are missing.