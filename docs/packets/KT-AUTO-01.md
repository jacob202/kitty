# KT-AUTO-01 — Automations stop reporting success they did not achieve

**Initiative:** `kitty-finish-truth-20260831-v1`
**Owner:** builder
**Depends on:** none
**Free or paid:** free
**Base:** `origin/main` `295b92fc33a3f1b93da86f3c6bb5fbb54e367105`
**Findings:** `AUTO-B001`, `AUTO-B002`, `AUTO-B004`

## What Jacob can do after this
Trust the Automations screen: if it says the morning brief went out, it went out, and the time he set is still the time he set.

## Why this is the next thing
Three linked untruths in the one automation Jacob actually depends on.

1. `gateway/brief_scheduler.py:125-133` — when `push_to_jacob` accepts on no channel, the code logs a warning and returns the brief text anyway, so `gateway/automation_actions.py` records the run as `completed`. The status vocabulary already has the right word: `ACTION_RESULT_STATUSES` at `gateway/automation_actions.py:17` is `{"completed", "source_unavailable", "condition_false"}`. Nothing new needs inventing.
2. `gateway/app.py:292-298` — every gateway start calls `cron.ensure_schedule` with `load_brief_time()` read from `config/user_profile.json`, and no route or UI writes that file. Change the brief time in the app and the next restart silently reverts it.
3. `gateway/cron.py:151-166` — the duplicate check keys on the exact tuple of action, schedule type, schedule value and metadata. Edit a seeded schedule and the key no longer matches, so the next startup seeds a second copy of it.

All three verified present at the base SHA above.

## Plan
1. Read `gateway/brief_scheduler.py`, `gateway/automation_actions.py`, `gateway/cron.py`, and the cron-registration block at the end of `gateway/app.py`.
2. Write the failing tests first: a brief run with no accepting channel records `source_unavailable`; a brief time changed after first start survives a restart; editing a seeded schedule then restarting leaves one row, not two. Run them and watch them fail.
3. Make the brief action return `source_unavailable` when no channel accepted, and `completed` when one did. The reason a person reads must not require knowing what a "channel" is.
4. Make startup stop overwriting a schedule that has been changed since it was seeded, while still seeding it on a machine that has none.
5. Make seeding recognise an existing seeded schedule that has since been edited, instead of adding a second one.
6. Re-run the four named test files.

The risk is step 4 and 5: you need a way to tell "seeded and untouched" from "seeded and then edited" without deleting anything. Preserve every existing schedule and run row — do not resolve duplicates by pruning.

## Not in scope
The content of the brief. The push facade itself, including quiet hours and dedupe. The Automations UI. Any other automation action. Wiring the deadline watch — that is `KT-DEADLINE-01`, which depends on this packet.

## Verification
**Tier 1 — mechanical.** `python -m pytest -q tests/test_brief_scheduler.py tests/test_cron.py tests/test_automation_actions.py tests/test_app_automation_supervision.py`. Today nothing asserts the three behaviours above; the tests you add must fail against the base SHA and pass after.

**Tier 2 — running app.** Add or extend a spec under `gateway/kitty-chat/tests/smoke/` covering the Automations screen showing a `source_unavailable` brief run as not-delivered. Builder cannot run this — it has no `node_modules` — so it runs in CI. Record here that it is CI-proved, not worker-proved.

**Tier 3 — product acceptance.** Required (D-008). An independent reviewer, on the running product at desktop and iPhone-class widths: set a brief time, restart Kitty, confirm the time held; then with no push channel configured, run the brief and confirm the screen does not claim it was delivered.

## Stop condition
If telling an edited schedule from an untouched one needs a new column or a migration, stop and say so. A schema change is a separate decision.

## Recovery
No repository-destructive steps. If the run fails part-way, re-read the four modules and restart at step 2. The tests must use a temporary data root; never point them at the real Kitty database.
