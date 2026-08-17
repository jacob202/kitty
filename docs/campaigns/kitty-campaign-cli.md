# Campaign: kitty-campaign-cli

**Goal:** Wire 'campaign' into the ./kitty launcher so the harness is reachable without venv paths
**Branch:** fix/reconcile-run-finalize-and-status-20260817

A phase is `verified` only when `scripts/campaign.py verify` ran its
command to a pass AND recorded the commit below. Never hand-edit a
status to `verified`; `audit` will catch it.

## Phases

| # | Phase | Status | Verify command | Commit |
|---|-------|--------|----------------|--------|
| 1 | launcher dispatch | pending | `venv/bin/python3.12 -m pytest tests/test_campaign_cli.py -q` | — |
| 2 | ledger tests still green | pending | `venv/bin/python3.12 -m pytest tests/test_campaign_ledger.py -q` | — |
| 3 | launcher suite gate | pending | `venv/bin/python3.12 -m pytest tests/test_kitty_launcher.py tests/test_campaign_cli.py tests/test_campaign_ledger.py -q` | — |

## Handoff

_(none yet — written by `campaign.py handoff`)_
