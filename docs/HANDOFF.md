# Kitty — Handoff to Gemini

Date: 2026-04-30 (updated 2026-05-01 — see **2026-05-01 incident** below)
From: OpenCode (Claude)
To: Gemini (and any agent picking up `arch-001` / `arch-002` / tool work)
Suite: **~399 passed**, 2 warnings (legacy checkout; run `pytest tests/` to confirm)
Repo: `git@github.com:anomalyco/kitty` (not confirmed — verify before pushing)

> Stale authority warning: this is a historical handoff. For current workspace and Layer 0 rules, read `docs/LAYER0_CONTROL_PLANE.md` first. Any instruction here that says `kitty-system/kitty-app` is the active runtime is superseded by the control plane.

---

## 2026-05-01 — Shelved WIP (read before restarting tool/specialist runtime)

**Canonical write-up:** `docs/archive/2026-05-01-shelved-wip-tool-specialist-runtime.md` — grep tag **`SHELVED-WIP-2026-05-01`**.

**What happened:** A **partial, uncommitted** experiment added `ToolRuntime`, `SpecialistRuntimeAdapter`, data-driven `definitions`, and rewired `registry.py` / `tool_manager.py`. It was **never in git as blobs** (untracked + local diffs only). Full **`pytest tests/`** failed: **`test_specialists_coverage`** (all twelve specialists) because adapters did not match how those tests patch `BaseSpecialist` internals, plus **`RuntimeError: Runner is closed`** on **`@pytest.mark.anyio`** tool/specialist runtime tests when the **whole** suite ran.

**What we did:** Reverted all dirty **tracked** files to the last good tree, **deleted** the **untracked** WIP files (exact list in the archive doc), kept the **design** by committing **`docs/plans/2026-04-30-unified-tool-runtime.md`** (Candidate A). **No further action required from Jacob** — tree is green; pre-commit runs full pytest again.

**What to do next (agents):** Do **not** resurrect the deleted files from memory alone. Follow **`docs/plans/2026-04-30-unified-tool-runtime.md`** + **`docs/plans/gemini-architecture-priorities-2026-04-30.md`** under an **approved spec**; keep **`SPECIALISTS` as concrete `BaseSpecialist` subclasses** until coverage tests or adapters are reconciled (details in archive §3–§5).

---

## What Kitty Is

Personal AI assistant for Jacob Brizinski (Regina, SK). Three domains: hardware repair
(Sansui AU-7900 amplifier), automotive (Honda Ridgeline J35A9), and daily life / self-improvement.
Runs locally on a Mac with Apple Silicon.

## Stack

| Layer | Tech | Port |
|-------|------|------|
| Frontend | Next.js 16 + React 18 + Tailwind | 3000 |
| Backend | Flask + Flask-SocketIO | 5001 |
| Local LLM | MLX + Qwen3.5-4B-4bit (not yet downloaded) | — |
| Fallback | OpenRouter (DeepSeek-R1) | — |
| Memory | SQLite-vec + LightRAG + Honcho + ChromaDB | — |

Start everything: `./scripts/start.sh` or `./kitty start`

---

## Canonical workspace (single checkout)

Daily work uses **one** git repository:

| Path | Purpose |
|------|---------|
| `/Users/jacobbrizinski/Projects/kitty` | **Canonical** runnable app, tests, and history |

The copy-first second checkout at `kitty-system/kitty-app` was **reconciled and removed** (2026-05-01). Do not revive a two-tree sync protocol unless `docs/DECISIONS.md` records a new migration decision.

**Protocol:** Edit, test, commit, and run `./kitty start` from `/Users/jacobbrizinski/Projects/kitty` only.

Historical detail (retired two-workspace instructions) is preserved in `docs/archive/2026-05-01-claude-handoffs/` and `docs/audits/CONSOLIDATION_REPORT_2026-05-01.md`.

---

## What OpenCode Just Did (This Session)

### Built: Agent Coordination Protocol
Three new files:
- `docs/AGENT_COORDINATION.md` — shared communication board for all agents. Has active lanes, inter-agent messages, feedback queue, debate topics, learnings log. Agents read this at session start, leave handoff at session end.
- `docs/AGENT_HANDOFF_TEMPLATE.md` — template for agent handoffs
- `specs/agent-coordination.spec.md` — spec for the coordination system

Four registered agents: `opencode`, `codex`, `claude`, `cursor`. All use the same coordination board. **Read `docs/AGENT_COORDINATION.md` at session start.**

### Ran: Full Project Audit (4 parallel explore agents)
Results synthesized into:
- `docs/audits/project-context-audit-20260430.md` — complete audit (all 4 domains)
- `docs/audits/operational-plan-20260430.md` — milestone plan: Phase A (blockers) through Phase D (capability completion)

### Executed: Phase A — Critical Blockers (ALL FIXED)

| # | What | Why |
|---|------|-----|
| A2 | `src/core/db_config.py` — added `memory_weave` to `DB_PATHS` | MemoryWeave crashed on import. CorrectionWorker cascade broken. |
| A6 | `config/SOUL.md` — created with full personality | KittySoulSpecialist fell back to 4-line hardcoded prompt |
| A3 | Removed `honcho_bp` dead blueprint from `src/api/__init__.py` + `web.py` | Registered but had zero routes |
| A5 | Guarded `/unified` and `/council` routes in `streaming_routes.py` | Crashed calling missing supervisor methods. Now return 501. |
| A4 | Added 10 supervisor shim methods in `web.py:_SupervisorShim` | ~8 slash commands called missing methods, crashed. Now return "not available in web mode." |
| A1 | Rewired `KittyCoderSpecialist` in `src/core/specialists/code.py` | Was a hard stub — canned responses, no LLM, no KB. Now extends `BaseSpecialist` with real LLM + KB. |

### Also done
- `KITTY_WEB_DEFAULT_MODE` env var: default is `fast` (local-first) — `src/api/shared.py:default_web_chat_mode()`
- Phase 4 merge gate: automated script at `scripts/run_phase4_merge_gate.sh`
- SOUL.md injection into web chat via `web_orchestrator._get_soul()`

---

## Pending: Phase B — Polish & UX

**This is what you should work on.** Phase A blockers are cleared. The app is functional but rough.

### B1: Light theme variant (HIGH — ~30m)
User wants dark/light toggle. v2 had cream `#FAF7F2` palette ready.
- `garage-ui/app/globals.css` — has 4 dark theme classes but NO light theme
- Need: `.theme-light` CSS class + toggle in SettingsModal or header
- Design tokens at `:root` in globals.css

### B2: React ErrorBoundary (HIGH — ~10m)
No error boundary exists — any component throwing unmounts the entire app.
- Add `garage-ui/app/components/ErrorBoundary.tsx`
- Wrap `<main>` in `page.tsx`

### B3: Mobile access to sidebar + inspector (HIGH — ~20m)
Both are `md:flex` only (hidden on mobile). Mobile users can't access thinking, suggestions, schematic upload, or memory archive.
- Options: bottom sheet, swipeable drawer, or tab bar at bottom

### B4: Toast notification system (HIGH — ~20m)
7+ places silently swallow errors (`catch {}` or `catch(() => {})`).
- Build ToastProvider + useToast hook
- Wire into settings save, journal save, voice recording, memory fetch

### B5: Inspector SVG sanitization (MEDIUM — ~5m)
`Inspector.tsx` uses `dangerouslySetInnerHTML` on backend SVG. Needs DOMPurify or sanitization.

Other Phase B items (see `docs/audits/operational-plan-20260430.md`):
- B6: Settings modal model dropdown persistence
- B7: Click-outside-to-close on CommandPalette + SettingsModal
- B8: Mode indicator pill in header

---

## Key Files Map

| File | Purpose |
|------|---------|
| `web.py` | Flask entry, `create_app()`, `_SupervisorShim` |
| `src/api/streaming_routes.py` | 15+ routes including SSE stream, chat, broken ones guarded |
| `src/api/socket_handlers.py` | Socket.IO handlers — `send_message` dispatches to CoreOrchestrator |
| `src/core/specialist_framework.py` | `BaseSpecialist` (ABC), `SpecialistResponse`, `SpecialistRegistry` |
| `src/core/specialists/` | 11 specialist classes + registry |
| `src/core/specialists/code.py` | Just fixed — now extends BaseSpecialist |
| `src/core/specialists/soul.py` | `KittySoulSpecialist` — reads `config/SOUL.md` |
| `config/SOUL.md` | Just created — core personality prompt |
| `config/specialists/*.md` | Per-specialist soul files (personality + system prompt) |
| `config/specialists/*.json` | Per-specialist tool configs |
| `garage-ui/app/page.tsx` | Main dashboard — all state, 18 useState, socket + SSE |
| `garage-ui/app/components/ChatInterface.tsx` | Chat UI with markdown + mascot |
| `garage-ui/app/globals.css` | Design tokens (warm dark palette, 4 theme classes) |
| `docs/AGENT_COORDINATION.md` | **Read this first** — inter-agent comms board |
| `docs/audits/operational-plan-20260430.md` | Full milestone plan A→D |
| `docs/DECISIONS.md` | Durable project decisions |
| `docs/FILE_GOVERNANCE.md` | Edit boundaries, protected files |
| `CURRENT_FOCUS.md` | What's allowed/forbidden right now |

---

## Agent Coordination Protocol

You are agent `gemini` — add yourself to the registry in `docs/AGENT_COORDINATION.md`:

1. Read the board at session start
2. Claim a lane before touching code
3. Leave a handoff at session end
4. Run autonomously — no asking for permission
5. Validate (tests), commit (canonical repo), move to next task

---

## Validation Minimum

```bash
# Tests
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short

# Server
cd /Users/jacobbrizinski/Projects/kitty && ./kitty status

# Smoke
curl -sS http://localhost:5001/api/brief
curl -sS -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
curl -sS -X POST http://localhost:5001/api/chat -H "Content-Type: application/json" -d '{"message":"smoke test","domain":"chat"}'

# Frontend
cd garage-ui && npx tsc --noEmit --incremental false && npm run build
```

---

## Boundaries (DO NOT)

- Delete raw chat logs (`data/sessions/`)
- Delete eval artifacts (`evals/artifacts/`)
- Touch `Icon\r` files (protected tree metadata)
- Move or rename `/Users/jacobbrizinski/Projects/kitty`
- Expand MCP, QLoRA, or proactive nudging
- Delete or commit generated databases

---

## Commit Style

Short, descriptive: `"Add thing: what it does"`. No multi-paragraph messages. Pre-commit hook runs full `pytest` before allowing commit (~15s).
