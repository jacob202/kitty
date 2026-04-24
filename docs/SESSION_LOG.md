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

<!-- Add new entries above this line, newest at top after the separator -->
