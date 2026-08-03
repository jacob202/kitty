# Session State — Open WebUI daily-driver acceptance

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-03T05:50:00Z",
  "branch": "feat/openwebui-tomorrow-ready",
  "worktree": "feat/openwebui-tomorrow-ready",
  "status": "awaiting_review",
  "completed_items": [
    "Rebuilt PR #384 on current main without unrelated Image Studio changes",
    "Pinned and isolated Open WebUI 0.10.2 as a loopback-only replaceable shell",
    "Configured Kitty model menu, provider policy, five workspace agents, and bounded Kitty tools",
    "Hardened environment isolation, process ownership, launchd enablement, backup, restore, and rollback",
    "Added feature-level verification for settings, agents, models, tools, memory, notes, projects, calendar, Tutor contract, and Builder projection",
    "Added bounded paid acceptance for every advertised model route and an end-to-end Daily Kitty turn",
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
    "PR #384 is rebased or force-pushed so commit 34a36fdfe6da45e62e68d84e6511e526b22f914a is no longer in its history",
    "Open WebUI, Gateway, provider, agent, or tool configuration changes after the recorded acceptance pass"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": {
    "number": 384,
    "state": "OPEN",
    "head_sha": "34a36fdfe6da45e62e68d84e6511e526b22f914a"
  },
  "head_sha": "34a36fdfe6da45e62e68d84e6511e526b22f914a"
}
-->

## Execution ownership

- this session: interactive Open WebUI onboarding and verification pass
- pull request: #384 (`feat/openwebui-tomorrow-ready`)
- product boundary: Open WebUI is the replaceable shell; Kitty Gateway remains authoritative

## Verified in repository

- loopback-only unauthenticated binding and minimal runtime environment;
- pinned isolated Open WebUI installation and owner-only service state;
- checked-in model roles and provider preferences;
- five configured workspace agents with bounded tool attachment;
- domain/modality-aware Auto routing and native direct OpenRouter IDs;
- schema-valid failure streams and fail-loud provider/memory behavior;
- PID ownership, launchd enablement, verified backup, atomic restore, and rollback identity checks;
- feature acceptance command and tests;
- lint, typecheck, hygiene, frontend tests/build, and browser smoke passed on the pre-continuity feature head.

## Not yet verified on Jacob's Mac

The repository cannot prove live credentials, Open WebUI's installed database state, launchd behavior, or real provider responses. The branch must stay in review until the live bootstrap and `verify --accept-charges` pass on the Mac and any failures are fixed rather than waived.