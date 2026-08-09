# Handoff — superseded; do not resume

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-09T02:20:00Z",
  "branch": "fix/kproof-authority-reconciliation-2026-08-08",
  "worktree": "github-connected-reconciliation",
  "status": "invalid",
  "completed_items": [
    "Confirmed KPROOF-001 replaced the earlier trustworthy-daily-driver mission after the 2026-08-04 roadmap reconciliation",
    "Reconciled docs/ROADMAP.md with KPROOF-001",
    "Reconciled docs/PROJECT_STATUS.md with current repository and GitHub evidence",
    "Confirmed PR #437 Actions jobs never reached a runner because GitHub blocked execution for account billing/spending reasons"
  ],
  "blockers": [
    "This GitHub-connected session cannot inspect Jacob's live Mac runtime or local Builder database",
    "GitHub Actions runners are currently blocked by the account billing/spending state"
  ],
  "next_action": "Do not resume the merged Open WebUI #384 session; establish a fresh KPROOF-001 checkpoint from the canonical Mac checkout.",
  "parallel_work": [
    {
      "kind": "pull_request",
      "ref": "#437",
      "owner": "jacob202",
      "touches": [
        "gateway/kitty-chat/src/components/BuilderSurface.tsx",
        "gateway/kitty-chat/src/lib/queries.ts"
      ],
      "observed_at": "2026-08-09T02:20:00Z"
    }
  ],
  "recommendations": [],
  "invalidation_conditions": [
    "This handoff is intentionally invalid because it replaces the superseded Open WebUI #384 continuation and was not created from a verified live Mac runtime session."
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "head_sha": "f1e820fea6dc6bac41e05c7ba2ef1b15fbae8646"
}
-->

## Why this handoff is invalid

The previous handoff told the next session to continue Open WebUI PR #384 even though that work had already merged and the approved mission had later changed to KPROOF-001. Reusing it would send a cold-starting agent into superseded work.

This file now fails closed on purpose. It is **not** an execution checkpoint.

## Current authority

Read, in order:

1. `docs/ROADMAP.md` — KPROOF-001 is the current gate.
2. `docs/ACTIVE_MISSION.md` — the approved two-week Builder proof and acceptance contract.
3. `docs/PROJECT_STATUS.md` — current repository/GitHub evidence and explicit unknowns.
4. `.claude/STATE.md` — the current interactive checkpoint when its metadata validates.

## Runtime boundary

GitHub evidence cannot establish the live Mac service state, local Builder queue, credentials, providers, or running UI. A future local session must generate those facts through supported probes; it must not fill them from this handoff.
