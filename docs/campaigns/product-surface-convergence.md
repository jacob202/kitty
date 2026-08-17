# Campaign: product-surface-convergence

**Goal:** Converge Kitty onto one coherent product surface per ADR 0027/0033 ratification, prove frontend+backend agree end-to-end, harden with contract tests and live multi-agent evaluation
**Branch:** fix/reconcile-run-finalize-and-status-20260817

A phase is `verified` only when `scripts/campaign.py verify` ran its
command to a pass AND recorded the commit below. Never hand-edit a
status to `verified`; `audit` will catch it.

## Phases

| # | Phase | Status | Verify command | Commit |
|---|-------|--------|----------------|--------|
| 1 | decision recorded | pending | `venv/bin/python3.12 -m pytest tests/test_surface_convergence_decision.py -q` | — |
| 2 | runtime truth endpoint | pending | `venv/bin/python3.12 -m pytest tests/test_capability_manifest.py -q` | — |
| 3 | openwebui home surface | pending | `venv/bin/python3.12 -m pytest tests/test_openwebui_home_extension.py -q` | — |
| 4 | builder status surface | pending | `venv/bin/python3.12 -m pytest tests/test_openwebui_builder_projection.py -q` | — |
| 5 | kitty-chat demoted to tested rollback | pending | `venv/bin/python3.12 -m pytest tests/test_surface_boundary.py -q` | — |
| 6 | live proof + agent eval evidence | pending | `venv/bin/python3.12 -m pytest tests/test_convergence_live_evidence.py -q` | — |

## Handoff

_(none yet — written by `campaign.py handoff`)_
