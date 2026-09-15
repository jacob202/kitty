# Campaign: product-surface-convergence

**Goal:** Make Kitty's native UI the one coherent product surface (ADR 0039).
**Branch:** `feat/product-surface-convergence-20260817`
**Recovery base:** `37d3a4eb1f7bdcb7cc84b19dadea519003933cd6`

The pre-wipe local campaign history was not pushed. Historical local pass counts are not treated as current verification. This ledger records only GitHub-restored work from the recreated branch.

| # | Phase | Status | Evidence / remaining gate |
|---|---|---|---|
| 1 | decision recorded | verified in CI | ADR 0039 contract is covered by `tests/test_surface_convergence_decision.py`. |
| 2 | runtime truth covered | verified in CI | Runtime manifest coverage is exercised by `tests/test_capability_manifest.py` and the full pytest suite. |
| 3 | presets tell the truth | verified in CI | Model preset/routing coverage passes; unavailable choices are not silently aliased. |
| 4 | shortlist carries decision info | verified in CI | Curated picker metadata is covered by model preset/picker tests. |
| 5 | picker exposed over HTTP | verified in CI | Picker route + frontend tests pass; curated metadata cannot introduce a model absent from runtime availability, and unknown live availability fails closed. |
| 6 | home dashboard converged | implemented + CI/browser verified | Frontend tests/build/browser smoke pass. Final policy still requires an independent reviewer completing the task in the running app. |
| 7 | image cost estimate + durable batches | implemented + CI/browser verified | Estimate/batch/session/cancel/reload contracts and mobile Image Lab smoke pass. No claim of a real paid renderer run is made. |
| 8 | frontend and backend agree | verified in CI | `tests/test_image_lab_frontend_route_parity.py` guards important Image Lab network controls against registered Gateway routes; full CI is green. |
| 9 | live proof + independent evaluation | blocked / not complete | GitHub CI supplies hermetic browser evidence, including browser → real Gateway → temp DB for Chat, but the original Mac is gone and there is no independent running-app task-completion review or real renderer proof yet. |

## Current exact-head evidence

GitHub Tests run #1797 passed on head `5e587c832ad1a0b4420e25a338cac7991823d978`: pytest, Ruff, mypy, hygiene, frontend unit tests, Next production build, browser smoke, and the hermetic browser → real Gateway → temporary DB seam all succeeded.

The PR policy is intentionally still blocking merge because this is user-facing work without completed independent running-app acceptance and because the PR is large enough to require explicit exact-head large-change approval. Do not bypass either gate.

## Handoff

**Single next action:** obtain Phase 9 running-product acceptance from a reviewer who did not implement the change. Once that evidence exists, bind the required large-change approval to the then-current full head SHA, rerun policy/CI, and only then consider marking the PR ready or merging.
