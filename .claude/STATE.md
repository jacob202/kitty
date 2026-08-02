# Session State — Open WebUI daily-driver baseline complete

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-02T21:10:00Z",
  "head_sha": "29f2165d",
  "branch": "feat/openwebui-tomorrow-ready",
  "worktree": "main",
  "status": "complete",
  "completed_items": [
    "Slice 1 of the Open WebUI onboarding: launch, login, streaming, persistence, diagnostics, backup, restore, rollback",
    "Handoff defect 2 (PYTHONPATH/cwd shadowing of the MCP SDK) fixed and regression-tested",
    "Handoff defect 3 (SSE contract and smoke verifier) fixed; failures now render in Open WebUI",
    "Handoff defect 4 (pending-account and duplicate-user trap) fixed idempotently",
    "Chat routing restored: AgentRouter token is revoked, Kitty runs on OpenRouter",
    "System prompt cut from 447,759 to ~24,200 chars; TTFT 26s to 6.4s",
    "Kitty memory restored (mem0 ollama client + openai provider)"
  ],
  "blockers": [
    "AGENT_ROUTER_TOKEN in .env is revoked (unauthorized_client_error); AgentRouter disabled, OpenRouter in use"
  ],
  "next_action": "Slice 2 — the user-facing model set (Kitty Auto/Fast/Think/Code/Vision/Image), which needs gateway-side aliases first",
  "parallel_work": [],
  "recommendations": [],
  "invalidation_conditions": [
    "HEAD changes beyond 29f2165d",
    "config/providers.json active changes away from auto"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": 384
}
-->

## Execution ownership

- this session: interactive
- no Builder bundle, task, or lease

## Evidence

`docs/plans/openwebui-onboarding-progress.md` and
`docs/plans/openwebui-onboarding-checklist.json`.

## Tests

Full suite: 3739 passed, 10 failed, 1 skipped. All 10 failures reproduce
identically at the branch point `e1c175c5` with the same `.env` present —
4 in `test_check_continuity_state.py`, 1 in `test_cold_start_acceptance.py`,
and 5 provider tests that leak environment state between tests. None are
caused by this branch.

## KB effectiveness

- no receipt recorded yet
