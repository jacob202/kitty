# Kitty — Session Log

**Purpose:** Append-only log of what happened each session. Never edit old entries. Each entry should take under 2 minutes to write.

Format:
```
## YYYY-MM-DD — [one-line summary]
**Done:** bullet list of what actually shipped
**Open:** anything left incomplete or blocked
**Corrections:** anything Claude got wrong that was fixed
```

---

## 2026-04-14/15 — Soul + journal interface (Goose session)

**Done:**
- Defined SOUL personality framework and canonical vision for Kitty
- Designed JournalInterface with pattern detection
- Established Honcho psychology layer

**Open:** Full Honcho integration pending

---

## 2026-04-18 — Project reorganization + disk cleanup

**Done:**
- Freed ~69GB of disk space from Mac
- Consolidated scattered files, cleaned ~/Documents and Airport NAS
- Fixed broken aliases and references after project move

**Corrections:** Directory rename mid-session broke Claude's bash sandbox. Had to switch to user terminal + rsync to finish.

---

## 2026-04-23 — Phase 2 + Phase 3 + Phase 4 + bug fixes

**Done:**
- Phase 4 eval platform: EvalRun/EvalCheck/EvalScore dataclasses, smoke suite (5 checks), regression detection, `/api/eval/run` route, 23 tests
- Fixed reasoning route bug: `_get_reasoning_layer()` now checks `current_app.orchestrator` first (not `supervisor.orchestrator`)
- Fixed context budget bug: direct named slot assignment instead of positional list
- Added validation loop to CLAUDE.md (exact 5-step wording)
- Browser smoke tests (Playwright/Chromium): test_page_loads, test_chat_input_exists, test_mic_button_exists, test_page_has_no_js_errors
- `scripts/eval_loop.py`: one-command pytest → eval route → regression check → iteration_log.md
- `scripts/verify_setup.sh`: checks Ollama, ChromaDB, LightRAG, deps
- direnv setup for auto-venv activation
- Post-edit hook: py_compile on every Python save
- Configured Goose with Ollama + qwen2.5-coder:7b
- Memory bootstrap files (this file + KITTY_CONTEXT.md, MEMORY_INDEX.md, EVALS.md)

**Open:**
- [x] Fix `POST /api/memory/corrections` (verified `/api/memory/forget`) returning 207 instead of 400 when `item_id` missing — DONE
- [x] Git pre-commit hook (needs manual terminal setup — Claude can't write to .git/hooks/) — DONE
- `test_web_launch.py` stale test: `test_launcher_uses_bounded_network_probe_and_resolved_curl` (pre-existing failure, not introduced here)
- Move root files: `checkpoint.log` → `data/checkpoints/`, `iteration_log.md` → `docs/`
- [x] Verify `scripts/eval_loop.py` runs end-to-end — DONE

**Corrections:**
- Playwright installed in venv (wrong) — needed `--break-system-packages` for Homebrew Python
- Browser tests failing: `allow_unsafe_werkzeug=True` missing from test fixture
- Hook using `python` instead of `/opt/homebrew/bin/python3.12`
- settings.json had fake `"skills"` field (not a real Claude Code config key)

---

## 2026-04-24 — [Cleanup + Bug Verification]
**Done:**
- Root directory decluttering (moved audits, skills, scripts, and logs to proper homes)
- Verified and finalized Priority 1.5 bug fixes (Reasoning layer, Context budget, Memory validation)
- Updated `crush.json` and `verify_setup.sh` to match new directory structure
- Improved test coverage for reasoning and memory product surface
- Validated all changes with full test suite (94 tests passed)

**Open:**
- Git pre-commit hook installation (requires manual EOF formatting)
- `test_web_launch.py` stale test

---

## 2026-04-24 — Model defaults → openrouter/free; memory docs; eval loop fixed

**Done:**
- Changed all model fallback defaults to `openrouter/free` (was `anthropic/claude-sonnet-4-5`, `deepseek-chat`, `gemini-2.0-flash`): `web.py`, `middleware.py`, `system_routes.py`
- Created 4 memory bootstrap docs: `docs/KITTY_CONTEXT.md`, `docs/SESSION_LOG.md`, `docs/MEMORY_INDEX.md`, `docs/EVALS.md`
- Fixed `scripts/eval_loop.py` Flask startup: replaced fixed 3s sleep with port polling (was failing with Connection refused)
- Full validation loop: **92 tests passed**, eval smoke **100% (5/5)**, no regression vs baseline
- Snapshot: `eval_snapshots/attempt_20260424T154304Z.json`, run_id `d4d8016d`

**Open:**
- [x] `POST /api/memory/corrections` (verified `/api/memory/forget`) still returns 207 instead of 400 when `item_id` missing — DONE
- Git pre-commit hook not installed (heredoc spacing issue in terminal — closing EOF must be at column 0)
- `test_web_launch.py` stale test (pre-existing, not introduced here)

**Corrections:**
- `eval_loop.py` FLASK_STARTUP_WAIT=3 too short — Flask takes ~5s to bind; fixed with socket poll

---

## 2026-04-24 — Specialist KB Training (Isolated LightRAG)

**Done:**
- Implemented **Domain-Isolated LightRAG Storage**: Separate directories for each specialist (`data/lightrag/{domain}`) to prevent knowledge cross-contamination.
- Refactored `LightRAGStore` to use a **Shared Global Event Loop**, improving efficiency and preventing thread exhaustion.
- Upgraded `IngestEngine`: Actually stores data in LightRAG (fixed lying logic) and uses **OpenRouter** (`google/gemini-2.0-flash-exp:free`) for faster, higher-quality extraction instead of Ollama.
- Established **Knowledge Inventory**: Automatic indexing of ingested files in `data/knowledge_bases/INVENTORY.md`.
- Refactored `BaseSpecialist` to bind directly to domain-specific KB stores.
- Validated architecture with fast-mode ingestion test.

**Open:**
- Tuning Circuit Breaker for parallel ingestion (current limits are tight for mass graph extraction).
- Mass ingestion of curated service manuals.

**Corrections:**
- Swapped Ollama for OpenRouter in LightRAG extraction per user directive ("Ollama is garbage").

---

## 2026-04-24 — Specialist-to-Agent Refactor & Tool Integration

**Done:**
- Refactored `BaseSpecialist` to use `AgentSpec` templates and `ToolCallingLoop`.
- Unlocked autonomous tool access for all domain experts (browse, search_files, read_diagnostics).
- Enabled parallel execution in `SpecialistCouncil` via `ThreadPoolExecutor`.
- Cleaned up Priority 2 tasks (stale pruned code, wired `ContextHierarchy`).
- Validated with full loop: 94 tests passed, 100% smoke eval, no regressions.

**Open:**
- Specialist KB training (LightRAG ingestion).
- MCP memory feedback loop integration.

**Corrections:**
- `SpecialistCouncil` previously blocked sequentially; now uses concurrent futures.
- `BaseSpecialist` was a static prompt wrapper; now a tool-capable agent runner.

---

## 2026-04-27 — Local MLX Multi-Specialist Router (Kitty v2) + Web Search

**Done:**
- Benchmarked Apple Silicon compatible MLX models, pivoting from 8B to 3B/1.5B to avoid Unified Memory OOM crashes.
- Created `model_loader.py` to handle dynamic model switching and caching.
- Developed `kitty_v2.py`: A persistent multi-specialist router with real-time token streaming, strict memory eviction (frees non-router models on switch), and session history.
- Implemented an autonomous Web Search tool using `duckduckgo-search` for the new "research" specialist, allowing it to fetch and synthesize live data without API keys.
- Configured optimized `mlx-community` 4-bit Safetensor models: `DeepSeek-R1-Distill-Qwen-1.5B` (Router), `Qwen2.5-3B-Instruct` (Code/Research), and `Llama-3.2-3B-Instruct` (Conversation).
- Reclaimed disk space by deleting older/incompatible models (8B DeepSeek and 1.5B Dolphin) from `~/.cache/huggingface/hub/`.

**Open:**
- Fine-tune specialists via QLoRA on the "ingest folder digest" (must follow strict memory limits: Rank 16, batch size 1).
- Wire `kitty_v2.py` logic directly into the main application orchestrator (`web.py` / `system_routes.py`).

**Corrections:**
- Initial 8B model benchmark caused `[METAL] Command buffer execution failed: Insufficient Memory`. Immediately pivoted to 3B models.
- Parallel MLX generation is impossible on single GPU buffers (Unified Memory limits). Adapted architecture to strictly load one specialist at a time while keeping the 1.5B router warm.

---

---

## 2026-05-08 — Loop Stabilization, Passive Chronicle & Engine Upgrades

**Done:**
- **Fixed Symlink Bug:** Resolved `PROJECT_ROOT` calculation error in `kitty_builder.py`; builder now works via symlinks and absolute paths.
- **Restored `kittybuilder` alias:** Re-created root symlink and added absolute path alias to `~/.zshrc`.
- **Icon File Purge:** Deleted 400+ problematic macOS `Icon` files and added an auto-purge step to `scripts/verify_setup.sh`.
- **Thinking Visibility:** Upgraded `stream_openrouter` to display `reasoning_content` in dimmed text for real-time visibility.
- **Passive Chronicle:** Updated `save_session()` to automatically capture a 2-sentence vision/vibe summary to this log on exit.
- **Format-Agnostic Parser:** Hardened `_extract_json` to handle multiple XML and JSON formats simultaneously.
- **Batch execution:** Enabled the builder to run multiple tools in a single turn, reducing stalling.
- **Autonomous Evaluator:** Created `scripts/overnight_retry.py` for headless task execution and grading.

**Open:**
- Fine-tune "Stall Guard" to prevent infinite nudges after task completion (heuristic-based).
- Validation of `deepseek-r1` as the primary autonomous implementation model.

**Corrections:**
- Fixed a `NameError` in `probe_tools` introduced during Groq disabling.
- Resolved a `SyntaxError` caused by a non-ASCII em-dash character.
- Fixed `ImportError` in `test_overnight_retry.py` by aligning with the latest script exports.
- Fixed API Key failure in `overnight_retry.py` evaluation step by utilizing `python-dotenv` instead of flawed manual parsing.

## Chronicle Entry — 2026-05-07 19:45
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapFpEwY7EY3y9Luyfiyh'}

## Chronicle Entry — 2026-05-07 19:46
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapFu3NQMuXvHWGQGnGKB'}

## Chronicle Entry — 2026-05-07 19:48
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapG3wNzQi7yLMTV8iBbB'}

## Chronicle Entry — 2026-05-07 19:49
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapG79tQAhncpSrhwZZ3f'}

## Chronicle Entry — 2026-05-07 19:52
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapGQ9TaZefMqQS7jCSsB'}

## Chronicle Entry — 2026-05-07 19:53
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapGRDJY6sse5XitLdRtJ'}

## Chronicle Entry — 2026-05-07 19:53
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapGS7mBnNvxjkAjWMCRB'}

## Chronicle Entry — 2026-05-07 19:53
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapGUBD7T5hmVVqm9SFkV'}

## Chronicle Entry — 2026-05-07 19:56
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapGff9Bo4jKu1SUokW2i'}

## Chronicle Entry — 2026-05-07 19:58
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapGqQHzsaJUCrNhXFbLh'}

## Chronicle Entry — 2026-05-07 20:00
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapGz1y5Vos4oLwH1YHzH'}

## Chronicle Entry — 2026-05-07 20:01
**Context:** Provider fallback failed. Anthropic: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CapH35aCmyGJ16EwZbkGi'}

## Chronicle Entry — 2026-05-07 20:02
**Context:** No LLM API key configured for web chat. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.

## Chronicle Entry — 2026-05-07 20:02
**Context:** No LLM API key configured for web chat. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.

## Chronicle Entry — 2026-05-07 20:03
**Context:** No LLM API key configured for web chat. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.

---

## 2026-05-10 — Gateway merge reconciliation + session closeout

**Done:**
- Verified integrated gateway merge lane (context builder + auth/env + validation + rate limit) on current `main`.
- Fixed `tests/test_llm_routing.py` drift so tests align with current router model IDs and explicitly test offline routing.
- Updated `gateway/knowledge.py` visual analyzer to load env before API-key lookup.
- Ran focused integration test bundles and knowledge tests successfully.
- Updated continuity artifacts (`SESSION_SUMMARY.md`, `docs/STANDUP.md`, dated handoff file).

**Open:**
- Lifespan deprecation warnings remain in FastAPI shutdown hook (`@app.on_event("shutdown")`).

**Corrections:**
- Resolved repeated false failures from routing tests caused by stale alias expectations (`kitty-default`/`kitty-agent`/`kitty-smart`) and unmocked offline behavior.

## Chronicle Entry — 2026-05-07 20:03
**Context:** No LLM API key configured for web chat. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.
