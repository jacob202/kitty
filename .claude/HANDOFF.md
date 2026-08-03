# Handoff — Open WebUI daily-driver acceptance

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-03T05:58:00Z",
  "branch": "feat/openwebui-tomorrow-ready",
  "worktree": "feat/openwebui-tomorrow-ready",
  "status": "valid",
  "completed_items": [
    "Rebuilt PR #384 on current main without unrelated Image Studio changes",
    "Pinned and isolated Open WebUI 0.10.2 as a loopback-only replaceable shell",
    "Configured Kitty model menu, provider policy, five workspace agents, and bounded Kitty tools",
    "Hardened environment isolation, process ownership, launchd enablement, backup, restore, and rollback",
    "Added feature-level verification for settings, agents, models, tools, memory, notes, projects, calendar, Tutor contract, and Builder projection",
    "Added bounded paid acceptance for every advertised model route and an end-to-end Daily Kitty turn",
    "Fixed ASGI request replay for streaming chat responses and kept OpenRouter normalization at the direct-provider boundary",
    "Documented bootstrap, daily verification, backup, restore, and rollback"
  ],
  "blockers": [
    "Mac-local bootstrap and paid feature acceptance have not yet been run against Jacob's live credentials and launchd environment",
    "An independent final review of the final PR head is still required"
  ],
  "next_action": "Run python3 scripts/openwebui_local.py bootstrap --accept-charges on Jacob's Mac, fix every reported failure, then record independent review evidence before marking PR #384 ready",
  "parallel_work": [],
  "recommendations": [],
  "invalidation_conditions": [
    "PR #384 is rebased or force-pushed so commit 3d4c2404182173f2184f09aa7b6a4951d6e7f63a is no longer in its history",
    "Open WebUI, Gateway, provider, agent, or tool configuration changes after the recorded acceptance pass"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": {
    "number": 384,
    "state": "OPEN",
    "head_sha": "3d4c2404182173f2184f09aa7b6a4951d6e7f63a"
  },
  "head_sha": "3d4c2404182173f2184f09aa7b6a4951d6e7f63a"
}
-->

## What is configured

- Open WebUI is pinned to `0.10.2`, isolated under `~/kitty-services/openwebui`, unauthenticated only on loopback, and receives a minimal non-secret environment.
- Kitty Gateway is the only OpenAI-compatible backend exposed to the shell.
- The visible model menu is Kitty Auto, Fast, Think, Code, and Vision.
- Daily Kitty, Research, Coding, Tutor, and Builder Operator are created or repaired on startup with the intended base route, tool attachment, and vision capability.
- The bounded tool server exposes memory, notes, projects, calendar, Tutor, and read-only Builder projections.
- Autostart, admin repair, PID ownership, backups, restore, rollback, and failure reporting are checked rather than assumed.

## What the acceptance gate proves

```bash
python3 scripts/openwebui_local.py verify
python3 scripts/openwebui_local.py verify --accept-charges
```

The first command checks the configured settings, model discovery, all five agents, the bounded OpenAPI tool contract, and live read-only Kitty projections. The second additionally sends bounded turns through all advertised model routes and through Daily Kitty in Open WebUI.

## Required next move

Run the full bootstrap on Jacob's Mac:

```bash
python3 scripts/openwebui_local.py bootstrap --accept-charges
```

Do not mark PR #384 ready merely because CI passes. Fix every live verifier failure, rerun until clean, then obtain or record an independent review of the final head. No new feature work belongs in this branch before those acceptance gates pass.