# Kitty — Handoff to Gemini

Date: 2026-04-30
From: OpenCode (Claude)
To: Gemini
Suite: 363 passed, 2 warnings
Repo: `git@github.com:anomalyco/kitty` (not confirmed — verify before pushing)

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

## Critical: Two Workspaces

Kitty now lives in TWO places. **The active workspace is NOT a git repo.**

| Path | Purpose | Git? | Tests |
|------|---------|------|-------|
| `/Users/jacobbrizinski/Projects/kitty` | Legacy rollback | Yes | 363 pass |
| `/Users/jacobbrizinski/Projects/kitty-system/kitty-app` | **Active daily runtime** | No | Same code |

**Protocol**: Do all git work in the legacy repo. After committing, `cp` changed files to the migrated workspace. The migrated workspace is where `./kitty start` runs from.

```bash
# Step 1: Edit + test + commit in legacy repo
cd /Users/jacobbrizinski/Projects/kitty
# ... edit files ...
git add <files>
git commit -m "description"

# Step 2: Sync changed files to migrated workspace
cp /Users/jacobbrizinski/Projects/kitty/<file> /Users/jacobbrizinski/Projects/kitty-system/kitty-app/<file>

# Step 3: Run server from migrated workspace
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app
./kitty start
```

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
5. Validate (tests), commit (legacy repo), sync (migrated workspace), move to next task

---

## Validation Minimum

```bash
# Tests
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short

# Server
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app && ./kitty status

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
