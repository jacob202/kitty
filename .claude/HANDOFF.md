# Handoff — main verified out of band; next move needs the Mac

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-09T08:41:35Z",
  "branch": "main",
  "worktree": "main",
  "status": "blocked",
  "completed_items": [
    "Verified main at ece1bad0341a7743681a0619e9266b186e8478d8 against every gate the Tests workflow defines, in a CI-equivalent container",
    "Established that GitHub Actions has run no workflow step since 2026-08-06: jobs get no runner, fail in 1-2 seconds, produce no logs, and return empty check output",
    "Merged and recorded the out-of-band verification receipt in docs/audit/MAIN_GATE_VERIFICATION_2026-08-09.md (#444)",
    "Repaired the STATE/HANDOFF agreement failure that #441 introduced and that turned main's test suite red"
  ],
  "blockers": [
    "GitHub Actions runners are blocked by the account billing/spending state; no branch change clears it and no PR check can go green until it is fixed",
    "This GitHub-connected container cannot inspect Jacob's Mac checkout, services, credentials, providers, or local Builder database"
  ],
  "next_action": "Clear the GitHub Actions billing block at https://github.com/settings/billing, then establish the live KPROOF-001 Mac baseline from the canonical checkout.",
  "parallel_work": [],
  "recommendations": [],
  "invalidation_conditions": [
    "main moves beyond ece1bad0341a7743681a0619e9266b186e8478d8, which makes the recorded gate results describe a commit that is no longer main",
    "GitHub Actions runners return, which restores automated verdicts and retires the out-of-band verification",
    "docs/ACTIVE_MISSION.md no longer names KPROOF-001 as the running mission",
    "live Mac or Builder evidence contradicts the repository/GitHub picture recorded here"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "head_sha": "ece1bad0341a7743681a0619e9266b186e8478d8"
}
-->

## What this handoff is

A repository-and-GitHub checkpoint, not a runtime one. It records what `main`
verifiably is and what is blocking, and nothing about Jacob's machine.

Do not resume any older session from this file. The Open WebUI #384 work and the
#441 authority reconciliation are both merged and finished; treat any reference
to them as history.

## Current authority

Read, in order:

1. `docs/ROADMAP.md` — KPROOF-001 is the current gate.
2. `docs/ACTIVE_MISSION.md` — the approved two-week Builder proof and acceptance contract.
3. `docs/PROJECT_STATUS.md` — repository/GitHub evidence and explicit unknowns.
4. `docs/audit/MAIN_GATE_VERIFICATION_2026-08-09.md` — why CI is red and what the gates actually say.
5. `.claude/STATE.md` — the current interactive checkpoint.

## The one thing blocking everything automated

GitHub Actions has executed no workflow step since 2026-08-06. Jobs are assigned
no runner and fail within two seconds, on every branch and every event type. It
is an account billing/spending state, visible only at
<https://github.com/settings/billing>, and no branch change clears it.

Until it clears, `make ci` is the gate. It was aligned to the workflow's exact
commands in #442, so a local pass and a CI pass now mean the same thing.

## Runtime boundary

GitHub evidence cannot establish the live Mac service state, local Builder queue,
credentials, providers, or running UI. A future local session must generate those
facts through supported probes; it must not fill them from this handoff.
