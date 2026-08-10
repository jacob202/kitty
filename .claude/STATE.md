# Session State — main was red on two gates; repair is on this branch

<!-- kitty-state
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

## Execution ownership

- owner: interactive GitHub-connected verification session
- active mission: `KPROOF-001`
- this branch carries one commit: the two-line gate repair plus this evidence

## What changed since the last checkpoint

The previous checkpoint verified `main` at `ece1bad`. `main` has since moved
seven commits, ending at `d54fd896`. That invalidated the recorded gate results,
so they were regenerated at the new HEAD.

`main` at `d54fd896` **fails `lint` and `typecheck`**. Both errors are in
`mcp/builder/context.py`, added by the KittyBuilder MCP bridge merge, which went
in as a direct-to-`main` squash with no green check. Full method, both failures,
and the repaired results:
[`docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md`](../docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md).

## Gate results with this branch's repair applied

| Gate | Result |
|---|---|
| ruff | All checks passed |
| mypy | no issues in 293 source files |
| pytest + coverage | 3987 passed, 2 deselected, 29 subtests, 78.38% vs 73% floor |
| vitest | 341 passed, 45 files |
| `next build` | compiled, TypeScript clean, 6/6 static pages |
| playwright smoke | 29 passed, 15 skipped (project-scoped by design) |
| vulture | exit 0, no findings |

Not covered: `lychee` needs outbound requests to every external URL in `docs/`;
`deptry`, `pip-audit`, and `bandit` are `continue-on-error` in the workflow.

One load-sensitive flake was observed and is recorded in the audit:
`test_killed_run_packet_recovers_end_to_end` failed once under concurrent build
load and passed in isolation and in both uncontended full-suite runs.

## Unknown until checked on Jacob's Mac

- canonical checkout/worktree state;
- Gateway, LiteLLM, Open WebUI, `kitty-chat`, and launchd state;
- current provider credentials/quotas;
- current Builder initiatives, packets, attempts, leases, runs, and budgets —
  the queue database does not exist in this container, so every Builder
  projection read `unavailable`, not empty;
- whether the merged #437 Builder action behavior works end to end in the
  running application.

## Exact next action

Merge this branch so `main` passes its own gates again.

Then, since Actions still cannot run, check which of the two causes the block is
— a failed payment method or an exhausted allowance — at
<https://github.com/settings/billing>.

Then, from the canonical Mac checkout, establish the live proof baseline:

```bash
cd ~/Projects/kitty
./kitty context --agent
./kitty status
./kitty doctor --json
./kitty builder initiative doctor --json
```

Until runners return, `make ci` is the gate. Do not infer missing runtime facts
from this file.
