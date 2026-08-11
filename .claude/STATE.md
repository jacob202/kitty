# Session State — CI is back; main is green and verified by real runners

<!-- kitty-state
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

## Execution ownership

- owner: interactive GitHub-connected verification session
- active mission: `KPROOF-001`
- this branch carries evidence and status corrections only; no code change

## What changed since the last checkpoint

The previous checkpoint verified `main` at `ece1bad` and recorded the Actions
outage as ongoing. Both facts expired during this session.

`main` moved seven commits to `d54fd896`, which **failed `lint` and
`typecheck`** — both in `mcp/builder/context.py`, added by the KittyBuilder MCP
bridge as a direct-to-`main` squash with no green check. That was confirmed out
of band here and fixed independently in #453, which found a third failure this
verification missed (`gateway/image_quality.py`) and added a local pre-push gate.

Then the outage lifted. Between 23:03Z and 23:20Z on 2026-08-10, `Tests` runs
went from 3–13 second no-runner failures to 200–314 second real executions.
`main` at `6de35bde` **passes `Tests`** in a genuine 275-second run.

Full method, timings, and both findings:
[`docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md`](../docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md).

## What this branch contains

- the 2026-08-10 verification receipt;
- `docs/PROJECT_STATUS.md` corrected — it still declared CI dead and `main` at
  `ece1bad`;
- this checkpoint.

No code. The repair derived here was already upstream by the time it was ready.

## Still true, and still nobody's job

Nothing server-side stops an unchecked merge to `main`. The default-branch
ruleset that would require passing checks (issue #399) is still disabled.
#453's pre-push hook is local only, so a merge made from anywhere else can still
land red — which is exactly how `d54fd896` happened.

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

CI no longer blocks anything, and the billing question is closed. From the
canonical Mac checkout, establish the live proof baseline:

```bash
cd ~/Projects/kitty
./kitty context --agent
./kitty status
./kitty doctor --json
./kitty builder initiative doctor --json
```

Do not infer missing runtime facts from this file.
