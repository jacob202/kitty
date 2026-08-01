# Session State — main was red; dependency resolution restored

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-01T05:00:00Z",
  "head_sha": "b68268b0333aedcf04085829deebe88371f832ef",
  "branch": "claude/kitty-stabilization-fbydi0",
  "worktree": "piddock",
  "status": "in_progress",
  "completed_items": [
    "Reconciliation: Gate 0.1 'main is green' is FALSE. tests.yml failed on 8 consecutive main commits (runs 1124-1139), current HEAD b68268b included.",
    "Root cause: Dependabot commit 600c0fa raised openai to >=2.49.0,<2.50.0. mem0ai 0.1.x requires openai<1.110.0, so 'pip install -r requirements.txt' is unresolvable. CI never reached pytest.",
    "Fix: openai pin restored to >=1.90.0,<1.110.0 with a comment recording the mem0ai coupling. Clean venv install resolves (mem0ai 0.1.118 + openai 1.109.1).",
    "Test evidence (single full run, 2026-08-01): 3452 passed, 7 failed, coverage 77.50% against the 73% floor.",
    "4 of 7 failures are container-environmental (no gh binary, no launchd, canonical-checkout path). 3 were real committed-state defects, repaired here: short head_sha, merged PR #331 declared active, HANDOFF missing pull_request key.",
    "Verified issue #336 diagnosis against code: plan is not persisted, /studio/generate takes raw form state not a plan id, worker hardcodes text_to_image_v1 (workers/comfy_worker/app.py:704), no image_agent.py, no image-session table."
  ],
  "blockers": [],
  "next_action": "Land the green-main repair, then execute docs/mission/execution.md slice A1 on a machine with Kitty runtime and RunPod credentials.",
  "parallel_work": [],
  "recommendations": [
    {
      "id": "dependabot-guardrail-sibling-pins",
      "what": "Gate Dependabot on resolvability: run 'pip install -r requirements.txt' in the guardrails workflow before a bump can merge",
      "why": "600c0fa merged a bump that made the tree unresolvable and reddened main for 8 commits. The Gate 0.2 Dependabot exemption let it past the tests gate.",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "mem0ai-major-bump",
      "what": "Evaluate mem0ai 0.1.118 -> 2.0.x, which drops the openai upper bound entirely",
      "why": "Unblocks future openai bumps permanently, but it is a major-version API break against gateway/memory.py and needs a live memory backend to verify. Separate slice.",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": [
    "origin/main advances past b68268b0333aedcf04085829deebe88371f832ef",
    "tests.yml turns green on main (the dependency repair landed)"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->
