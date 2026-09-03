# OK-AUTOMATIONS-01 — Automations Has One Truthful Lifecycle

**Status:** draft candidate; not activated
**Roadmap phase:** 2 — primary surfaces

## Mission
Make Automations fully controllable and trustworthy from creation through delivery/history/recovery without duplicate external effects or “completed” runs that did not accomplish the user-visible outcome.

## Depends on
- `KT-AUTO-01` for known seed/delivery truth defects where still current.
- `KF-WHY-02` for explain/act-on-failure where still current.
- Existing cron/action/run stores remain authoritative.

## Product acceptance moment
Create or edit an automation, enable it, run it now, see what actually happened, understand why it did not run or deliver, retry safely when supported, change its schedule, restart Kitty, and confirm the schedule/history remain truthful.

## Required behavior
- Create/edit schedule uses one timezone contract and displays the effective next run plainly.
- Enable/disable survives restart and actually governs execution.
- Run-now is distinct from scheduled execution and creates an inspectable run/result.
- `completed` means the intended action outcome completed; source unavailable/condition false/delivery unavailable remain distinct.
- Retry is offered only when duplicate external effects are prevented or explicitly acknowledged by the owning action.
- Why/explain shows one useful cause plus a real recovery action when one exists.
- Editing a seeded automation does not create a duplicate on restart.
- History shows current/recent runs without requiring raw action names/cron syntax.
- Healthy silence and stale/failed scheduler heartbeat are distinguishable.

## Verification
**Tier 1:** automation/cron/action tests plus regressions for edit→restart, delivery failure, run-now and safe retry semantics.

**Tier 2:** desktop + iPhone-class running app: create/edit/enable/disable/run-now; restart; one source/delivery unavailable path; one supported retry path; no duplicate schedule/run claim.

**Tier 3:** independent reviewer can answer “will this run, when, what happened last time, and what can I do now?” entirely from the Automations surface.

## Non-goals
- New scheduler.
- Generic workflow engine.
- Silent automatic retry of external side effects.

## Done when
The Automations screen is sufficient to configure, understand and recover an automation without inferring truth from cron rows, logs, or terminal output.
