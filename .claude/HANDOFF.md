# Handoff — Open WebUI daily-driver baseline complete, slice 2 next

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-02T21:10:00Z",
  "head_sha": "29f2165d",
  "branch": "feat/openwebui-tomorrow-ready",
  "worktree": "main",
  "status": "valid",
  "completed_items": [
    "All four defects in docs/plans/openwebui-agent-handoff-2026-08-02.md are fixed and verified live",
    "All nine baseline criteria in that handoff's 'Immediate onboarding objective' pass",
    "PR #384 updated"
  ],
  "blockers": [
    "AGENT_ROUTER_TOKEN in .env is revoked; Jacob replaces it or leaves AgentRouter disabled"
  ],
  "next_action": "Slice 2 — the user-facing model set (Kitty Auto/Fast/Think/Code/Vision/Image)",
  "parallel_work": [],
  "recommendations": [
    "Ollama serves knowledge embeddings but does not start at login; homebrew.mxcl.ollama.plist exists and is unloaded",
    "10 pre-existing test failures on this branch's base are worth their own fix",
    "./kitty up boots out the launchd jobs ./kitty install creates — the two startup paths still contradict each other"
  ],
  "invalidation_conditions": [
    "HEAD changes beyond 29f2165d"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": 384
}
-->

## What was done

Slice 1 of the Open WebUI onboarding. Read
`docs/plans/openwebui-onboarding-progress.md` for the evidence; the short
version is that chat could not complete a single turn (revoked provider token
behind a hard pin), every turn carried a 447KB system prompt of Builder
initiative records, Kitty memory was dead on two separate missing dependencies,
Open WebUI's MCP SDK was shadowed by Kitty's own `mcp/` package through both
`PYTHONPATH` and the working directory, six pending admin accounts blocked the
door, and a provider failure reached the user as a blank message.

All of it is fixed, verified through the real UI, and survives a restart.

## Next move

Slice 2: the user-facing model set. It needs gateway-side aliases before Open
WebUI can present `Kitty Auto` / `Fast` / `Think` / `Code` / `Vision` / `Image`
as a menu — today the gateway exposes only `kitty-default`.
