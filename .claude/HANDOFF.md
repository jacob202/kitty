# Handoff — CI is back; main is green and verified by real runners

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-11T00:07:00Z",
  "branch": "claude/next-4gj621",
  "worktree": "main",
  "status": "awaiting_review",
  "completed_items": [
    "Verified main at d54fd8966edd1f8a14802ed19e26a07917498caf out of band and found it red on lint (ruff I001) and typecheck (mypy assignment), both in mcp/builder/context.py",
    "Established that the GitHub Actions outage ended on 2026-08-10 between 23:03Z and 23:20Z: runs went from 3-13 second no-runner failures to 200-314 second real executions",
    "Confirmed Tests passes on main at 6de35bde4da298ca7e1c51401397eda201bf6dcc in a real 275-second CI run",
    "Recorded both findings in docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md and corrected docs/PROJECT_STATUS.md, which still declared CI dead",
    "Dropped this branch's code repair as redundant: #453 fixed both failures independently, plus a third in gateway/image_quality.py, and added scripts/hooks/pre-push"
  ],
  "blockers": [
    "This GitHub-connected container cannot inspect Jacob's Mac checkout, services, credentials, providers, or local Builder database"
  ],
  "next_action": "Establish the live KPROOF-001 Mac baseline from the canonical checkout; CI no longer blocks anything.",
  "parallel_work": [
    {
      "kind": "pull_request",
      "ref": "#450 feat: ratify architecture governance and harden Builder boundaries (docs/architecture-ratification-governance)",
      "owner": "unknown; not this session",
      "observed_at": "2026-08-11T00:05:00Z",
      "touches": [
        "AGENTS.md",
        "START_HERE.md",
        "docs/AUTHORITY_MAP.md",
        "gateway/actions/",
        "gateway/builder_commands.py",
        "gateway/builder_initiative.py",
        "artifacts/proof/live-audit/",
        "196 paths; no overlap with this branch; its Tests run fails for real, not from the outage"
      ]
    }
  ],
  "recommendations": [],
  "invalidation_conditions": [
    "main moves beyond 6de35bde4da298ca7e1c51401397eda201bf6dcc, which makes the recorded CI verdict describe a commit that is no longer main",
    "GitHub Actions stops executing again, which would restore the need for out-of-band verification",
    "docs/ACTIVE_MISSION.md no longer names KPROOF-001 as the running mission",
    "live Mac or Builder evidence contradicts the repository/GitHub picture recorded here"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "head_sha": "6de35bde4da298ca7e1c51401397eda201bf6dcc"
}
-->

## What this handoff is

A repository-and-GitHub checkpoint, not a runtime one. It records what `main`
verifiably is and what is blocking, and nothing about Jacob's machine.

Do not resume any older session from this file. The Open WebUI #384 work and the
#441 authority reconciliation are both merged and finished; treat any reference
to them as history.

## The headline: the Actions outage is over

Between 23:03Z and 23:20Z on 2026-08-10, `Tests` runs went from 3–13 second
no-runner failures to 200–314 second real executions. `main` at `6de35bde`
**passes `Tests`** in a genuine 275-second run.

Two consequences:

1. Out-of-band gate verification is retired. `make ci` is no longer the only
   gate; CI is authoritative again.
2. Red checks are information again. #450's failing `Tests` run is a real result
   about that branch's code, not outage noise. Any document still describing red
   checks as meaningless is describing the pre-23:20Z window only.

## What `main` was, before that

`d54fd896` failed `lint` and `typecheck`, both in `mcp/builder/context.py`, added
by the KittyBuilder MCP bridge as a direct-to-`main` squash with no green check.
Confirmed out of band here; fixed independently in #453, which also found a third
failure this verification missed (`gateway/image_quality.py`) and added
`scripts/hooks/pre-push`.

The unexplained part is the miss: reproducing the workflow's exact `lint` and
`typecheck` commands surfaced two failures where #453 found three. Worth
understanding before trusting a container reproduction again.

## Current authority

Read, in order:

1. `docs/ROADMAP.md` — KPROOF-001 is the current gate.
2. `docs/ACTIVE_MISSION.md` — the approved two-week Builder proof and acceptance contract.
3. `docs/PROJECT_STATUS.md` — repository/GitHub evidence and explicit unknowns.
4. `docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md` — when CI came back, and what the gates said before it did.
5. `.claude/STATE.md` — the current interactive checkpoint.

## What is still open

Nothing server-side stops an unchecked merge to `main`. The default-branch
ruleset that would require passing checks (issue #399) is still disabled, and
#453's pre-push hook is local only. `d54fd896` is the worked example of what that
allows.

## Runtime boundary

GitHub evidence cannot establish the live Mac service state, local Builder queue,
credentials, providers, or running UI. Builder's queue database does not exist in
this container, so its projections read `unavailable`, not empty. A future local
session must generate those facts through supported probes; it must not fill them
from this handoff.
