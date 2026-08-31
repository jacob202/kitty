# KT-DEADLINE-01 — The deadline warning actually reaches the phone

**Initiative:** `kitty-finish-truth-20260831-v2`
**Owner:** builder
**Depends on:** `KT-AUTO-01` (both edit the cron-registration block in `gateway/app.py`)
**Free or paid:** free
**Base:** `origin/main` `295b92fc33a3f1b93da86f3c6bb5fbb54e367105`
**Findings:** `MOBILE-B001` and `MAIL-B001` — one gap described twice, not two packets

## What Jacob can do after this
Get a warning on his phone before a deadline bites, without running anything himself.

## Why this is the next thing
This is the reason the phone-channel work exists. `docs/packets/017-benefits-rails-urgent-sweep.md` cites a real $600 loss from a deadline nobody saw. The escalation is written, tested, and never called.

- `gateway/deadline_watch.py` exports `check_and_push`. Grepping `gateway/` and the `kitty` launcher finds no caller outside its own definition and its tests.
- `gateway/app.py` registers cron actions for `brief.deliver`, `brief.refresh`, `insights.return_due`, `monitors.check`, `inbox.scan`, `traces.compact`, `mail.poll`, `github.poll`, `experts.poll` and `prefetch.warm`. The string `deadline` does not appear in that file at all.
- `gateway/routes/deadlines.py:49` — `post_sweep(push: bool = False)`, and the UI's only caller sends no `push` argument.
- `kitty:685` — the CLI sweep calls `sweep(push_fn=None)`.

So all three reachable triggers — schedule, button, command — are independently wired off. Verified at the base SHA above.

**The button and the command do not run the deadline watch at all.** Both call `gateway/deadline_sweep.py`'s `sweep()`, which is a different feature: it discovers new deadlines from documents and mail signals, then pushes one daily summary of the single most urgent item under the dedupe key `sweep-{date}`. `deadline_watch.check_and_push` walks every open deadline against a per-deadline escalation checkpoint. Turning `push` on without deciding between them would leave two notification paths firing from one button press, which this packet forbids.

## Plan
1. Read `gateway/deadline_watch.py`, `gateway/deadline_sweep.py`, `gateway/routes/deadlines.py`, the cron-registration block in `gateway/app.py`, and `cmd_sweep` in `kitty`.
2. Write the failing tests first: a registered scheduled action runs the watch and calls the push facade for a deadline inside the window; the sweep route escalates by default; the CLI goes through the same path; the discovery scan still records what it finds. Run them and watch them fail.
3. Register the deadline watch as a scheduled automation action beside the existing ones, using the same registration shape they use.
4. Keep `deadline_sweep`'s discovery scan exactly as it is, and remove its own `sweep-{date}` summary push. Escalation becomes `check_and_push`'s job, so one sweep reports every deadline that has crossed a checkpoint instead of only the most urgent one.
5. Turn `push` on by default in the route so pressing the button does the whole job, and have the response say how many deadlines were escalated.
6. Point the CLI at the same path as the route rather than a second one.
7. Make the no-channel-configured case say plainly that nothing could be delivered, instead of reporting an escalation that did not happen.
8. Re-run all five named test files.

The risk is steps 4 and 5 together: turning escalation on by default means a real notification can now fire. Keep the existing quiet-hours and dedupe behaviour of the push facade exactly as it is — that is what stops this becoming noise.

## Not in scope
What counts as an approaching deadline. The push facade, its channels, quiet hours, or dedupe rules. Any second notification path. Deadline extraction, including how `deadline_sweep` discovers deadlines from documents and mail — that scan keeps working unchanged. The Home deadlines card, which is a separate finding.

## Verification
**Tier 1 — mechanical.** `python -m pytest -q tests/test_deadline_watch.py tests/test_deadline_sweep.py tests/test_deadlines_routes.py tests/test_brief_deadlines.py tests/test_cron.py`. Today nothing asserts that anything in production calls `check_and_push`; the tests you add must fail against the base SHA and pass after. Tests must use a stub push function and must never send a real notification.

**Tier 2 — running app.** Extend a smoke spec covering the Home sweep control reporting an escalation count, and reporting honestly when no channel is configured. Builder cannot run this; CI does.

**Tier 3 — product acceptance.** Required (D-008), and this one matters more than most because a wrong result is a missed deadline. An independent reviewer, on the running product at desktop and iPhone-class widths: with a push channel configured, seed a deadline inside the window and confirm the notification arrives; then with no channel configured, confirm the sweep says nothing was delivered rather than claiming success.

## Stop condition
If registering the action requires changing what the push facade does — its channels, quiet hours, or dedupe — stop. Reuse it or escalate; do not fork it.

## Recovery
If this fails part-way, the dangerous half-state is a registered schedule with the escalation path incomplete. Confirm no schedule row was left registered for an action that does not resolve, then restart at step 2. `KT-AUTO-01` must be landed first; if it is not, stop — both packets edit the same registration block.
