# Handoff — main was red on two gates; repair is on this branch

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-10T23:35:00Z",
  "branch": "claude/next-4gj621",
  "worktree": "main",
  "status": "awaiting_review",
  "completed_items": [
    "Re-verified main at d54fd8966edd1f8a14802ed19e26a07917498caf against every gate the Tests workflow defines, in a CI-equivalent container",
    "Found main red on lint (ruff I001) and typecheck (mypy assignment), both in mcp/builder/context.py, added by the KittyBuilder MCP bridge merge",
    "Repaired both without changing runtime behaviour; all reproducible gates now pass",
    "Confirmed the GitHub Actions outage has not lifted: 30 most recent runs, 0 successes, 3-13 second durations",
    "Recorded the receipt in docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md"
  ],
  "blockers": [
    "GitHub Actions runners are blocked by the account billing/spending state; no branch change clears it and no PR check can go green until it is fixed",
    "This GitHub-connected container cannot inspect Jacob's Mac checkout, services, credentials, providers, or local Builder database"
  ],
  "next_action": "Merge the claude/next-4gj621 gate repair so main is green again, then clear the GitHub Actions billing block at https://github.com/settings/billing and establish the live KPROOF-001 Mac baseline from the canonical checkout.",
  "parallel_work": [
    {
      "kind": "pull_request",
      "ref": "#450 feat: ratify architecture governance and harden Builder boundaries (docs/architecture-ratification-governance)",
      "owner": "unknown; not this session",
      "observed_at": "2026-08-10T23:12:00Z",
      "touches": [
        "AGENTS.md",
        "START_HERE.md",
        "docs/AUTHORITY_MAP.md",
        "gateway/actions/",
        "gateway/builder_commands.py",
        "gateway/builder_initiative.py",
        "artifacts/proof/live-audit/",
        "196 paths total; no overlap with this branch"
      ]
    },
    {
      "kind": "pull_request",
      "ref": "#449 docs: specify KittyBuilder MCP v2 dogfood proof (docs/kittybuilder-mcp-v2-dogfood)",
      "owner": "unknown; not this session",
      "observed_at": "2026-08-10T23:12:00Z",
      "touches": [
        "docs/superpowers/plans/2026-08-10-kittybuilder-mcp-v2-dogfood.md",
        "docs/superpowers/specs/2026-08-10-kittybuilder-mcp-v2-dogfood-design.md"
      ]
    }
  ],
  "recommendations": [],
  "invalidation_conditions": [
    "main moves beyond d54fd8966edd1f8a14802ed19e26a07917498caf, which makes the recorded gate results describe a commit that is no longer main",
    "GitHub Actions runners return, which restores automated verdicts and retires the out-of-band verification",
    "docs/ACTIVE_MISSION.md no longer names KPROOF-001 as the running mission",
    "live Mac or Builder evidence contradicts the repository/GitHub picture recorded here"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "head_sha": "d54fd8966edd1f8a14802ed19e26a07917498caf"
}
-->

## What this handoff is

A repository-and-GitHub checkpoint, not a runtime one. It records what `main`
verifiably is and what is blocking, and nothing about Jacob's machine.

Do not resume any older session from this file. The Open WebUI #384 work and the
#441 authority reconciliation are both merged and finished; treat any reference
to them as history.

## The finding

`main` at `d54fd896` does not pass its own gates. `mcp/builder/context.py`, added
by the KittyBuilder MCP bridge merge, fails `ruff` (I001, un-sorted import block)
and `mypy` (`None` assigned to a `str`-inferred variable). Neither affects
runtime behaviour and the module's own tests pass, but both would fail the
`Tests` workflow if it could run.

That merge reached `main` as a direct squash with no green check. Actions cannot
run, and the default-branch ruleset that would require checks is disabled
(issue #399), so nothing in the current setup could have stopped it. This is the
second consecutive checkpoint where `main` was left red by a merge no gate
examined.

## Current authority

Read, in order:

1. `docs/ROADMAP.md` — KPROOF-001 is the current gate.
2. `docs/ACTIVE_MISSION.md` — the approved two-week Builder proof and acceptance contract.
3. `docs/PROJECT_STATUS.md` — repository/GitHub evidence and explicit unknowns.
4. `docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md` — why CI is red, what the gates actually say, and the two failures at `d54fd896`.
5. `.claude/STATE.md` — the current interactive checkpoint.

## The one thing blocking everything automated

GitHub Actions has still executed no workflow step. Of the 30 most recent runs
(2026-08-10 22:16Z through 23:04Z) none succeeded and every one ended in 3–13
seconds, the same no-runner pattern first recorded on 2026-08-09. It is an
account billing/spending state, visible only at
<https://github.com/settings/billing>, and no branch change clears it.

Until it clears, `make ci` is the gate. It was aligned to the workflow's exact
commands in #442, so a local pass and a CI pass now mean the same thing — and
running it before merge would have caught both of these failures.

## Runtime boundary

GitHub evidence cannot establish the live Mac service state, local Builder queue,
credentials, providers, or running UI. Builder's queue database does not exist in
this container, so its projections read `unavailable`, not empty. A future local
session must generate those facts through supported probes; it must not fill them
from this handoff.
