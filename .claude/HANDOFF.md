# Handoff — Builder reliability fixes, UI alignment, ImagePlan boundary, provider health

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
