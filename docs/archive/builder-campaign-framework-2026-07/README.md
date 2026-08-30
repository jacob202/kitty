# Builder Campaign Framework (archived, verbatim)

Recovered from the stale branch `codex/campaign-p1-05` (forked 2026-07-14, last touched
2026-07-15, never merged). Tagged in full at `archive/builder-campaign-framework-2026-07`
before the branch was deleted.

## What this is

A design for running KittyBuilder as an autonomous multi-agent "campaign" — a 31-packet
implementation plan with an explicit state machine, kill switch, retry/escalation policy,
merge evidence gate, and phased rollout. It got 3/31 packets in before stopping on an
unresolved architecture question (see `campaign_state.json`) and was never resumed. The
runtime code this branch also built (`builder_scope.py`, `builder_identity.py`, etc.) was
independently superseded by what's live on `main` today — only this orchestration-layer
design is unique.

## Status: not yet integrated

These 4 files are kept verbatim for reference. They are **not** wired into KittyBuilder's
current design — do not treat any path, script, or doc reference inside them as live
(e.g. `docs/roadmap/BUILDER_IMPLEMENTATION_CAMPAIGN.md`, `scripts/docs_lint.py` may not
exist on `main` in this form). Adapting this into KittyBuilder's actual current
architecture (not verbatim) is tracked as a proposal — see the campaign-lifecycle work.

## Files

- `GOVERNANCE.md` — documentation ownership/review/deprecation/supersession process
- `BUILDER_CAMPAIGN_CONTROLLER.md` — runtime operating manual: state machine, stop
  conditions, retry policy, escalation thresholds, kill switch, phased rollout
- `BUILDER_CAMPAIGN_ORCHESTRATOR.md` — the orchestrator's own operating prompt
- `BUILDER_IMPLEMENTATION_CAMPAIGN.md` — the 31-packet work graph and dependency map
- `campaign_state.json` — actual run state at the point it stopped (3/31 complete)
