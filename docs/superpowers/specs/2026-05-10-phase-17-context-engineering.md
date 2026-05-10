# Phase 17 — Context Engineering + Code Review Fixes Design Spec

## Goal

Bake context engineering as a first-class design law into the Kitty gateway: every LLM call — whether Jacob-facing or an internal worker — gets exactly the context it needs, nothing more. Simultaneously resolve all 10 code review blockers (5 critical, 5 important) from the Phase 1-16 review.

**Design law:** minimum viable context, maximum signal density, lowest token cost.

---

## Architecture

Two new files. Everything else is updated to use them.

### `gateway/paths.py` (new)

Single source of truth for all filesystem paths. Replaces 14 hardcoded `/Users/jacobbrizinski/...` strings across the codebase.

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
PROMPTS_DIR  = PROJECT_ROOT / "prompts"
LOGS_DIR     = PROJECT_ROOT / "logs"
```

All modules import from here. `model_digest.py` already uses `Path(__file__)` — that pattern now applies everywhere.

### `gateway/context_builder.py` (new)

The core of the context engineering layer. Two public functions, one responsibility each.

---

## context_builder: User-Facing Calls

`build_user_context(query: str, domain: str) -> str` (async)

Called by `/v1/chat/completions` and `/ask`. Returns a fully assembled system prompt string.

**Pipeline:**
1. Fetch memory + knowledge **in parallel** via `asyncio.gather`
2. Filter each result set: keep chunks with similarity score ≥ 0.7
3. Apply token budget per section (see below)
4. Assemble structured prompt
5. Return — empty sections silently omitted (no noise injected)

**Token budget (total ~1600 tokens):**

| Section | Budget | Source | Order |
|---|---|---|---|
| Soul | ~400 tokens (fixed) | `prompts/soul.md` | Always first, Anthropic cache-pinned |
| About Jacob | 500 tokens max | Mem0 search results | Newest-first, truncate to budget |
| Relevant context | 700 tokens max | ChromaDB search results | Score-descending, truncate to budget |

**Token counting:** `len(text.split()) * 1.3` — no external dependency.

**Anthropic prompt cache pin:** The soul section is marked with `cache_control: {"type": "ephemeral"}` when the downstream model is a Claude model. Saves ~400 input tokens per turn at zero implementation cost.

**Assembled format:**
```
{soul_prompt}

---
## About Jacob
- [memory chunk 1]
- [memory chunk 2]

---
## Relevant context
[knowledge chunk 1]
[knowledge chunk 2]
```

Sections with no qualifying chunks are omitted entirely — no headers, no dashes.

---

## context_builder: Worker Calls

`build_worker_context(task_type: str, **kwargs) -> str` (sync)

Called by internal workers: `brief.py`, `researcher.py`, `onboarding.py`, `learning.py`, `reset.py`, `troubleshooter.py`.

**Rules (enforced, not optional):**
- No soul prompt — workers don't need Kitty's personality
- No full memory dump — at most a 100-token snippet of one relevant recent fact
- No unrelated knowledge chunks
- Hard cap: 300 tokens total

**Templates per worker type:**

| Task type | Context it receives |
|---|---|
| `brief` | Top task (from TASKS.md) + 1 recent memory + Jacob's timezone |
| `researcher` | Topic string + 3 highest-scored KB chunks for that topic |
| `onboarding` | User's raw response text only |
| `learning` / `reset` / `troubleshooter` | 2-sentence task description only |

Each template is a string constant in `context_builder.py`. Workers call `build_worker_context("brief", task=..., memory=..., tz=...)` — no inline prompt assembly anywhere else.

---

## Code Review Fixes

All 10 fixes land in the same phase, as separate commits from ContextBuilder.

### C1 — Key safety
- Commit `.env.example` with placeholder values so the repo is safe to publish
- Add `_validate_env()` called at gateway startup — logs `WARNING` for any key that is missing or still set to a default value (e.g. `"kitty-local-key-change-me"`)
- Key rotation is operational (Jacob does it); the code change is the validator and the example file

### C2 — Auth fail-open
- When `GATEWAY_SECRET` is unset: return `503 Service Unavailable` with `{"error": "Gateway not configured"}` on all non-`/health` routes
- Test environment bypass: check `os.environ.get("KITTY_ENV") == "test"` to allow tests to run without a secret
- Startup log: `WARNING: GATEWAY_SECRET not set — all routes blocked` when secret is missing

### C4 — Duplicate function definitions
- Delete the second and third copies of `list_memories` / `delete_memory` in `gateway/memory.py`
- Delete the duplicate `/memories` and `/sessions/close` route registrations in `gateway/app.py`
- Add `# ruff: noqa: F811` audit note to `ruff.toml` or equivalent so duplicates are caught in CI

### C5 — CORS wildcard + credentials
```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:8000",
    os.environ.get("KITTY_WEBUI_ORIGIN", "http://localhost:3000"),
],
allow_credentials=True,
```
`KITTY_WEBUI_ORIGIN` in `.env` lets Jacob add his Tailscale hostname without code changes.

### I1/I2 — Input validation + rate limiting
- Every endpoint that accepts user text gets a Pydantic request body with `max_length` (1 000 chars for topics/queries, 32 000 for chat messages)
- `/research/deep`, `/troubleshoot`, `/learn` get `slowapi` rate limiting: 10 requests/minute per IP
- `MAX_BODY_BYTES` middleware moved to apply to ALL routes, not just `/v1/chat/completions`

### I4 — Absolute paths
- All 14 files updated to import `DATA_DIR`, `PROMPTS_DIR`, `LOGS_DIR` from `gateway/paths.py`
- No more `/Users/jacobbrizinski/...` strings anywhere in `gateway/`

### I7 — Domain router health priority
- Medical keywords (`blood`, `symptom`, `medication`, `diagnosis`, `pain`, `doctor`, `nurse`, `hospital`, `prescription`) get a 3× score multiplier
- Health domain wins any tie
- Add `tests/test_domain_router.py` with at least 6 cases including the "blood test → health, not code" regression

### I8 — Offline check cache
- `_is_offline()` result cached for 30 seconds using a module-level `(result, timestamp)` tuple
- No external dependency — two lines of stdlib

### I9 — model_digest duplicate events
- Free-to-paid transitions collected into `model_changes` dict (one entry per model), same as the existing price-change path
- One event emitted per model, not one per price field

### I5 — /ask serial fetch (fixed by ContextBuilder)
- `/ask` calls `build_user_context(message, domain)` — parallel fetch is built into that function
- No separate fix needed; the ContextBuilder adoption resolves this

---

## File Map

| File | Action |
|---|---|
| `gateway/paths.py` | **Create** |
| `gateway/context_builder.py` | **Create** |
| `gateway/app.py` | Modify: CORS, auth wiring, `/ask` → ContextBuilder, body size middleware |
| `gateway/auth.py` | Modify: 503 on missing secret, KITTY_ENV=test bypass |
| `gateway/memory.py` | Modify: delete duplicate function definitions |
| `gateway/domain_router.py` | Modify: health priority multiplier |
| `gateway/llm_client.py` | Modify: `_is_offline` 30s cache |
| `gateway/model_digest.py` | Modify: dedupe free-to-paid events |
| `gateway/brief.py` | Modify: use `build_worker_context("brief", ...)` |
| `gateway/researcher.py` | Modify: use `build_worker_context("researcher", ...)` |
| `gateway/onboarding.py` | Modify: use `build_worker_context("onboarding", ...)` |
| `gateway/learning.py` | Modify: use `build_worker_context("learning", ...)` |
| `gateway/reset.py` | Modify: use `build_worker_context("reset", ...)` |
| `gateway/troubleshooter.py` | Modify: use `build_worker_context("troubleshooter", ...)` |
| `gateway/inventory.py` | Modify: bump vision model string to claude-3.7-sonnet |
| All 14 path-containing files | Modify: import from `gateway/paths.py` |
| `.env.example` | **Create** |
| `tests/test_context_builder.py` | **Create** |
| `tests/test_domain_router.py` | **Create** |
| `scripts/setup/gate-check.sh` | Modify: Phase 17 gate |

---

## Testing

**`tests/test_context_builder.py`** (new):
- `test_build_user_context_parallel_fetch` — memory + knowledge called via gather
- `test_relevance_threshold_filters_low_scores` — chunks below 0.7 not included
- `test_token_budget_truncates_memory` — memory section capped at 500 tokens
- `test_token_budget_truncates_knowledge` — knowledge section capped at 700 tokens
- `test_empty_sections_omitted` — no chunks → no section headers in output
- `test_build_worker_context_no_soul` — soul text never appears in worker output
- `test_build_worker_context_under_300_tokens` — worker context stays within budget
- `test_cache_pin_present_for_claude_model` — soul section has cache_control when model is claude-*

**`tests/test_domain_router.py`** (new):
- `test_blood_test_routes_health_not_code`
- `test_medication_routes_health`
- `test_car_noise_routes_repair`
- `test_python_code_routes_code`
- `test_health_wins_tie`
- `test_general_routes_default`

All existing 65 tests must continue to pass.

---

## Execution order

1. `gateway/paths.py` + update all path imports (foundation — nothing else depends on this but it touches many files)
2. Structural fixes: C4 (duplicates), C5 (CORS), C2 (auth), I9 (model_digest)
3. Logic fixes: I7 (domain router + tests), I8 (offline cache), I4 (confirm paths done)
4. `gateway/context_builder.py` + tests (the new module)
5. Wire ContextBuilder into `app.py` `/ask` + `/v1/chat/completions`
6. Wire `build_worker_context` into all 6 worker modules
7. Input validation + rate limiting: I1/I2
8. C1 cleanup: `.env.example` + startup validator
9. Phase 17 gate check
