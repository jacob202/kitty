# Session State — Open WebUI baseline and model menu complete

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-02T21:10:00Z",
  "head_sha": "c37785cd",
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
    "Kitty memory restored (mem0 ollama client + openai provider)",
    "Slice 2: five-model menu (Auto/Fast/Think/Code/Vision) live and verified through Open WebUI",
    "Image uploads no longer 500 the chat endpoint; Kitty Vision reads images",
    "Guarded _prepare_main_worktree against hard-resetting the primary checkout"
  ],
  "blockers": [
    "AGENT_ROUTER_TOKEN in .env is revoked (unauthorized_client_error); AgentRouter disabled, OpenRouter in use",
    "A Builder campaign with --publish --gate auto hard-resets the primary checkout to origin/main on every merge; the guard is on this branch, not on main"
  ],
  "next_action": "Slice 3 — expose Kitty memory, projects, files, and planning to Open WebUI through its OpenAPI tool surface",
  "parallel_work": [],
  "recommendations": [],
  "invalidation_conditions": [
    "HEAD changes beyond c37785cd",
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
