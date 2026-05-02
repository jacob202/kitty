# Kitty — Claude Code Rules

## Storage Targets (look this up before writing any data)
| Data | Store | NEVER use |
|------|-------|-----------|
| KB / knowledge ingestion | LightRAG | JournalDB |
| Journal entries | JournalDB | LightRAG |
| MCP entities/relations | @modelcontextprotocol/server-memory | — |

Violating this routing is the #1 source of data-loss bugs in this project.

## Before Touching Frontend
1. Search for the CSS class, DOM element ID, or JS function name before adding it
2. Previous agents left complete implementations — check first, always
3. Duplicate mic button CSS was introduced twice by not checking; don't do it again

## Model Routing
| Need | Model | Notes |
|------|-------|-------|
| Default + fallback | MLX Qwen3.5-4B (local) | T0–T3 complexity; free, private, no API key needed |
| Reasoning | deepseek/deepseek-r1-0528 | MODERATE tier (T4), paid — use sparingly |
| Premium | anthropic/claude-sonnet-4-6 | EXPENSIVE tier (T5), explicit requests only |

Local models are free. Use them first.

## File Organization
- Source code → `src/`
- Tests → `tests/`
- Docs and plans → `docs/`
- Config → `config/`
- Scripts → `scripts/`
- **NEVER save to project root**

## Specialist Framework
- Base class: `src/core/specialist_framework.py`
- Configs: `config/specialists/*.md`
- Python: `src/core/specialists/*.py`
- Specialists are Python classes, not agents (unless explicitly wired as agents)

## Voice Pipeline
`Browser MediaRecorder → POST /api/transcribe → src/api/transcription_service.py → faster-whisper → text`

## Skills
- Consolidated (reasoning/execution/planning): `consolidated-skills/`
- Project-level: `src/tools/superpowers/skills/`

## Validation Loop (REQUIRED after every code change)

After writing or editing any code, run this loop before reporting done:

```
1. Run tests:   venv/bin/python -m pytest tests/ -q --tb=short
2. If failures: read the error, fix the root cause, go back to 1
3. If passing:  run the full test suite (same command) to check for regressions
4. For eval-gated changes: POST /api/eval/run -d '{"suite":"smoke"}' (expect 200, not 422)
5. Only mark done when: all tests pass + eval smoke returns 200 + no new failures vs baseline
```

Never skip this. The reasoning route bug and ChromaDB regression both slipped through
because code was marked done before the loop ran.

## After Structural Changes
Run evals before marking done. ChromaDB changes once silently dropped eval scores — always verify.

## Test Command
```bash
venv/bin/python -m pytest -q
```

## Commit Rules
- Never commit `.env`, secrets, or credentials
- Run tests before committing
- Staged files must be exactly what should be committed

## Security
- Validate user input at system boundaries
- Sanitize file paths from user input
- No API keys in source files — ever

## Workflow Conventions

These prevent recurring frictions seen in past sessions.

- Always check for existing work before creating new code (especially CSS, components, helpers). A previous agent has likely already built it. Search first, then write.
- After making code changes, run `venv/bin/python -m pytest tests/ -q --tb=short` and report pass/fail counts BEFORE declaring done. Never claim done without a fresh test result.
- For any design doc, plan, or new markdown file longer than ~100 lines, present an outline first and wait for explicit approval. Do not begin writing the full content until Jacob says go.
- Jacob's live instruction overrides older project notes, handoff constraints, and generic brevity rules. If he says to override a rule, asks for the best possible product, or asks for full/detailed/complete output, state any conflict briefly and follow Jacob's latest direction.
- Detailed handoffs must preserve more detail than requested: chronology, raw decisions, rejected options, exact Jacob quotes or close paraphrases, files, commit SHAs, commands, tests, current dirty state, risks, and next actions. Do not compress a grilling session into only a short decision list; keep the source transcript or point to it, then add a decision ledger.
- When Jacob says a phase or feature is "complete" or "built," treat that as a review gate. Verify against live tree and tests, do not trust status optimism.
- When Jacob says "you missed a lot," "that doesn't seem like all of it," or "nothing works," stop summarizing from memory. Verify against the live tree and reproduce the issue before responding.

## Project Context (Known Gotchas)

These have all bitten previous sessions. Read before touching the named area.

- **Stack:** Python 3.12 + Flask + Flask-SocketIO + Next.js (`garage-ui/`). Local inference: MLX + Qwen3.5-4B. Memory: LightRAG + ChromaDB + SQLite-vec.
- **Storage routing — strict:** KB content → LightRAG (NOT JournalDB). Journal entries → JournalDB (NOT LightRAG). MCP entities → `@modelcontextprotocol/server-memory`. Wrong routing is the #1 source of data-loss bugs in this project.
- **Werkzeug flag required:** local SocketIO launch needs `socketio.run(..., allow_unsafe_werkzeug=True)` or Flask-SocketIO refuses to start.
- **TokenCapture leaks stdout to chat:** never use `print(...)` in backend code — it forwards into the user-visible SSE stream. Use `logging` instead.
- **Port split:** `localhost:5001` is the Flask backend/API. `localhost:3000` is the `garage-ui` frontend. Launcher confusion has happened before — always verify which surface is being tested.
- **Live orchestrator path:** `current_app.orchestrator` (not `current_app.reasoning_layer` or supervisor wiring). Reasoning routes that check the wrong path will look broken in web mode.
- **Pre-commit hook flags certain dynamic-execution function calls** (builtins like `eval` and similar). Rename related functions to `evaluate_` or `run_eval_` prefixes.
- **Linters auto-revert model constants:** clear `.pyc` cache after model routing fixes — `find . -name __pycache__ -exec rm -rf {} +`.
- **LightRAG empty results need fallback:** `query_knowledge_base()` should treat `[no-context]`, `no relevant document chunks`, and `LightRAG search error` as fallback signals and continue to ChromaDB.
- **Voice MIME types:** Safari/iOS records `audio/mp4`, Chrome records `audio/webm`. Both must be handled in `MediaRecorder` setup.
- **Launcher false negatives:** the 8-second readiness probe times out before app is fully up. Follow timeout with `./kitty status`, logs, and `curl http://localhost:5001/` before concluding the app is dead.
- **Workspaces (legacy reference only):** `/Users/jacobbrizinski/Documents/Kitty` is manuals/context, NOT runnable. The runnable repo is `/Users/jacobbrizinski/Projects/kitty`. The `kitty-system/kitty-app` migrated workspace was reconciled and deleted on 2026-05-01.

## Session Management

For long autonomous runs and clean handoffs.

- At session start, read recent entries in `docs/AGENT_COORDINATION.md`, `SESSION_SUMMARY.md`, and `CURRENT_FOCUS.md` before planning.
- For autonomous work spanning multiple tasks, write a checkpoint to a `HANDOFF-<date>.md` file (in `.claude/` or `docs/handoffs/`) after each task completes. Don't only write at session end — usage limits cut off too early.
- Always commit work-in-progress before risky operations (renames, large refactors, dependency changes). Commit often; small commits are easier to revert.
- For ordinary status or transfer handoffs, keep it concise: exact files changed, verified URLs, what's running, what's incomplete.
- For detailed/full/complete handoffs, or when Jacob says a handoff missed context, do the opposite of concise mode: include chronology, decisions, rejected options, source references, exact files, commits, verification, incomplete work, risks, and next steps. The "no narrative" rule does not apply in this mode.

## Cost Discipline

Conserve usage. Jacob has explicitly said "always conserve your usage" multiple times.

**Routing strategy: cheap-first, free-as-backup, premium-reserved.**

- **Default tier (cheap-and-reliable):** DeepSeek V4 Flash, Gemini 2.5 Flash, Groq paid tier — under $0.01/1K, deterministic, low queue risk. Use for execution work, code generation, file edits, test writing.
- **Backup tier (free):** OpenRouter free models (`qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`), Groq free tier. Use when daily budget is hit, primary is down, or task is genuinely simple. Accept rate-limit risk.
- **Premium tier (reserved):** Claude Sonnet for architecture, code review, multi-file synthesis, and Jacob-facing summaries. Claude Opus only for highest-leverage strategic decisions.
- **Why cheap-first not free-first:** free models have rate limits, queues, quality variance, and outage risk. Cheap models like DeepSeek Flash are deterministic. Free is the safety net.
- **Local first when offline or private:** MLX Qwen3.5-4B-4bit, Ollama qwen2.5-coder:7b. Free, private, and avoids any cloud dependency.
- **Cut parallel agents** the moment they stop producing evidence. Don't keep them alive "just in case."
- **Named-tool fidelity:** when Jacob explicitly names a tool (`coderabbit review`, `aider`, `crush run`), use that exact tool. Do not silently substitute.

## User Profile

Jacob's working preferences, harvested from cross-agent session history.

- He has explicitly said "NO experience" and "never have any idea what to do." Default to beginner-friendly explanations. No power-user jargon unless he asks.
- He cares about honest verification. If you say something is done, it must actually be done with test evidence. He reacts strongly to status optimism.
- For UX/UI work, Kitty should feel like a warm companion — mascot motion, mood-based visuals, morning brief that catches him up. Not a sterile operator console.
- Treat "nothing works," "nothing clicks," "it's not navigable" as functional bug reports, never cosmetic complaints.
- When recovering after a crash or losing context, reconstruct from repo artifacts and local history. Don't ask him to restate project state.
- He prefers narrow, surgical fixes on dirty trees over broad cleanup churn. When in doubt, do less.
- For voice/companion features, mascot presence and mood are first-class product requirements, not decoration.
