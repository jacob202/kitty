# Kitty Repo AGENTS

Canonical agent rules for **all agents** (Claude, Codex, opencode, Gemini, Goose).
Agent-specific stubs (CLAUDE.md, CODEX.md) reference this file.

---

## First Read Order (minimal)

1. `docs/STANDUP.md` (read first — has quick commands + key doc references)
2. `docs/ARCHITECTURE.md` (canonical live stack: gateway, Open WebUI, LiteLLM, ports, verification, KB rebuild — values taken from `kitty_gateway/*.sh`)
3. `docs/LAYER0_CONTROL_PLANE.md`
4. `docs/README.md` (documentation index and stale-doc rule of thumb)
5. `CURRENT_FOCUS.md`
6. `TASKS.md` (checklist; authoritative roadmap: `docs/UNIFIED_IMPLEMENTATION_PLAN.md`)
7. `docs/IMPROVEMENT_AUDIT.md` (2026-05-09 - start here for new work)
8. `docs/PROCESS_UPGRADES.md` (quick reference for workflows)

**Cursor:** Before **Compact chat**, refresh `SESSION_HANDOFF.md`, then read `docs/HANDOFF_AND_COMPACT.md`.

## Read When Relevant

- `docs/AGENT_COORDINATION.md` — **only** when claiming a lane, posting board messages, or resolving overlap (large file; never paste the whole thing into prompts).
- `SESSION_SUMMARY.md` — long-session continuity; pair with `SESSION_HANDOFF.md` using `docs/HANDOFF_AND_COMPACT.md` before Cursor **Compact chat**.
- `docs/DECISIONS.md` — durable decisions touching your task.
- `docs/FILE_GOVERNANCE.md` — before moves, renames, or archival.
- `docs/PARKED_FEATURES.md` — scope checks against parked work.

If these conflict with older notes, these files win.

---

## Project Structure

- Source code → **`gateway/`** (FastAPI — canonical runtime Python for this checkout)
- Shared types → `contracts/`
- Tests → `tests/`
- Docs and plans → `docs/`
- Config → `config/`
- Scripts → `scripts/`
- **NEVER save new source files to project root**

## Storage Targets

| Data | Store | NEVER use |
|------|-------|-----------|
| KB / knowledge ingestion | LightRAG | JournalDB |
| Journal entries | JournalDB | LightRAG |
| Semantic search | ChromaDB | — |
| MCP entities/relations | @modelcontextprotocol/server-memory | — |
| Corrections, various | SQLite | — |

Violating this routing is the #1 source of data-loss bugs.

## Model Routing

| Need | Model | Notes |
|------|-------|-------|
| Default + fallback | MLX Qwen3.5-4B (local) | Free, private, no API key needed |
| Reasoning | deepseek/deepseek-r1-0528 | Paid — use sparingly |
| Premium | anthropic/claude-sonnet-4-6 | Expensive — explicit requests only |

Local models are free. Use them first.

## Specialist framework (legacy retired)

The old **src/core specialists** tree and **config/specialists/*.json** configs were **removed** from this checkout (2026-05) in favor of a **gateway-centric** runtime. Do not recreate that layout without an approved spec—new domain logic belongs in **`gateway/`** (or clearly named modules under `contracts/`).

## Voice pipeline

`Browser MediaRecorder → POST /api/transcribe → gateway/stt.py → faster-whisper → text`

## Skills

- When present: `consolidated-skills/`, `.agents/skills/` (paths vary by checkout; verify before referencing).

---

## Execution Contract

- Before creating new specs, docs, or modules, scan this **canonical checkout**
  `/Users/jacobbrizinski/Projects/kitty` for existing equivalents (git,
  full tree). Prefer extending what exists; avoid duplicate control docs or
  parallel names that drift from old copies.
- Convert request -> one spec -> one build -> one validation -> one completion report.
- Dry-run defaults for intake/builder tools; require explicit write flags.
- Every meaningful change must include:
  - files changed
  - commands run
  - tests run
  - outcome and remaining risks

## Handoff Detail Rule

- Jacob's latest live instruction beats older handoff constraints, including "concise," "no narrative," "no new decisions," and "no clarifying questions."
- If Jacob asks for a detailed, full, complete, or best-possible handoff, preserve more detail than he asked for.
- Detailed handoffs must include chronology, decisions, rejected options, exact files, commit SHAs, commands, tests, current dirty state, open questions, risks, and next actions.
- Do not compress grilling sessions into only a decision list. Keep or reference the raw transcript/source context, then add a decision ledger.
- Concise transfer mode applies only when Jacob has not asked for detail and has not said prior context was missed.

## Scope Guards

- Respect `CURRENT_FOCUS.md` forbidden work list.
- Do not expand MCP, QLoRA, proactive nudging, or unrelated UI polish unless a new approved spec explicitly allows it.
- Do not delete raw chat logs.
- Do not delete or rename `/Users/jacobbrizinski/Projects/kitty`; it is the canonical runnable checkout.

---

## Before Touching Frontend

1. Search for the CSS class, DOM element ID, or JS function name before adding it
2. Previous agents left complete implementations — check first, always
3. Duplicate mic button CSS was introduced twice by not checking; don't do it again

## Workflow Conventions

These prevent recurring frictions.

- Always check for existing work before creating new code (especially CSS, components, helpers). A previous agent has likely already built it. Search first, then write.
- After making code changes, run the validation loop and report pass/fail counts BEFORE declaring done. Never claim done without a fresh test result.
- For any design doc, plan, or new markdown file longer than ~100 lines, present an outline first and wait for explicit approval.
- Jacob's live instruction overrides older project notes, handoff constraints, and generic brevity rules. If he says to override a rule, ask for the best possible product, or ask for full/detailed/complete output, state any conflict briefly and follow Jacob's latest direction.
- When Jacob says a phase or feature is "complete" or "built," treat that as a review gate. Verify against live tree and tests, do not trust status optimism.
- When Jacob says "you missed a lot," "that doesn't seem like all of it," or "nothing works," stop summarizing from memory. Verify against the live tree and reproduce the issue before responding.

---

## Validation Minimum

Run this after EVERY code change:

1. Run tests: `/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short`
2. If failures: read the error, fix the root cause, go back to 1
3. If passing: run the same command again. Before a release or when touching merge-gate / browser code, also run: `python3.12 -m pytest tests/ -q --tb=short -m ""`
4. For control-layer/build-tooling work: `bash scripts/run_gates.sh`
5. For runtime/API work, also verify:
   ```bash
   ./kitty status
   curl -sS http://localhost:5001/api/brief
   curl -sS -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
   ```
6. For eval-gated changes: `POST /api/eval/run -d '{"suite":"smoke"}'` (expect 200, not 422)

Default `pytest` skips browser + merge-gate tests (see `pytest.ini`).

Never skip this. The reasoning route bug and ChromaDB regression both slipped through because code was marked done before the loop ran.

## After Structural Changes

Run evals before marking done. ChromaDB changes once silently dropped eval scores — always verify.

---

## OpenAI/Codex Docs Rule

When answering OpenAI API/Codex usage questions:

- Use official OpenAI developer documentation first.
- Prefer MCP docs server when available: `https://developers.openai.com/mcp`.
- If MCP is unavailable, fall back to official domains only:
  - `developers.openai.com`
  - `platform.openai.com`
  - `openai.com`
  - `help.openai.com`

## Delegation Rule

- Delegate only independent, bounded lanes.
- Each delegated lane must include exact ownership (files/modules), validation command, and completion report.
- Close idle agents after results are captured.

## Git Rule

- Never commit without explicit user request
- Never commit `.env`, secrets, or credentials
- Never revert unrelated dirty changes
- Never use destructive git commands (force push, hard reset) unless explicitly requested
- Checkpoint verified green states before starting the next risky feature
- Run tests before committing
- Staged files must be exactly what should be committed

## Git Guardrails (Pocock-style)

**CONFIRM before running:**
- `git push --force` — overwrites remote history
- `git reset --hard` — discards local changes
- `git clean -f` — deletes untracked files

**Safe to run without confirmation:**
- `git add .` — staging
- `git commit -m` — creates commit
- `git push` — normal push

## Security

- Validate user input at system boundaries
- Sanitize file paths from user input
- No API keys in source files — ever

---

## Token Optimization Practices

Applies to all agents: Claude, Gemini, opencode, Codex, Goose.

### Core Rules

1. **Token Efficiency First** — Every LLM call must justify its token cost
2. **Prevention Over Compression** — Filter context before it becomes a problem
3. **Deterministic > Probabilistic** — Use jq/awk/scripts for deterministic tasks
4. **Cache Everything Static** — Reuse deterministic caching for system prompts / repeated completions (prior `prompt_cache.py` retired with `src/`; extend `gateway/` if you reintroduce it).
5. **Just-In-Time Context** — Load only what's needed for the current task

### Mandatory

- **Log token usage** — All LLM calls log to `data/kitty_token_log.jsonl` (JSONL: `{"ts","date","provider","model","operation","usage","metadata"}`)
- **Semantic caching** — Dedupe identical or near-identical completions when you have a cache layer wired
- **Truncation** — Prefer bounded reads (roughly 2K lines / ~50KB caps) before stuffing files into prompts
- **Local routing** — Route simple queries to cheaper models (`--quick` mode)
- **No broad Firecrawl** — Max 1-2 queries per run, use `scrape()` not `crawl()` for single pages
- **Use research tooling** — Firecrawl / Tavily / browser skills per task; avoid deep unmanaged crawls

### Quick Reference

| Situation | Action |
|-----------|--------|
| Simple status check | Use `./kitty status` (deterministic) |
| Count lines in file | Use `wc -l file` not LLM |
| Parse JSON | Use `jq` not LLM |
| Repeated query | Dedupe or cache when a cache exists; otherwise keep prompts stable |
| Long system prompt | Truncate or externalize prompts; avoid resending verbatim mega-blocks |
| File > 50KB | Trim or chunk reads before sending to the model |
| Web scrape (1 page) | Use `firecrawl scrape` not `crawl` |
| Session start | Use `./kitty quick` for deterministic commands |
| Quick status | `./kitty quick status` — server status |
| Quick test | `./kitty quick test` — run pytest |
| Quick health | `./kitty quick health` — API check |
| Quick tokens | `./kitty quick tokens` — recent token usage |
| Quick index | `./kitty quick index <pattern>` — search file index |
| Quick count | `./kitty quick count <path>` — count lines |
| Ingest / books queue | `scripts/ingest.py`, `scripts/enqueue_books.py`, `scripts/scout_queue.py` (verify with `ls scripts/`) |

### Monitoring

- Token log: `data/kitty_token_log.jsonl`
- Optimizer report: `docs/optimizer/feedback-latest.md`
- Run optimizer: `python .agents/skills/kitty-optimizer/scripts/optimizer.py --full`

---

## Project Context (Known Gotchas)

These have all bitten previous sessions. Read before touching the named area.

- **Stack:** Python 3.12 + Flask + Flask-SocketIO gateway on **`localhost:5001`**. Separate Open WebUI / LiteLLM per `docs/ARCHITECTURE.md` and `kitty_gateway/*.sh`. Local inference: MLX + Qwen3.5-4B optional. Memory: LightRAG + ChromaDB + SQLite-vec.
- **Storage routing — strict:** KB content → LightRAG (NOT JournalDB). Journal entries → JournalDB (NOT LightRAG). MCP entities → `@modelcontextprotocol/server-memory`. Wrong routing is the #1 source of data-loss bugs in this project.
- **Werkzeug flag required:** local SocketIO launch needs `socketio.run(..., allow_unsafe_werkzeug=True)` or Flask-SocketIO refuses to start.
- **TokenCapture leaks stdout to chat:** never use `print(...)` in backend code — it forwards into the user-visible SSE stream. Use `logging` instead.
- **Gateway:** treat **`localhost:5001`** as the Kitty API/control surface unless `docs/ARCHITECTURE.md` says otherwise for your stack tier.
- **Live orchestrator path:** `current_app.orchestrator` (not `current_app.reasoning_layer` or supervisor wiring). Reasoning routes that check the wrong path will look broken in web mode.
- **Pre-commit hook flags certain dynamic-execution function calls** (builtins like `eval` and similar). Rename related functions to `evaluate_` or `run_eval_` prefixes.
- **Linters auto-revert model constants:** clear `.pyc` cache after model routing fixes — `find . -name __pycache__ -exec rm -rf {} +`.
- **LightRAG empty results need fallback:** `query_knowledge_base()` should treat `[no-context]`, `no relevant document chunks`, and `LightRAG search error` as fallback signals and continue to ChromaDB.
- **Voice MIME types:** Safari/iOS records `audio/mp4`, Chrome records `audio/webm`. Both must be handled in `MediaRecorder` setup.
- **Launcher false negatives:** the 8-second readiness probe times out before app is fully up. Follow timeout with `./kitty status`, logs, and `curl http://localhost:5001/` before concluding the app is dead.
- **Workspaces (legacy reference only):** `/Users/jacobbrizinski/Documents/Kitty` is manuals/context, NOT runnable. The runnable repo is `/Users/jacobbrizinski/Projects/kitty`.

## Multi-Agent Coordination (learned from Phase 17)

When two agents (e.g. Claude and Gemini) are active simultaneously on the same repo:

- **Check `git log --oneline -10` before starting any task.** The most common wasted-work pattern is implementing something that was committed 30 minutes ago by the other agent.
- **Claim files before editing.** Drop a note in `docs/AGENT_COORDINATION.md` with: agent name, branch, files being touched, ETA. The other agent checks this before starting a task.
- **Never work on `main` directly.** Always use a worktree + feature branch. Gemini working on main + Claude on a feature branch creates merge confusion.
- **Divide by file, not by feature.** Features span files. Two agents editing `gateway/app.py` simultaneously = conflict. Assign each agent a file boundary they own for the session.
- **If you discover you duplicated work:** don't delete blindly. Read both versions, keep whichever is better or merge. Log the collision in AGENT_COORDINATION.md so the pattern is visible.

## Code Patterns (learned from Phase 17)

- **Use `gateway/paths.py` for all file paths.** Never hardcode absolute paths like `/Users/jacobbrizinski/...` in module code. Import `DATA_DIR`, `LOGS_DIR`, etc. from `paths.py`. Violating this immediately after writing `paths.py` is the easiest regression.
- **`LITELLM_BASE` and `LITELLM_KEY` are duplicated** in `app.py` and `llm_client.py` — known tech debt. Don't add a third copy. Next phase: move them to `paths.py` or env-driven `config.py`.
- **Define constants only if they're actually used.** Dead constants (`SOUL_TOKEN_CAP`) add confusion without value. Either use it or don't define it.
- **Model IDs between `llm_client.py` (direct OpenRouter) and `litellm_config.yaml` (LiteLLM proxy) use different formats** — `qwen/model-id:free` vs `openrouter/qwen/model-id:free`. Both routes hit the same model. Don't try to "fix" this by making them identical — the prefix difference is intentional routing.
- **Wire trigger functions.** Defining `is_journal_trigger()` or similar in a module is not enough — something in the request path must call it. Check: every new detection function should appear in `app.py` or equivalent entry point.
- **Journal synthesis must persist.** Any synthesized artifact (journal entry, summary, report) that is generated from a user session must be written to disk. Returning it only in the HTTP response loses it.

## Session Management

- At session start, read `docs/LAYER0_CONTROL_PLANE.md` and `CURRENT_FOCUS.md`. Open `docs/AGENT_COORDINATION.md` only when coordinating lanes with other agents; use `SESSION_SUMMARY.md` when resuming long work.
- For autonomous work spanning multiple tasks, write a checkpoint to a `HANDOFF-<date>.md` file (in `docs/handoffs/`) after each task completes. Don't only write at session end — usage limits cut off too early.
- Always commit work-in-progress before risky operations (renames, large refactors, dependency changes).
- For ordinary status or transfer handoffs, keep it concise: exact files changed, verified URLs, what's running, what's incomplete.
- For detailed/full/complete handoffs, or when Jacob says a handoff missed context, do the opposite of concise mode: include chronology, decisions, rejected options, source references, exact files, commits, verification, incomplete work, risks, and next steps.

## User Profile

Jacob's working preferences, harvested from cross-agent session history.

- He has explicitly said "NO experience" and "never have any idea what to do." Default to beginner-friendly explanations. No power-user jargon unless he asks.
- He cares about honest verification. If you say something is done, it must actually be done with test evidence. He reacts strongly to status optimism.
- For UX/UI work, Kitty should feel like a warm companion — mascot motion, mood-based visuals, morning brief that catches him up. Not a sterile operator console.
- Treat "nothing works," "nothing clicks," "it's not navigable" as functional bug reports, never cosmetic complaints.
- When recovering after a crash or losing context, reconstruct from repo artifacts and local history. Don't ask him to restate project state.
- He prefers narrow, surgical fixes on dirty trees over broad cleanup churn. When in doubt, do less.
- For voice/companion features, mascot presence and mood are first-class product requirements, not decoration.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
