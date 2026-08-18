# Campaign: product-surface-convergence

**Goal:** Make Kitty's native UI the one coherent product surface (ADR 0039).
**Branch:** `feat/product-surface-convergence-20260817`
**Recovery base:** `37d3a4eb1f7bdcb7cc84b19dadea519003933cd6`

The pre-wipe local campaign history was not pushed. Historical local pass counts are not treated as current verification. This ledger records only GitHub-restored work from the recreated branch.

| # | Phase | Status | Verification target | Commit |
|---|---|---|---|---|
| 1 | decision recorded | in progress | `tests/test_surface_convergence_decision.py` | — |
| 2 | runtime truth covered | pending | `tests/test_capability_manifest.py` | — |
| 3 | presets tell the truth | pending | `tests/test_model_presets.py` + routing/config tests | — |
| 4 | shortlist carries decision info | pending | `tests/test_model_presets.py` | — |
| 5 | picker exposed over HTTP | pending | `tests/test_model_picker_route.py` | — |
| 6 | home dashboard converged | pending | Home frontend/contract tests + live viewport proof | — |
| 7 | image cost estimate + durable batches | pending | image estimate/queue + frontend tests | — |
| 8 | frontend and backend agree | pending | `tests/test_surface_contract_parity.py` | — |
| 9 | live proof + agent eval | pending | live evidence artifact + adversarial review | — |

## Handoff

**Single next action:** add and verify the phase-1 decision contract against ADR 0039, then restore the capability/runtime truth layer.
