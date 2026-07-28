# Handoff — Builder reliability fixes, UI alignment, ImagePlan boundary, provider health

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-07-28T13:50:00Z",
  "head_sha": "be8dd1223c91810497391d1c3ef35bd563478d5a",
  "base_sha": "0a2a04480ecd555168656de62dfa9a3cc971031f",
  "branch": "jacob202/fix-description",
  "worktree": "amphipod",
  "status": "valid",
  "completed_items": [
    "Builder reliability: LOOP_CANCELLED preserved, stale attempt liveness fence",
    "Builder read-only surface: mutation controls removed",
    "Studio contract: seed/image_count/reference_ids removed",
    "ImagePlan boundary: plan dataclass, guidance bank, /studio/plan endpoint",
    "Provider health: kind/free_tier annotations and safety-net warnings",
    "Model routing refactor: RouteDecision moved to model_routing Module"
  ],
  "blockers": [],
  "next_action": "Fix failing PR #289 checks (typecheck, lint, cold-start, BuilderSurface test), then merge",
  "parallel_work": [
    {
      "kind": "pr",
      "ref": "#288",
      "owner": "jacob202",
      "touches": [".env.example", "gateway", "kitty", "tests"],
      "observed_at": "2026-07-28T13:50:00Z"
    }
  ],
  "recommendations": [
    {
      "id": "merge-pr-289",
      "what": "Fix the five failing checks on PR #289 and merge the 129-commit sweep",
      "why": "The branch carries substantial landed work that is blocked behind failing CI",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "harden-context-receipt",
      "what": "Deepen the context receipt validation Module as the next hardening target",
      "why": "Protects session continuity and stale-handoff detection",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "review-merged-prs",
      "what": "Extended review of recently merged PRs 281-288 for regression risk",
      "why": "Eight PRs merged in rapid succession; cumulative review is owed",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": ["HEAD advances past be8dd12", "PR #289 merges to main"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": {
    "number": 289,
    "state": "OPEN",
    "head_sha": "13aa8cd32d0c6f5e88205f1b69d241054cd28b9f"
  }
}
-->

## What was done
- **Builder reliability:** Cancellation outcomes preserved as distinct durable state (`08de685`), stale attempt liveness fence prevents incorrect recovery (`160806f`), 293 focused tests pass
- **UI alignment:** Mutation controls removed from read-only Builder surface, `⌘K` command palette button wired to open state (`fc6cd5a`)
- **Studio contract repairs:** Removed unsupported `seed`/`image_count` from frontend, removed dead `reference_ids` from backend request model (`3fcac83`)
- **ImagePlan boundary (GenEvolve adapted):** `gateway/image_plan.py` — `ImagePlan` dataclass with reference resolution + `build_image_plan()`, `gateway/image_guidance.py` — `GuidanceBank` (SkillBank pattern), 2 seed guidance files, `POST /studio/plan` endpoint, `PlanPreviewCard` frontend with approve/generate flow (`6695227`, `c18108b`)
- **Studio error surfacing:** ImageGenPanel shows transport errors as actionable messages instead of silently falling through (`5d137a9`)
- **Provider health:** `kind` (local/api_credit/subscription) and `free_tier` annotations on all 6 providers, free backup warnings when no provider is configured (`56ec965`)

## In-flight / WIP
- One dirty file: `docs/plans/kitty-master-architecture-audit.md` — unrelated architecture notes, uncommitted

## Other work in flight (not mine)
- **PR #288 (draft):** `fix/runtime-truth-agentrouter-2026-07-28` by jacob202 — runtime lifecycle, provider, tool state truthfulness. Touches `.env.example`, `gateway/`, `kitty`, `tests/`.
- **Worktree `fix/dogfood-provider-chat-shell-2026-07-28`:** uncommitted provider work (`.env.before-agentrouter`, `config/providers.json`, new `gateway/routes/providers.py`)
- 38 unmerged branches (many dependabot)
- Builder queue: UNAVAILABLE (DB file not accessible from this worktree)

## Blockers
- `docs/plans/kitty-master-architecture-audit.md` is dirty — review whether to commit or discard

## Next move
Launch this worktree on a non-conflicting port, capture browser evidence for the unified UI (Builder read-only surface, ImagePlan preview, provider health badges)

## Deferred, and what releases them
- None blocked

## Files changed this session
- `gateway/builder_run.py`, `gateway/builder_status.py`
- `gateway/builder_loop.py`, `gateway/builder_attempt.py`, `gateway/builder_initiative.py`
- `gateway/image_plan.py` (new), `gateway/image_guidance.py` (new), `gateway/image_guidance/spatial_layout.md` (new), `gateway/image_guidance/text_rendering.md` (new)
- `gateway/llm_client.py`, `gateway/model_routing.py`, `gateway/routes/extended.py`
- `gateway/kitty-chat/src/components/BuilderSurface.tsx`, `ProviderCenter.tsx`, `ImageStudio.tsx`, `ImageGenPanel.tsx`, `CommandPalette.tsx`
- `gateway/kitty-chat/src/app/page.tsx`, `gateway/kitty-chat/src/lib/gateway.ts`
- `tests/test_builder_loop.py`, `tests/test_builder_run.py`, `tests/test_builder_status.py`
- `docs/session-notes/2026-07-28-kittybuilder-execution-plan.md`

## Verification
- `python3.12 -m pytest tests/test_builder_run.py tests/test_builder_status.py -q`: 48 passed
- `python3.12 -m pytest tests/test_builder_attempt.py tests/test_builder_loop.py tests/test_builder_initiative.py -q`: 245 passed
- `python3.12 -c "from gateway.image_plan import ImagePlan, build_image_plan; from gateway.image_guidance import GuidanceBank"`: imports pass, 2 guidance tags loaded
