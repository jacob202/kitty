# Session State — Architecture Deepening Landed; Ready for Live-ComfyUI Smoke

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-20T18:00:00Z",
  "head_sha": "9f2960683031f37ca2e08bd610ad8efd1186865d",
  "branch": "feat/image-studio-v1",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "PR #216 merged (docs/kitty-frontend-experience-harvest) at f2f79dc — origin/main and local main synced",
    "post-merge main advanced past 082a2e8 to f2f79dc via 2dc915d (safe image cancel + CI repair), 23ff786, 0708b62 (Kitty-wide UX program), dd17d8f (Character Card spec)",
    "feat/image-studio-v1 branched from main with 5 commits (3df1fe2..9f29606): Image Studio V1 shell, IP-Adapter identity workflow, reference quality checks, upload quality + cancel + result cards, workflow node fixes for installed IPAdapter_FaceID",
    "tests/test_db.py migration snapshot updated to include 024_image_characters, 025_image_references, 026_image_recipes — snapshot test green",
    "kitty-chat vitest: 33 files / 256 tests all pass on this branch",
    "call_llm fail-loud contract implemented: new ProviderChainExhausted(RuntimeError, code='llm.chain_exhausted') in gateway/llm_client.py replaces silent return \"\" on chain deadline and provider exhaustion; tests/test_llm_client_contract.py added; tests/test_llm_client.py updated to assert new raise contract",
    "redundant seed_default_recipes() calls removed from 3 route handlers in gateway/routes/extended.py (already seeded once in app.py lifespan)",
    "STATE and HANDOFF continuity docs rewritten to match live git + PR state; ./kitty context --agent now returns 27/27 PASS",
    "full pytest: 2676 passed / 1 skipped / 4 deselected (2 pre-existing timing flakes in test_builder_loop and test_builder_runner + the 2 old assert-empty-string tests replaced by the raise-contract tests)",
    "Architecture deepening review: 4 candidates identified and crystallized with implementation plans (see docs/plans/) — all 4 verified as delivered against live code"
  ],
  "blockers": [],
  "next_action": "Smoke-test Image Studio V1 end-to-end against a live ComfyUI (character add → recipe pick → generate → gallery). ComfyUI IPAdapter_FaceID node names in 9f29606 are unverified against a running engine; that is the last unbounded validation limitation on this branch. Do not push feat/image-studio-v1 or open a PR without Jacob's explicit approval.",
  "invalidation_conditions": [
    "HEAD changes beyond 9f2960683031f37ca2e08bd610ad8efd1186865d",
    "branch or registered worktree changes",
    "origin/main advances beyond f2f79dc39096f140826c05fb85ce480f5f7ee625"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

- `origin/main` = local `main` = `f2f79dc`. PR #216 merged. `main` and `origin/main` are in sync.
- We are on `feat/image-studio-v1` (HEAD `9f29606`), 5 commits ahead of `main`. These commits are runtime code — Image Studio V1 shell, character system, IP-Adapter identity workflow, quality checks, cancel support.
- Working tree has additional uncommitted changes from architecture-deepening implementations (see below). Nothing on this branch has been pushed. No PR opened.
- Active mission KFX-001 (frontend + product-experience harvest) authorised docs work only. The Image Studio V1 commits and the architecture-deepening changes on this branch are separate runtime streams; treat this branch as work-in-progress requiring Jacob's review, not a KFX-001 deliverable.
- ComfyUI offline state remains an explicit validation limitation for all image-engine work.

## Feature branch commits (main..feat/image-studio-v1)

| commit  | what |
|---------|------|
| 3df1fe2 | feat(image): Image Studio V1 — character system, recipe registry, auto routing |
| aa95352 | feat(image): IP-Adapter identity workflow for character generation |
| 5ed41ce | feat(image): reference quality checks with local image analysis |
| b370f36 | feat(image): quality checks on upload, cancel support, richer result cards |
| 9f29606 | fix(image): update workflow node names for installed ComfyUI IPAdapter_FaceID |

## Main advanced (082a2e8 → f2f79dc)

| commit  | what |
|---------|------|
| dd17d8f | Implement Character Card specification with reference repositories and API integration |
| 0708b62 | docs(ux): define Kitty-wide product experience program |
| 23ff786 | docs(state): record PR #216 in handoff and state |
| 2dc915d | fix(image): safe cancellation, truthful reconciliation, CI repair |
| f2f79dc | Merge PR #216 (docs/kitty-frontend-experience-harvest-2026-07-20) |

## Test posture (end of session)

- kitty-chat vitest: 33/33 files, 256/256 tests pass.
- pytest: 2676 passed / 1 skipped / 4 deselected. Two of the four deselected are pre-existing timing flakes in the builder suite (test_builder_loop::test_killed_run_packet_recovers_end_to_end and test_builder_runner::test_heartbeat_renews_lease_during_run — both pass in isolation, fail intermittently when the whole suite runs).
- `./kitty context --agent`: 27/27 PASS, 0 WARN, 0 FAIL.

## Architecture deepening — implemented

Four candidates identified, crystallized, and implemented:

| # | Candidate | Decision | Status |
|---|-----------|----------|--------|
| 1 | Image-job runner | New `gateway/image_runner.py`, engine dispatch inside, lifecycle invariant | **done** |
| 2 | Recipe registry vs keyword router | Kill dead code, SDXL-only, advisory registry, seed at lifespan, strip dead fields | **done** |
| 3 | memory_graph adapter contract | Adapters raise, source = adapter name (SIGNALS/FACTS), await directly | **done** |
| 4 | call_llm error contract | ProviderChainExhausted raised on chain exhaustion / deadline; tests added | **done** |

**Bugs fixed this session (candidate 4):**
- `call_llm`: silent `return ""` on provider chain exhaustion → `raise ProviderChainExhausted(errors=[...])` (per-provider diagnostics). Callers previously interpreting `""` as a real answer now surface the failure. `inventory.py`'s existing `try: except Exception:` catches the new exception with no further edit.
- `call_llm`: silent `return ""` on chain deadline exceeded → same raise, with `"chain: deadline Ns exceeded"` diagnostic.

**Bugs fixed by earlier work (candidates 1–3, verified live):**
- `studio_generate` drawthings path: `recipe_id` TypeError → impossible by construction (runner handles dispatch)
- `studio_generate` drawthings path: stuck-RUNNING → invariant enforced (runner always reaches terminal state)
- `generate()`: SD1.5 params on SDXL workflow → dead branch eliminated, always SDXL-native params
- `_wf_sd15`: dead production code → deleted
- `SignalsAdapter`: source=Source.TRACES → source=Source.SIGNALS
- `WeaveAdapter`: source=Source.MEMORY → source=Source.FACTS
- `KnowledgeAdapter`: asyncio.to_thread(asyncio.run(...)) → await directly
- `StudioGenerateRequest`: dead fields (aspect_ratio, image_count, seed) → stripped
- `seed_default_recipes()`: called on GET handlers → moved to app.py lifespan (this session removed the 3 remaining redundant call sites in `gateway/routes/extended.py`)

**New files (across the branch):**
- `gateway/image_runner.py` — deep module owning job lifecycle and engine dispatch
- `tests/test_image_runner.py` — 11 tests
- `tests/test_memory_graph_contract.py` — 11 tests
- `tests/test_llm_client_contract.py` — 4 tests (this session added; layout refined by linter/user pass)
- `docs/plans/image-runner-and-recipe-cleanup.md`
- `docs/plans/memory-graph-contract-enforcement.md`
- `docs/plans/call-llm-error-contract.md`

## Uncommitted working tree (as of end-of-session)

```
 M .claude/HANDOFF.md
 M .claude/STATE.md
 M gateway/app.py
 M gateway/image_gen.py
 M gateway/image_recipes.py
 M gateway/llm_client.py          # ProviderChainExhausted + raise contract
 M gateway/memory_graph.py
 M gateway/routes/extended.py     # 3 redundant seed_default_recipes() removed
 M tests/test_db.py               # migration snapshot 024/025/026
 M tests/test_llm_client.py       # 2 tests updated to raise contract
 M tests/test_memory_graph.py
?? docs/plans/*.md                # 3 crystallized plans
?? gateway/image_runner.py
?? tests/test_image_runner.py
?? tests/test_llm_client_contract.py
?? tests/test_memory_graph_contract.py
```

## Known follow-ups

- Smoke-test Image Studio V1 end-to-end against a live ComfyUI. The ComfyUI IPAdapter_FaceID node-name fix in 9f29606 is unverified against a running engine.
- Decide whether feat/image-studio-v1 becomes a PR now, waits for KFX-01 rollup, or stays a local review branch until Jacob picks.
- Two builder timing flakes (test_killed_run_packet_recovers_end_to_end, test_heartbeat_renews_lease_during_run) — pass in isolation, fail under load. Worth a separate look at lease-clock behavior.
- Campaign/reconcile/reasoning-backend worktrees kept for review; none active this session.
