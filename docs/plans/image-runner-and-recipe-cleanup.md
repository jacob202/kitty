# Plan: Image-job runner + recipe registry cleanup

**Status:** Ready to implement
**Branch:** `feat/image-studio-v1` (or a new `refactor/image-runner` off it)
**Candidates:** 1, 2 (image cluster deepening)

## Candidate 1 — Image-job runner

### What changes

**New file:** `gateway/image_runner.py`

```
async def run(
    engine: str,
    prompt: str,
    *,
    recipe: Recipe | None = None,
    character: Character | None = None,
    parent_id: str | None = None,
) -> JobResult
```

- Owns: `create_job` (recording `workflow_template_id` + hash from recipe), the `SUBMITTED → RUNNING → SUCCEEDED/FAILED` drive, artifact persistence, error normalization
- Engine dispatch inside: `comfyui` → `image_gen.generate` / `generate_with_character`; `drawthings` → `mcp.imagen` engine registry
- Character-ref resolution (primary ref lookup, "no references" 400) moves in from routes
- Invariant: if `run()` returns or raises, the job is in a terminal state
- `cancel` stays in `image_gen` (noted as future runner responsibility)

**Files modified:**
- `gateway/routes/extended.py` — `image_generate` and `studio_generate` shrink to thin handlers: request model → `run(...)` → status-code mapping
- `gateway/image_gen.py` — `generate()` and `generate_with_character()` become internal to the runner (not route-called directly)

### Bug fixes made impossible by construction

1. **`recipe_id` TypeError** — `create_job` never receives a nonexistent kwarg; recipe data mapped to real fields (`workflow_template_id`, `workflow_hash`)
2. **Stuck-RUNNING on studio drawthings path** — lifecycle drive is uniform; exception always marks `FAILED`
3. **Missing `workflow_template_id` on studio jobs** — recorded from recipe in `run()`

### Tests

- New `tests/test_image_runner.py`:
  - Fake engine adapter (in-memory, returns bytes)
  - Tmp SQLite (`KITTY_DB_FILE`)
  - Success path → `SUCCEEDED` with `output_path` set
  - Engine raise → `FAILED` with `normalized_error`
  - Character path with no refs → `ImageRunnerError`
  - Cancel-mid-flight → `ImageGenerationCancelled`
- Existing `tests/test_image_jobs.py` (store tests) untouched
- Existing `tests/test_image_cancel.py` may need minor import adjustment

### Step order

1. Create `gateway/image_runner.py` with `run()` and `JobResult` dataclass
2. Write `tests/test_image_runner.py` (fake engine + tmp DB)
3. Refactor `routes/extended.py` `image_generate` and `studio_generate` to call `run()`
4. Remove duplicated drawthings lifecycle scripts from both routes
5. Run `python3.12 -m pytest tests/test_image_runner.py tests/test_image_jobs.py tests/test_image_cancel.py -q --tb=short`
6. Run `cd gateway/kitty-chat && npm run build` (no UI changes expected but verify)

---

## Candidate 2 — Recipe registry cleanup

### What changes

**`gateway/image_gen.py`:**
- Delete `_wf_sd15` (dead code, zero callers)
- Delete dead if/else in `generate()` — always build SDXL workflow with SDXL-native params (1024×1024, 6 steps, cfg 1.5, euler, sgm_uniform)
- `_parse()` simplified: remove SD1.5 branch (512×512, 25 steps, cfg 7). Keep keyword parsing for explicit/bear LoRA detection only (still relevant to workflow params)
- SDXL-specific param overrides from keywords (portrait → 832×1216, landscape → 1216×832, detailed → 10/2.0) preserved

**`gateway/image_recipes.py`:**
- `DEFAULT_RECIPES`: mark `comfyui_sd15_standard`, `comfyui_pulid_sdxl`, `drawthings_standard` with `is_available=False` (they claim capabilities the infra doesn't have)
- `comfyui_sdxl_standard` remains the only active recipe
- `seed_default_recipes()` stays as-is (idempotent)

**`gateway/routes/extended.py`:**
- `StudioGenerateRequest`: strip `aspect_ratio`, `image_count`, `seed` (dead interface — never read)
- Wire `negative_prompt` through both the character path and the plain comfyui path
- Remove `seed_default_recipes()` calls from GET handlers; seed once in `app.py` lifespan

**`gateway/app.py`:**
- Add `image_recipes.seed_default_recipes()` to lifespan startup

**Files modified:** `gateway/image_gen.py`, `gateway/image_recipes.py`, `gateway/routes/extended.py`, `gateway/app.py`

### Tests

- Existing `tests/test_image_recipes.py` — update expected available count (1 active recipe)
- Existing `tests/test_image_gen.py` or equivalent — verify SDXL-native params used
- `tests/test_image_runner.py` (from candidate 1) — verify recipe workflow_template_id recorded

### Step order

1. Kill `_wf_sd15` and the dead if/else in `generate()` — always SDXL
2. Mark unavailable recipes in `DEFAULT_RECIPES`
3. Strip dead request fields from `StudioGenerateRequest`
4. Wire `negative_prompt` through both paths
5. Move `seed_default_recipes()` to `app.py` lifespan
6. Run tests
7. Run `cd gateway/kitty-chat && npm run build`

---

## Combined order (candidates 1 + 2)

1. Candidate 2 step 1-2 first (clean up image_gen before extracting runner)
2. Candidate 1 steps 1-6 (extract runner with clean substrate)
3. Candidate 2 steps 3-7 (wire remaining cleanup through runner)
4. Full test suite: `python3.12 -m pytest tests/ -q --tb=short`
5. UI build: `cd gateway/kitty-chat && npm run build`
6. `./kitty status` and `./kitty doctor --json` if services are running
