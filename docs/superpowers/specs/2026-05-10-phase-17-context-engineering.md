# Phase 17 — Context Engineering + Code Review Fixes Design Spec

**Design law:** minimum viable context, maximum signal density, lowest token cost.

---

## Goal

Bake context engineering as a first-class design law into the Kitty gateway: every LLM call — whether Jacob-facing or an internal worker — gets exactly the context it needs, nothing more. Simultaneously resolve all 10 code review blockers (5 critical, 5 important) from the Phase 1-16 review.

---

## New Files

### `gateway/paths.py`

Single source of truth for all filesystem paths. Replaces 14 hardcoded `/Users/jacobbrizinski/...` strings across the codebase.

```python
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
PROMPTS_DIR  = PROJECT_ROOT / "prompts"
LOGS_DIR     = PROJECT_ROOT / "logs"

def validate_dirs() -> None:
    """Assert essential directories exist. Call once at startup."""
    for d in (DATA_DIR, PROMPTS_DIR, LOGS_DIR):
        if not d.exists():
            raise RuntimeError(f"Required directory missing: {d}")
```

`validate_dirs()` is called in `gateway/app.py` at startup so a missing directory surfaces immediately with a clear error, not as a `FileNotFoundError` deep in a worker.

---

### `gateway/context_builder.py`

The core context engineering module. Two public functions, one responsibility each.

#### Module-level constants (easy to tune)

```python
MEMORY_BUDGET_TOKENS    = 500
KNOWLEDGE_BUDGET_TOKENS = 700
RELEVANCE_THRESHOLD     = 0.7
WORKER_BUDGET_TOKENS    = 300
```

#### `build_user_context(query, domain) -> tuple[str, str]` (async)

Returns `(cached_prefix, dynamic_suffix)`:
- `cached_prefix` — the soul prompt, marked for Anthropic prompt cache. Fixed per deployment, safe to pin.
- `dynamic_suffix` — `## About Jacob` + `## Relevant context` sections, assembled fresh per request.

Callers pass both to the LLM: `[{role: system, content: cached_prefix, cache_control: {type: ephemeral}}, {role: system, content: dynamic_suffix}]` when the model is a Claude model. Non-Claude callers concatenate them. Returning a tuple makes the cache-pin boundary explicit and unambiguous — callers never have to guess where the split is.

**Pipeline:**

1. Fetch memory + knowledge with explicit exception isolation:
```python
mem_results, know_results = [], []
results = await asyncio.gather(
    _fetch_memory(query),
    _fetch_knowledge(query),
    return_exceptions=True
)
if isinstance(results[0], Exception):
    logger.warning("memory fetch failed: %s", results[0])
else:
    mem_results = results[0]
if isinstance(results[1], Exception):
    logger.warning("knowledge fetch failed: %s", results[1])
else:
    know_results = results[1]
```
One failure never blocks the other. If both fail, `dynamic_suffix` is empty — soul-only context is returned.

2. Filter: keep chunks with `score >= RELEVANCE_THRESHOLD`. Log discard count at DEBUG level for tuning.
3. Sort: memory newest-first, knowledge score-descending.
4. Truncate to token budget (filter first, truncate second — high-score old items are never dropped before low-score new ones).
5. Assemble `dynamic_suffix`. Omit section entirely if no chunks pass (no headers, no separators).

**Assembled format** (only sections with content appear):
```
### About Jacob
- Jacob lives in Regina, Saskatchewan
- Jacob is building Kitty as a personal AI companion

### Relevant context
[knowledge chunk 1]
[knowledge chunk 2]
```

Uses `###` headings, not `---` separators — clearer hierarchy, fewer wasted tokens.

**Token counting:** `len(text.split()) * 1.3`. May slightly under-count code-heavy content, but safe for prompt budget enforcement at these sizes.

#### `build_worker_context(task_type, **kwargs) -> str` (sync)

Hard cap: `WORKER_BUDGET_TOKENS`. No soul prompt. At most a 100-token memory snippet, passed in by the caller — the worker fetches it, then passes it as `memory=snippet`. If `memory=None`, the snippet section is silently omitted.

**Templates:**

| Task type | Gets |
|---|---|
| `brief` | Top task + `memory` snippet + Jacob's timezone |
| `researcher` | Topic string + 3 highest-scored KB chunks (passed as `chunks=[...]`) |
| `onboarding` | User's raw response text only |
| `learning` / `reset` / `troubleshooter` | 2-sentence task description only |

Each template is a module-level string constant. Workers call `build_worker_context("brief", task=..., memory=..., tz=...)` — no inline prompt assembly anywhere else.

---

## Code Review Fixes

### C1 — Key safety
- Commit `.env.example` with placeholder values (safe to publish)
- Add `_validate_env()` at gateway startup — `WARNING` log for any key missing or still at default value (e.g. `"kitty-local-key-change-me"`)
- Key rotation is operational; code change is the validator + example file only

### C2 — Auth fail-open
- `GATEWAY_SECRET` unset → `503` with `{"error": "Gateway not configured"}` on all non-`/health` routes
- `KITTY_ENV=test` bypass: when `KITTY_ENV == "test"` AND `GATEWAY_SECRET` is unset → allow through with a `WARNING` log. When `GATEWAY_SECRET` IS set, `KITTY_ENV` has no effect — the secret is always checked.
- Startup log: `WARNING: GATEWAY_SECRET not set — all routes blocked` when secret is missing in non-test env

### C4 — Duplicate function definitions
- Delete second and third copies of `list_memories` / `delete_memory` in `gateway/memory.py`
- Delete duplicate `/memories` and `/sessions/close` route registrations in `gateway/app.py`
- Verify remaining function signatures match all call sites before committing

### C5 — CORS wildcard + credentials
```python
_webui_origin = os.environ.get("KITTY_WEBUI_ORIGIN")
allow_origins = [o for o in [
    "http://localhost:3000",
    "http://localhost:8000",
    _webui_origin,
] if o]  # filter None — invalid origin crashes Starlette
```
`KITTY_WEBUI_ORIGIN` in `.env` for Tailscale hostname. `None` filtered before list construction.

### I1/I2 — Input validation + rate limiting
- Pydantic request bodies on all user-text endpoints: `max_length=1000` for topics/queries, `max_length=32000` for chat messages
- `slowapi` rate limit on paid-API routes (`/research/deep`, `/troubleshoot`, `/learn`): 10 req/min per IP
- `MAX_BODY_BYTES` body-size check moved to middleware level — applies to all routes

### I4 — Absolute paths
- All 14 files updated to import `DATA_DIR`, `PROMPTS_DIR`, `LOGS_DIR` from `gateway/paths.py`
- No `/Users/jacobbrizinski/...` strings anywhere in `gateway/`

### I7 — Domain router health priority
- Medical keywords (`blood`, `symptom`, `medication`, `diagnosis`, `pain`, `doctor`, `nurse`, `hospital`, `prescription`) get a `3×` score multiplier
- Health domain wins any tie
- New test file covers: "blood test → health not code", "pain in Python script → health not code" (3× ensures health wins even with competing code keywords), "medication → health", tie-breaking

### I8 — Offline check cache
```python
_offline_cache: tuple[bool, float] | None = None
_offline_lock = threading.Lock()

def _is_offline() -> bool:
    global _offline_cache
    with _offline_lock:
        now = time.monotonic()
        if _offline_cache and now - _offline_cache[1] < 30:
            return _offline_cache[0]
        result = _check_connectivity()
        _offline_cache = (result, now)
        return result
```
`threading.Lock` prevents a race where two coroutines both see a stale cache and both open sockets simultaneously. For a 30s TTL this is a minor race in practice, but the lock is a one-liner.

### I9 — model_digest duplicate events
- Free-to-paid transitions collected into `model_changes` dict (one entry per model) before emitting, same as existing price-change path
- One event per model regardless of how many price fields change

### I5 — /ask serial fetch
- Resolved by ContextBuilder adoption: `/ask` calls `build_user_context(message, domain)` — parallel fetch is built in

---

## File Map

| File | Action |
|---|---|
| `gateway/paths.py` | **Create** |
| `gateway/context_builder.py` | **Create** |
| `tests/test_context_builder.py` | **Create** |
| `tests/test_domain_router.py` | **Create** |
| `.env.example` | **Create** |
| `gateway/app.py` | CORS fix, auth wiring, `/ask` + chat_completions → ContextBuilder, body-size middleware, validate_dirs call |
| `gateway/auth.py` | 503 on missing secret, KITTY_ENV=test bypass |
| `gateway/memory.py` | Delete duplicate function definitions |
| `gateway/domain_router.py` | Health priority multiplier |
| `gateway/llm_client.py` | `_is_offline` 30s cache with lock |
| `gateway/model_digest.py` | Dedupe free-to-paid events |
| `gateway/brief.py` | Use `build_worker_context("brief", ...)` |
| `gateway/researcher.py` | Use `build_worker_context("researcher", ...)` |
| `gateway/onboarding.py` | Use `build_worker_context("onboarding", ...)` |
| `gateway/learning.py` | Use `build_worker_context("learning", ...)` |
| `gateway/reset.py` | Use `build_worker_context("reset", ...)` |
| `gateway/troubleshooter.py` | Use `build_worker_context("troubleshooter", ...)` |
| `gateway/inventory.py` | Bump vision model to `claude-3.7-sonnet` |
| All 14 path-containing gateway files | Import from `gateway/paths.py` |
| `scripts/setup/gate-check.sh` | Phase 17 gate |

---

## Tests

### `tests/test_context_builder.py`
- `test_build_user_context_parallel_fetch` — both fetches called via gather
- `test_relevance_threshold_filters_low_scores` — chunks below `RELEVANCE_THRESHOLD` excluded
- `test_token_budget_truncates_memory` — memory section stays within `MEMORY_BUDGET_TOKENS`
- `test_token_budget_truncates_knowledge` — knowledge section stays within `KNOWLEDGE_BUDGET_TOKENS`
- `test_filter_before_truncate` — high-score old chunk kept over low-score new chunk when budget is tight
- `test_empty_sections_omitted` — no qualifying chunks → no headers in output
- `test_one_fetch_fails_other_succeeds` — memory failure → knowledge section still present, no exception raised
- `test_both_fetches_fail_returns_soul_only` — both fail → returns `("", "")` dynamic suffix, soul prefix unaffected
- `test_build_user_context_returns_tuple` — return type is `tuple[str, str]`
- `test_cache_prefix_contains_soul` — first element of tuple contains soul prompt text
- `test_build_worker_context_no_soul` — soul text never in worker output
- `test_build_worker_context_under_budget` — output within `WORKER_BUDGET_TOKENS`
- `test_build_worker_context_memory_none` — `memory=None` → no snippet section, no crash

### `tests/test_domain_router.py`
- `test_blood_test_routes_health_not_code`
- `test_pain_in_python_script_routes_health` — health wins with competing code keyword
- `test_medication_routes_health`
- `test_car_noise_routes_repair`
- `test_python_code_routes_code`
- `test_health_wins_tie`
- `test_general_routes_default`

All existing 65 tests must continue to pass.

---

## Execution Order

1. `gateway/paths.py` (with `validate_dirs`) + update all path imports — foundation commit
2. Structural fixes: C4 (memory.py + app.py duplicates), C5 (CORS None-filter), C2 (auth 503 + KITTY_ENV semantics), I9 (model_digest dedup)
3. Logic fixes: I7 (domain router 3× + `test_domain_router.py`), I8 (offline cache + lock)
4. `gateway/context_builder.py` + `tests/test_context_builder.py` — new module, TDD
5. Wire `build_user_context` into `gateway/app.py` (`/ask` + `/v1/chat/completions`)
6. Wire `build_worker_context` into all 6 worker modules + update any affected worker tests
7. I1/I2: Pydantic request bodies + `slowapi` rate limiting
8. C1: `.env.example` + `_validate_env()` startup validator
9. Phase 17 gate check
