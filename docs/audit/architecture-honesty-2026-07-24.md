# architecture honesty audit: 2026-07-24

> **position in the kit**: ground truth of what code exists. feeds into `kitty-vision-gap-analysis.md` (what's missing that north star demands) and both planning documents (`kittybuilder-redesign.md`, `image-studio-character-system.md`) which plan on top of existing infrastructure.

comparison of documented architecture (docs/architecture.md, docs/north_star.md, docs/decisions.md, adrs) against actual code. every claim was verified by reading the source, not inferred from filenames or docs.

correction note — v1 of this audit (same date, earlier draft) falsely claimed the memory system, agent runner, mcp bridge, and skill registry were absent. they all exist with substantial implementations. this version corrects those errors and deepens the analysis.

## methodology

read all architecture docs, adrs, the full gateway directory tree (50 route files, 49 frontend components, ~60 python modules), plus: memory.py (424 lines), memory_graph.py (732 lines, 9 store adapters), memory_weave.py (650 lines), memory_policy.py (262 lines), memory_consolidation.py (204 lines), context_assembler.py (383 lines), context_enrichment.py, context_receipt.py, agent_runner.py (508 lines), mcp_tool_bridge.py (140 lines), skill_registry.py (191 lines), skill_import.py (187 lines), llm_client.py, auth.py, builder_*.py (6 files), image_*.py (4 files), page.tsx (1060 lines), views.tsx, and the component tree.

---

## subsystem audit

### 1. memory system — exists, substantial, multi-layer

**documented**: memory persistence for companion continuity.

**actual code**:
- `gateway/memory.py` (424 lines): mem0 wrapper with lazy init, add/search/list/delete, namespace filtering, session consolidation. backend: chromadb vector store + ollama embeddings (nomic-embed-text) + llm via litellm. fails safe — returns degraded context marker on error, never crashes.
- `gateway/memory_graph.py` (732 lines): **unified memory graph** — the most architecturally sophisticated subsystem in the codebase. 9 store adapters queried concurrently with per-store timeouts: memory (mem0), knowledge (chromadb), journal (sqlite), traces (log file text search), todos (sqlite), inbox (jsonl file), signals (signal store), facts (memory weave temporal kg), and optional mempalace. privacy gate (`_is_sensitive`) filters items with sensitivity tags unless query matches. token-aware budgeting (`_select_unified_items`) caps context at ~1200 tokens. returns `GraphResult` with per-adapter results + errors list.
- `gateway/memory_weave.py` (650 lines): temporal knowledge graph with confidence decay (λ=0.023, halves in 30 days), conflict resolution (`surface_conflict`), source provenance tracking (9 source types from user_correction to training_data). core operations: `fact`, `correct` (deprecate old + add new), `event`, `query` (with decay), `search`. ported from salvage codebase, ~6 methods still stubbed with NotImplementedError.
- `gateway/memory_policy.py` (262 lines): rule-based classification into memoryclass enum: pinned, working_context, preference, creative_thread, sensitive_support, archived, blocked. keyword-based classification with priority chain. `should_surface` determines whether an item appears in context (pinned always, blocked never, sensitive only when directly queried). `rewrite_sensitive_summary` transforms recovery/mental-health language into support-preference statements.
- `gateway/memory_consolidation.py` (204 lines): nightly dream: cluster traces by domain, llm summarize each cluster, store as memory facts, prune old trace log entries. called by cron action and `POST /session/end`.
- `gateway/context_assembler.py` (383 lines): the single entry point for read-path context. `assemble_context` (async) returns `ContextBundle` with system prompt string + memory items + live enrichment blocks + warnings. invokes skill_registry.suggest, memory_graph.search_all, user_context enrichment, domain_router, journal, prompts. partial-result contract: individual source failures become warnings, never exceptions.
- `gateway/context_enrichment.py` + `gateway/context_receipt.py`: enrichment pipeline and receipt tracking.
- migrations: `013_memory_weave.sql` (temporal kg schema), `022_chat_message_memory.sql` (chat persistence).

**verdict**: **exists and is deep.** the memory system is the most architecturally mature subsystem — better than the builder queue, better than the image system. 9 stores, concurrent fetch, privacy gates, token budgeting, consolidation pipeline, policy-based classification. the architecture.md description understates what actually exists. the gap is not "absent memory" but rather: (a) chat history browsing ui doesn't exist, (b) ~6 weave methods are stubbed, (c) mem0/chromadb/ollama is a heavy dependency chain for a local-first system.

### 2. agent runner — exists, has presets and reasoning loop

**documented**: autonomous task execution.

**actual code** (`gateway/agent_runner.py`, 508 lines):
- 5 agent presets: explorer, planner, coder, reviewer, researcher — each with distinct system prompt, max iterations, temperature.
- 6-phase reasoning loop: observe → orient → decide → act → verify → learn. `detect_phase` parses `PHASE: NAME` markers from agent output.
- async execution with `autonomy_state.db` persistence. `spawn(goal, agent_type)` → `get_status(session_id)` → `get_output(session_id)` → `stop(session_id)`.
- runs as background asyncio tasks with 5-minute hard timeout per agent.
- phase detection works on regex markers in agent output — no structured json contract, so phase detection is best-effort.

**verdict**: **exists and is functional but unvalidated.** agents run, phases are detected, status is persisted. gaps: no tool access (agents reason but can't execute), no sandboxing, no result validation against criteria, no spawning from chat conversations (agents are api-only). essentially a reasoning scaffold without execution capability — the builder_runner.py fills the execution gap but the two are not connected.

### 3. mcp tool bridge — exists, functional, has known limitations

**documented** (not prominently featured in architecture.md).

**actual code** (`gateway/mcp_tool_bridge.py`, 140 lines):
- `list_servers()`: discovers from plugin registry + `.mcp.json` config.
- `list_tools(server_name)`: returns tool schemas from plugin definitions.
- `invoke(server_name, tool_name, arguments)`: async subprocess invocation using json-rpc 2.0 protocol with 120-second timeout.
- `get_tool_schema_for_llm()`: formats tools for llm consumption with `mcp__{server}__{tool}` naming convention.
- **known limitation per code comment**: "full mcp protocol support (stdio/sse transport) is a future upgrade." currently reads tool schemas from plugin configs, not from live mcp server connection.

**verdict**: **exists and is usable but incomplete.** the bridge can invoke tools via subprocess + json-rpc. the missing piece is dynamic tool discovery from live mcp servers (protocol handshake, `tools/list`) and sse transport support. this is a known and acknowledged limitation.

### 4. skill registry — exists, yaml-frontmatter based

**documented** (not in architecture.md).

**actual code** (`gateway/skill_registry.py`, 191 lines):
- `discover()`: scans `.agents/skills/**/SKILL.md` for yaml frontmatter skills. caches after first scan.
- `get(name)`, `search(query)`: name/description/when_to_use search.
- `suggest(message)`: matches trigger phrases from `USE WHEN` clauses against user message.
- `invoke(name, context)`: strips frontmatter, returns rendered system prompt. does not execute — returns metadata for context assembler to inject.
- `gateway/skill_import.py` (187 lines): zip bundle import with zip slip defense, binary payload rejection (checks magic bytes), extension allowlisting, size/ratio/count bounds.

**verdict**: **exists and is well-designed.** skills are markdown documents with `USE WHEN / NOT FOR` trigger clauses — the same pattern as codegraph, build, sparring, and other opencode skills. the registry is used by context_assembler.py to inject skills into the system prompt. gaps: no skill versioning, no skill evolution (what skillopt does), no skill marketplace.

### 5. builder system — queue mature, runner pre-alpha

**documented** (architecture.md, adr 0017): autonomous mission execution with control plane separation.

**actual code** (`builder_*.py`, 6 files):
- `builder_queue.py`: kb-s1 state machine with 6 states (pending, active, done, paused, abandoned, error_edge). sqlite-backed with item-level status tracking. repair loop in `builder_loop.py`. this is the most carefully engineered queue in the codebase.
- `builder_initiative.py`: parses initiative manifests (markdown with yaml frontmatter). single parser (markdown), no schema validation, no pydantic models.
- `builder_runner.py`: phase 1c-alpha. worktree-based sandboxed execution with shadow mode. clones worktree, executes python script, parses structured output. single-shot only — no streaming, no iterative refinement, no sub-task decomposition, no validation.
- `builder_status.py`: read-only status projection from queue store. returns queue item status. does not project initiative-level progress.
- `builderpy.py`: thin facade over all builder components. adds no behavior — imports and wires.
- no test coverage for any builder module.

**verdict**: **queue is excellent, runner is alpha.** the state machine infrastructure is real. the execution capability is a proof of concept. the two are architecturally separated (queue doesn't depend on runner) which is correct but means the run phase is the weakest link.

### 6. llm client — accurate, well-structured

**documented**: provider-agnostic llm abstraction.

**actual code** (`gateway/llm_client.py`): table-driven provider dispatch (openai, anthropic, openrouter, google, deepseek, custom endpoints). d10 privacy boundary. rate limiting. retry logic. `route_model` for context-dependent model selection.

**verdict**: **accurate.** matches documentation.

### 7. auth — accurate

**documented**: bearer token auth.

**actual code** (`gateway/auth.py`): `bearertokenmiddleware` from `kitty_api_key` env var. applies to all routes.

**verdict**: **accurate.**

### 8. image system — functional basic, oversold advanced

**documented**: comprehensive image system with character consistency, multiple modes.

**actual code** (`image_*.py`, 4 files):
- `image_gen.py`: comfyui api wrapper. four workflow templates referenced (text2img, img2img, inpainting, upscale) but loaded generically without type validation. single backend (comfyui only).
- `image_characters.py`: v1 sqlite store (name, prompt, lora, negative_prompt). honest about v1 limitations — no versioning, no reference images, no face embeddings, no gallery.
- `image_jobs.py`: pending→running→done/failed lifecycle. no retry, no priority, no scheduling.
- `image_runner.py`: background thread polling comfyui. not asyncio.

**verdict**: **functional basic, oversold.** basic text2img works. v1 character store exists and is honestly named. inpainting, img2img pipeline, multi-backend, and character consistency are not implemented. lora support is in schema but not verified in workflow templates.

### 9. frontend — monolithic, 9/16 views empty

**documented** (architecture.md): modular layered presentation.

**actual code**:
- `gateway/kitty-chat/src/app/page.tsx`: 1060-line client component handling rendering, state, websocket, image jobs, and view routing. imports all views eagerly. no layer separation.
- `gateway/kitty-chat/src/lib/views.tsx`: `VIEWS` registry with 16 entries. 9 entries are `PlaceholderView` — only chat, settings, splash, and image studio have real code. all views imported eagerly via `getViewComponent()`, no lazy loading.
- `gateway/kitty-chat/src/components/`: 49 component entries across shared (ToolCallCard, MarkdownRenderer, etc.), views (ChatView, ImageStudio, etc.), and layout.
- tool call detection in `ToolCallCard.tsx`: regex-based pattern matching on llm output text, not structured tool call events. fragile.

**verdict**: **overstated.** the backend has reasonable layering (routes → services → db). the frontend is a monolith with no lazy loading, no independent routing, and 56% placeholder views. architecture.md describes an aspirational state.

### 10. routing layer — broad coverage, unknown quality

**documented**: not described in detail in architecture.md.

**actual code**: 50 route files under `gateway/routes/`. covers: ask, completions, chats, memories, journal, knowledge, search, projects, tasks, calendar, builder, council, cron, dream, experts, feedback, insights, inbox, integrations, logs, onboarding, personality, prompts, signals, status, telos, tutor, voice, and more.

**verdict**: **broad but uncharacterized.** 50 routes suggests ambition. without reading every file, the quality, test coverage, and request validation practices are unknown. the ask route (routes/ask.py) streams responses but does not persist messages — message persistence may be in routes/chats.py or routes/memories.py.

### 11. test coverage — unknown

**documented**: not claimed in architecture.md.

**actual**: `make test` and `python3.12 -m pytest tests/ -q --tb=short` exist as commands. builder modules have no tests. `npm test` exists for frontend. no coverage report or test count was examined.

**verdict**: **uncharacterized.** the test infrastructure exists but coverage was not measured in this audit.

---

## summary

| subsystem | files | lines ~ | status | critical gap |
|-----------|-------|--------|--------|--------------|
| memory system | 7+ | 2800+ | exists, deep | chat history ui, weave stubs |
| agent runner | 1 | 508 | exists | no tool execution, no sandbox |
| mcp bridge | 1 | 140 | exists, limited | no live protocol discovery |
| skill registry | 2 | 378 | exists | no versioning, no evolution |
| builder queue | 1 | ~300 | mature | — |
| builder runner | 1 | ~200 | pre-alpha | single-shot, no validation |
| llm client | 1 | ~400 | accurate | — |
| auth | 1 | ~50 | accurate | — |
| image gen | 4 | ~600 | functional basic | single backend, no consistency |
| context assembler | 1 | 383 | exists, deep | — |
| frontend | ~49 | ~5000 | monolithic | no routes, no lazy loading, 9 empty views |
| routing | 50 | — | broad | quality unknown |
| tests | — | — | uncharacterized | coverage unknown |

**corrected theme**: the previous draft of this audit claimed memory, agent runner, mcp bridge, and skill registry were absent. they all exist with substantial implementations. the codebase has real, deep infrastructure in memory (9 stores, policy, consolidation), context assembly, skill discovery, and agent reasoning. the documented gaps versus architecture.md are: (a) frontend is monolithic with placeholder views, (b) builder runner is pre-alpha, (c) chat history browsing ui doesn't exist, (d) image character consistency doesn't exist, (e) some weave methods are stubbed. these are real gaps but the foundation underneath them is more solid than architecture.md admits.

the architecture.md describes a less mature system than actually exists in some areas (memory, context assembly) and a more mature system than exists in others (frontend, image generation, builder execution). both directions are documentation drift.

---

## cross-references to other audit documents

- `kitty-vision-gap-analysis.md`: the strengths section should reference the 9-store memory graph, context assembler, agent presets, and skill registry as existing infrastructure to build on
- `kittybuilder-redesign.md`: should reference the existing agent_runner.py presets as patterns for builder sub-tasks; the context_assembler.py partial-result contract as a pattern for builder result handling
- `image-studio-character-system.md`: should reference memory_policy.py's privacy gate pattern for image character privacy; memory_weave.py's confidence decay for image character version confidence
- `repo-landscape.md`: memory_consolidation.py's nightly_dream maps to skillopt-sleep; memory_graph.py's 9-adapter concurrent fetch maps to 12-factor-agents factor 3 (own your context window)