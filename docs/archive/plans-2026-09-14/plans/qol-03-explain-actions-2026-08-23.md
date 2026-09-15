# QoL Packet 03 — Why Didn't This Happen?

**Status:** Implementation plan for Jacob approval (not self-authorizing)
**Packet:** `docs/quality_of_life_packets.md` PACKET 03 — WHY DIDN'T THIS HAPPEN? (P0)
**Branch:** `feat/explain-actions-20260823` (worktree `/Users/jacobbrizinnski/Projects/kitty-explain-20260823`)
**Base:** origin/main `ad5b4967`

## Objective

Eliminate silent failure. Every meaningful automation/action answers *"Why didn't this
happen?"* truthfully — including non-execution. "Nothing happened" must never be
represented merely by absence of a row when the system can know why.

## Constraints

- Use existing **Automation Run** evidence (`gateway/automation_runs.py`, #550). Do **not**
  invent a parallel explanation store.
- Do **not** create fake run records for things genuinely never due.
- Preserve existing #550 Automation Run semantics and #552 memory semantics.
- Read-only explanation surface where possible; the only writes allowed are the existing
  run-ledger transitions (begin/claim/finish/reconcile) already in place.
- Do not modify Builder execution governance.

## Required outcome vocabulary (map to existing sources)

| Required outcome | Source / derivation |
|---|---|
| not yet due | `cron.explain_schedule(s)` → state `not_due`, reason "next occurrence is not due yet" |
| disabled | `cron` schedule `enabled=0` (explain must say disabled) |
| already claimed | `automation_runs` run row exists with running/completed terminal status for that schedule occurrence |
| source unavailable | `automation_runs` terminal `source_unavailable` |
| condition false | `automation_runs` terminal `condition_false` |
| policy refused | `automation_runs` terminal `policy_refused` |
| approval required | `action_grants.evaluate` → Decision not allowed with ask/deny reason |
| grant expired | `action_grants` grant `expires_at` passed |
| grant revoked | `action_grants` grant `revoked_at` set |
| action unavailable | `automation_runs` terminal `action_unavailable` |
| execution failed | `automation_runs` terminal `failed` |
| interrupted | `automation_runs` terminal `interrupted` (incl. reconcile_interrupted_runs on restart) |
| completed | `automation_runs` terminal `completed` |

## Explanation shape

Every explanation contains: **Status, Reason, Relevant timestamp, Action, Automation,
Evidence, Next step.** For a given automation (cron schedule or manual action), the
surface resolves the true answer by checking, in order:

1. Was the automation enabled and due? (`cron.list_schedules` + `explain_schedule`)
2. Does a run ledger row exist for this occurrence? (claimed / running / terminal)
3. If no row but due-and-enabled and not claimed — report the execution gap with the
   supervising status (`supervisor.get_status("cron")`) as evidence (e.g. cron not
   running / stale → the true reason the schedule didn't fire).
4. Manual action: `action_grants.evaluate` outcome for the capability → approval
   required / grant expired / grant revoked / policy refused.
5. Latest run row terminal status → failed / interrupted / completed with error and
   timestamp.

## Deliverables

1. **`gateway/why_not.py`** — `explain_automation(action_name_or_schedule_id, *, now) ->
   Explanation` implementing the ordered resolution above, composing `cron`, the
   automation-run ledger, `action_grants`, and the supervisor. Pure function; no writes.
2. **Route(s)** in `gateway/routes/automations.py`:
   - `GET /automations/{action}/why` — explanation for an action (latest manual/scheduled
     evidence).
   - `GET /automations/schedules/{schedule_id}/why` — explanation for one schedule.
   Each returns the full Explanation shape (status, reason, relevant timestamp, action,
   automation, evidence, next step).
3. **UI** — where automations are listed, render an "Why didn't this happen?" affordance
   per automation showing the Explanation shape.

## RED tests first

`tests/test_why_not.py` — matrix covering every required outcome:

1. not yet due (schedule future) → status not-due, reason "next occurrence is not due yet".
2. disabled (enabled=0) → reason disabled.
3. already claimed (run row exists for occurrence) → reason already claimed.
4. source unavailable terminal run → reason source unavailable.
5. condition false terminal run → reason condition false.
6. policy refused terminal run → reason policy refused.
7. manual action with grant ask/deny → approval required.
8. expired grant → grant expired (uses evaluate with past expires_at).
9. revoked grant → grant revoked.
10. action unavailable terminal run → reason action unavailable.
11. failed terminal run → reason execution failed with error.
12. interrupted (reconciled on restart) → reason interrupted.
13. completed → status completed.
14. due but no run row and cron supervisor stale/stopped → reports execution gap with
    supervisor evidence (never silently "nothing happened").
15. no fake rows: schedule genuinely never due leaves no new run row.

## Acceptance

1. RED tests fail before implementation; GREEN after smallest implementation.
2. Every supported automation can produce a truthful explanation for non-execution.
3. Verified live for at least one real schedule (not-due + disabled + one failed run).
4. No new database table / store; diff review confirms run ledger is the only evidence
   source.
5. Ruff + mypy clean on changed files.

## Deferred / out of scope

- Builder initiative/task explanation (separate surface, own governance).
- Explainable Memory (Packet 04) and Safe Self-Recovery (Packet 05).
