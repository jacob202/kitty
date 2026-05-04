# Kitty App — Comprehensive System Audit Prompt

> Copy and paste this entire prompt to your AI of choice. It will perform a thorough,
> zero-mercy audit of the entire kitty project: codebase, skills, config, Crush integration,
> performance, memory, redundancies, and token efficiency.

---

## Mission

You are performing a **merciless, zero-bullshit, full-spectrum audit** of the Kitty project at `/Users/jacobbrizinski/Projects/kitty`. Your job is not to compliment — your job is to find what's broken, what's wasted, what's slow, what's redundant, and what's missing. Every finding must have **evidence** (file paths, line numbers, actual content) and a **recommendation** (specific action, not vague advice).

**Four categories of findings, each severity-rated P0–P3:**
- **P0 (CRITICAL):** Blocks functionality, wastes significant money/tokens, security risk
- **P1 (IMPORTANT):** Hurts performance, causes waste, needs fixing before further work
- **P2 (MINOR):** Should be addressed, but not blocking
- **P3 (COSMETIC/INFO):** Style, preference, observation

---

## Phase 1: Codebase Mapping

Map the entire project tree — every directory, every file of significance. Ignore `venv/`, `__pycache__/`, `node_modules/`, `.DS_Store`. For each major directory, answer:

- What does this directory do? (single sentence)
- How many files? Total lines?
- Entry points? Main orchestrators?
- Are there any files that are dead/unreachable/empty?
- Are there any files that duplicate functionality elsewhere?

### Key areas to examine

```
src/core/           → 35 files, ~10k lines — routing, memory, MCP, error handling, skills
src/api/            → 16 files, ~2.5k lines — HTTP/REST/streaming routes, socket handlers
src/tools/          → 20+ files — custom tool implementations
src/agents/         → 7 files — agent types, orchestrators, auto-fix loops
src/cli/            → 3 files — CLI menus, settings, UI
src/dashboard/      → 3 files — performance dashboard, metrics, integration
src/autonomy/       → 2 files — self-improvement engine, improvement trigger
src/affective/      → 1 file — emotive mirror
src/eval/           → 1 file — RLHF collection
src/config/         → 5 files + 6 profiles — config management, settings
consolidated-skills/ → 3 SKILL.md files — reasoning, execution, planning overlay skills
skills/             → legacy skills, skills-archive
src/tools/superpowers/skills/ → 18+ skills (TDD, debugging, code-review, etc.)
socratic-lens/      → CGI chains (6 YAML files), runner, tests, docs
master-prompt-architect/ → 1 SKILL.md
.crush/             → Crush state directory
```

---

## Phase 2: Configuration Audit

### 2a. Exam file: `/Users/jacobbrizinski/Projects/kitty/crush.json`

- **Provider configuration:** Only one provider (deepseek) configured. Both `large` and `small` models use `deepseek-chat`. The `reasoner` model uses `deepseek-reasoner` with `reasoning_effort: "high"`. Is this optimal? Could there be cost savings by using a smaller/cheaper model for `small`? Is there fallback if deepseek is down?
- **Context window:** 64k for all models. `max_tokens` varies (16384/4096/8192). Are these aligned with actual usage patterns?
- **LSP:** Python configured with `basedpyright-langserver` from `/Users/jacobbrizinski/Library/Python/3.9/bin/` — is this path correct? Does the LSP actually work? Check crush logs for LSP errors.
- **MCP servers:** filesystem, memory, sequential-thinking, pdf. The **memory MCP server is connected but the knowledge graph is EMPTY** (zero entities, zero relations). Why? Is memory working? Is it being used by any code? Check if `src/core/longterm_memory.py` and `src/core/memory_manager.py` actually integrate with it.
- **MCP pdf error:** The crush logs show `pdf = error: invalid character 'M' looking for beginning of value` — this MCP server is broken. Fix or remove.
- **Options:** `auto_lsp: true`, `auto_summarize: true` (set in crush state but not in crush.json? Check both).
- **Skills paths:** `["./src/tools/superpowers/skills", "./skills"]` — verify all skills under both paths load correctly. Crush logs show **multiple skill validation errors** — document every failing skill with exact error message.

### 2b. Crush runtime state (run `crush_info`)

- **Active model:** deepseek-chat for both large and small. Is this appropriate? DeepSeek V3 is powerful but slower/expensive for simple lookups.
- **Skills loaded/available:** 22 total, 14-15 loaded per session. Are all 22 actually used? Are there skills that should be loaded but aren't? Check the `loaded_this_session` count vs `active_total`.
- **Auto-LSP status:** `python = not_started` — the LSP never started. Check if this adds startup latency.

---

## Phase 3: Crush Optimization Audit

### 3a. Model strategy

- Only one provider. No fallback. If DeepSeek API goes down, Crush is dead. Should there be a secondary provider?
- Same model for `large` and `small` — defeats the purpose of having two tiers. The `small` model should be cheaper/faster for simple queries.
- Check if `auto_summarize: true` is working — is context being summarized effectively? Check `.crush/` for summarization artifacts.
- `max_tokens` for `large` is 16384 — is this sufficient for complex code generation tasks? The context window is 64k but output is capped at 16k.

### 3b. Context/token efficiency

- **Skills consume context on every load.** 14-15 skills loaded per session. Count the total token cost of loading all those SKILL.md files. Are they all needed? Are some bloated?
- **The `consolidated-skills/` overlay layer** (reasoning, execution, planning) adds ~2,600 words on top of the existing skills. Is this providing value or just consuming context? Each includes a "Design Notes" section explaining the overlay pattern — that's 3x duplication of the same explanation.
- **Legacy skills** in `skills/legacy-skills/` are still in the skills_path but many fail validation. They're still consuming scan time on every Crush startup. Should they be removed, fixed, or moved out of the skills path?
- **Surgical-coding SKILL.md** has broken frontmatter (YAML parsing error) — it's in the skills path but never loads. Fix or remove.
- **Technical-documentation SKILL.md** also has broken frontmatter.

### 3c. Memory/learning effectiveness

- **Memory knowledge graph is EMPTY.** The `@modelcontextprotocol/server-memory` MCP server is running and connected, but has zero entities and zero relations. This means:
  - No cross-session learning is happening
  - No patterns, preferences, or knowledge accumulates
  - The MCP server is wasting RAM and startup time for nothing
  - Check `src/core/longterm_memory.py` and `src/core/memory_manager.py` — do they actually write to the memory graph? If so, why is it empty? If not, why do they exist?
- **No git history** — the project is not a git repo. No version control for any code changes. This is a P0 risk (no rollback, no history, no collaboration).

### 3d. Speed/performance

- **Total Python files:** ~3,383 (including venv deps). App code is ~15,000 lines across ~50 files. Is there any profiling data? Check `src/core/profiler_engine.py`.
- **Are there synchronous bottlenecks?** Check for blocking I/O in the API routes, streaming, socket handlers.
- **Database files:** `.crush/` contains event_store.db, honcho.db, job_queue.db. How large are these? Are they indexed properly? Are old records ever pruned?
- **Import chains:** Check for circular imports or heavy import chains in `src/core/` that slow down startup.

---

## Phase 4: Feature Completeness Audit

### 4a. Feature map

Build a complete feature map from the codebase. For each feature, identify:

| Feature | Where | Status | Callers |
|---------|-------|--------|---------|
| Agent routing | `src/core/agent_router.py` | ? | ? |
| Domain routing | `src/core/domain_router.py` | ? | ? |
| Semantic routing | `src/core/semantic_router.py` | ? | ? |
| Cost routing | `src/core/cost_router.py` | ? | ? |
| Physical reality routing | `src/core/physical_reality_router.py` | ? | ? |
| Context management | `src/core/context_manager.py`, `context_loader.py` | ? | ? |
| Long-term memory | `src/core/longterm_memory.py` | ? | ? |
| Session memory | `src/core/session_memory.py` | ? | ? |
| Memory manager | `src/core/memory_manager.py` | ? | ? |
| Skill engine | `src/core/skill_engine.py` | ? | ? |
| Skill refinery | `src/core/skill_refinery.py` | ? | ? |
| Prompt refiner | `src/core/prompt_refiner.py` | ? | ? |
| Silent enhancer | `src/core/silent_enhancer.py` | ? | ? |
| MCP client | `src/core/mcp_client.py` | ? | ? |
| Model caller | `src/core/model_caller.py` | ? | ? |
| Error handler | `src/core/error_handler.py` | ? | ? |
| Rate limiter | `src/core/rate_limiter.py` | ? | ? |
| Circuit breaker | `src/core/circuit_breaker.py` | ? | ? |
| Profiler engine | `src/core/profiler_engine.py` | ? | ? |
| Event store | `src/core/event_store.py` | ? | ? |
| Tool registry | `src/core/tool_registry.py` | ? | ? |
| Task delegator | `src/core/task_delegator.py` | ? | ? |
| Specialist framework | `src/core/specialist_framework.py` | ? | ? |
| Aura loader | `src/core/aura_loader.py` | ? | ? |
| Onboarding | `src/core/onboarding.py` | ? | ? |
| Watchers | `src/core/watchers.py` | ? | ? |
| DB config | `src/core/db_config.py` | ? | ? |

For each: Read the file. Understand what it does. Check if it's actually wired up and called by anything. Identify dead code.

### 4b. API surface

- **Routes:** streaming_routes, core_routes, system_routes, settings_routes, memory_routes, reasoning_routes, hardware_routes, swarm_routes, BOM routes, honcho routes
- **Middleware:** `src/api/middleware/middleware.py`, `middleware_settings.py`
- **Socket handlers:** `src/api/socket_handlers.py`
- **Dispatcher:** `src/api/dispatcher.py`
- **Emitters:** `src/api/emitters.py`

Are all these routes functional? Are any half-implemented? Are they properly guarded (auth, validation)?

### 4c. Agents system

- `agent_types.py` — what agent types exist?
- `intake_agent.py` — entry point agent
- `auto_fix_loop.py` — self-healing loop?
- `sd_agent.py` / `sd_agent_img2img.py` — stable diffusion agents
- `swarm_orchestrator.py` — swarm orchestration
- `custom_agents.py` — custom agent definitions

How do these interact with the core routing system? Is the swarm system working?

### 4d. Dashboard

- `performance_dashboard.py` (581 lines) — substantial dashboard
- `performance_integration.py` (391 lines)
- `specialist_metrics.py` (521 lines)

Is this dashboard actually serving data? Where does it output? Is anyone looking at it?

### 4e. Tools inventory

List every tool in `src/tools/` (excluding `superpowers/` and `lightrag/venv`):
- `kitty_tools.py` (420 lines), `system_tools.py` (377 lines) — main tool collections
- `deep_search.py`, `web_search.py` — search tools
- `code_edit.py`, `read_file.py`, `search_files.py`, `list_directory.py` — file tools
- `tool_registry.py` — tool registration
- `image_gen.py`, `face_swap.py` — image tools
- `obd_parser.py` — OBD-II vehicle data?
- `n8n_trigger.py` — workflow automation?
- `obsidian_bridge.py` — Obsidian integration?
- `lightrag_wrapper.py` — RAG wrapper
- `analytics_engine.py` — analytics
- `claude_mem_wrapper.py` — Claude memory
- `vision_worker.py` — vision processing
- `base.py` — base class?

For each: Does it work? Is it used? Is it redundant with something else?

---

## Phase 5: Skill System Audit

### 5a. Skill inventory

Count every SKILL.md across all skill paths and the consolidated-skills overlay. For each:

- **Does it pass validation?** (Check frontmatter: valid YAML, name matches directory, description starts with "Use when")
- **Does it have cross-references to non-existent skills?** Find dead cross-refs.
- **What's the word count?** Skills should be <500 words per writing-skills guidelines. List the worst offenders.
- **Is it referenced anywhere?** Check if other skills or code actually reference it.
- **Is it a legacy skill that should be archived?** Skills in `skills/legacy-skills/` that fail validation and aren't referenced.
- **Is it duplicated?** E.g., `deepseek-reasoning-review` exists in both `skills/` and `skills/legacy-skills/`.

### 5b. Skill validation errors (from crush logs)

These are actively broken:
1. `surgical-coding/SKILL.md` — YAML parsing error (mapping values not allowed)
2. `technical-documentation/SKILL.md` — YAML parsing error (did not find expected key)
3. `visual-web-app-development/SKILL.md` — name mismatch with directory
4. `create-style-guide/SKILL.md` — name mismatch with directory
5. `flashcard-study-system/SKILL.md` — name mismatch
6. `typescript-code-review/SKILL.md` — name mismatch
7. `ai-app-improvement-loop/SKILL.md` — name mismatch

For each: Read the broken skill. Decide: fix (update frontmatter), archive (move out of skills path), or delete.

### 5c. Overlay skills (consolidated-skills)

- `reasoning/SKILL.md` (938 words) — 7-stage reasoning pipeline
- `execution/SKILL.md` (887 words) — 4-phase execution pipeline
- `planning/SKILL.md` (826 words) — 6-stage planning workflow

These are all over the 500-word guideline. Are they providing unique value or just summarizing existing skills? Check for actual unique content vs. paraphrased cross-refs. The "Design Notes" section is identical in all three (explaining overlay layer pattern) — that's ~100 words × 3 of pure duplication.

---

## Phase 6: Empty/Dead/Wasted Analysis

### 6a. Empty directories

- `kitty-desktop/` — contains only `.DS_Store`. What was this supposed to be? Is it dead?
- `garage-ui/` — contains only `.DS_Store` and empty `node_modules/`. Dead?
- `.worktrees/personal-ai-assistant/` — empty worktree? Was it cleaned up?
- `src/data/db/` — contains `orange_lab_pka.db` — what is this?
- `src/config/` — profile files exist but are they actually used?

### 6b. Database files — examine and report sizes

- `event_store.db`
- `honcho.db`
- `job_queue.db`
- `orange_lab_pka.db`

Are they growing unbounded? Do they have cleanup/rotation? What's storing data in them?

### 6c. Virtual environments

- `venv/` (at project root, Python 3.12)
- `src/tools/lightrag/.venv/` (Python 3.13)

Are both needed? Are they up to date? Is there significant package duplication?

---

## Phase 7: Recommendations

For each P0/P1 finding, provide a concrete recommendation:
- **What to do** (exact file changes, config changes, deletions)
- **Expected impact** (tokens saved, performance gained, bugs fixed)
- **Priority** (P0 fix immediately, P1 this week, P2 this month)

Group recommendations into a prioritized action plan with estimated effort (minutes/hours).

---

## Reporting Format

Produce a single markdown document with:

```markdown
# Kitty App — Full System Audit

## Executive Summary
[3-5 bullet points of the most critical findings]

## Severity Legend
P0 = Critical | P1 = Important | P2 = Minor | P3 = Info

## 1. Codebase Map
[Directories, files, functions — what exists]

## 2. Configuration Audit
[Crush config, provider strategy, model tiering, MCP status]

## 3. Optimization Analysis
[Token waste, context efficiency, memory graph, startup speed]

## 4. Feature Map
[Every feature, where it lives, does it work, is it wired up]

## 5. Skills Audit
[Every skill, validation status, word count, cross-ref health, duplicates]

## 6. Dead/Wasted Assets
[Empty dirs, dead code, duplicate files, unused imports]

## 7. Prioritized Action Plan
[Ordered recommendations with effort estimates and impact]

## Appendix: All Findings (table)
| # | Severity | Category | Finding | Evidence | Recommendation |
```

---

## Post-Audit State (2026-04-23)

### Summary

The audit was executed against the live codebase at `/Users/jacobbrizinski/Projects/kitty`. All 7 phases were completed:

| Phase | Status | Key Findings |
|-------|--------|-------------|
| 1. Codebase Mapping | ✅ Complete | ~15k lines across ~50 app files; `src/core/` (35 files, ~10k lines) fully orphaned — not wired into any active pipeline |
| 2. Configuration Audit | ✅ Complete | Crush.json validated; memory MCP server connected but had 0 entities (now populated: 57 entities, 47 relations); PDF MCP broken (`invalid character 'M'`); LSP (basedpyright) active with 400+ errors |
| 3. Optimization Audit | ✅ Complete | Single provider (deepseek) — single point of failure; same model for `large`/`small`; 3 skills with broken frontmatter; 5 skills with name mismatches; 3 broken imports fixed this session |
| 4. Feature Completeness | ✅ Complete | All 28 features mapped; most `src/core/` features unreachable from active code paths; web chat, voice, SocketIO pipelines verified end-to-end |
| 5. Skills Audit | ✅ Complete | 22 skills inventoried; 11 legacy skills validated (0 broken); 3 overlay skills over 500-word guideline; 3 broken frontmatter skills identified |
| 6. Dead/Wasted Analysis | ✅ Complete | Empty dirs: `kitty-desktop/`, `garage-ui/`, `.worktrees/`; DB files: `event_store.db` (1.8MB), `honcho.db` (10MB), `job_queue.db` (small); 2 virtual envs (venv + lightrag venv) |
| 7. Prioritized Action Plan | ✅ Complete | See AUDIT_REPORT.md for full prioritized list |

### Actions Taken This Session
- Fixed 3 broken imports: `memory_manager.py:8` (→ `src.utils.token_manager`), `macos_tools.py:183` (→ `src.config.config_loader`), `web_tools.py:32,60` (→ `src.tools.web_search` / `src.tools.deep_search`)
- Added audit stamps to 4 documentation files
- Created consolidated `AUDIT_REPORT.md`
- Populated MCP memory graph (57 entities, 47 relations)

### Remaining P0/P1 Items
1. **P0**: No API key fallback — single provider, no secondary
2. **P0**: No git history — no rollback capability
3. **P1**: Orphaned `src/core/` directory — 35 files, ~10k lines of unused code
4. **P1**: Memory MCP server may not be populated by active code — needs verification that entities persist across sessions
5. **P1**: 3 skills with broken frontmatter waste scan time every startup
