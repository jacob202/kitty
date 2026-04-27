# Kitty — Handoff (2026-04-27)

## What Kitty Is
Personal AI assistant for Jacob Brizinski (Regina, SK). Three domains: hardware repair
(Sansui AU-7900 amplifier), automotive (Honda Ridgeline J35A9), and daily life / self-improvement.
Runs locally on a Mac with Apple Silicon.

## Stack
| Layer | Tech | Port |
|-------|------|------|
| Frontend | Next.js 16 + React 18 + Tailwind | 3000 |
| Backend | Flask + Flask-SocketIO | 5001 |
| Local LLM | MLX + Qwen3.5-4B-4bit | — |
| Fallback | OpenRouter (free tier → DeepSeek-R1) | — |
| Memory | SQLite-vec + LightRAG + Honcho | — |

Start everything: `./scripts/start.sh`

## Repo Layout
```
src/
  api/            Flask routes + SSE streaming
  core/           specialist_framework, circuit_breaker, silent_enhancer
  core/specialists/  11 specialist classes (Mike, Kelly, etc.) + registry.py
  space_kitty/    personality, core_orchestrator, llm_client
  memory/         KittyMemoryEnhanced, LightRAG store
  services/       context_service.py (KB query, LightRAG wrapper)
  autonomy/       safe_patch.py (worktree-based auto-patching)
  agents/         custom_agents.py, AgentSpec dataclass
config/specialists/  .md personality files + .json tool configs per specialist
garage-ui/        Next.js frontend (the actual UI Jacob uses)
tests/            116 passing
```

## Current State: Working
- **Frontend** — warm dark theme, orange tabby mascot, markdown chat bubbles,
  pill input bar, mobile-responsive (sidebar hidden on small screens, ☰ menu)
- **LAN / mobile access** — Next.js binds 0.0.0.0, start.sh prints mobile URL,
  `allowedDevOrigins` configured in `garage-ui/next.config.js`
- **SOUL.md** — injected into every web chat via `web_orchestrator._get_soul()`
- **Morning brief** — fires on socket connect via `executeCommand('/brief')`
- **Thinking tokens** — routed to ThinkingMonologue, not chat
- **Mike (automotive)** — full J35A9 KB loaded: fuel trim thresholds, Bank 2 gasket,
  VTC rattle, TC shudder, Regina pricing
- **mlx-lm 0.31.3** — installed in venv; model not yet downloaded (see below)
- **Tests** — 116/116 passing

## Uncommitted Changes (all safe, tests pass)
Run this commit to clean up:
```bash
git add garage-ui/app/page.tsx garage-ui/next.config.js \
  src/api/system_routes.py src/core/specialist_framework.py \
  src/services/ src/core/specialists/registry.py \
  src/core/silent_enhancer.py src/core/circuit_breaker.py \
  src/autonomy/__init__.py src/autonomy/safe_patch.py \
  config/specialists/*.json scripts/validate.sh autolaunch.sh \
  tests/test_core_circuit_breaker.py tests/test_silent_enhancer.py \
  tests/test_safe_patch.py tests/test_eval_loop_logging.py \
  tests/test_phonetic_scrubber.py src/eval/__init__.py \
  garage-ui/app/components/ActiveNodes.tsx
git rm src/graphs/__init__.py src/graphs/hardware_subgraph.py \
  src/graphs/investigative_subgraph.py src/graphs/main_graph.py \
  src/modules/__init__.py src/modules/kitty_software_analysis.py \
  src/modules/persona_engine.py src/modules/prompt_enhancer.py \
  src/modules/visual_diagram_generator.py src/sensory/__init__.py \
  src/modules/test_files/pe32.exe
```
Also add `evals/artifacts/` to `.gitignore` — 100+ JSON files shouldn't be tracked.

## Next Steps (ordered)

### 1. Commit the backlog (5 min)
Use the git commands above. All 116 tests pass. Just needs staging.

### 2. Download the MLX model (one-time, ~2.5 GB)
```bash
venv/bin/python3.12 -c "from mlx_lm import load; load('mlx-community/Qwen3.5-4B-4bit')"
```
Until this runs, every query falls through to OpenRouter. Set in `.env`:
```
KITTY_ENABLE_LOCAL_MLX=1
MLX_MODEL=mlx-community/Qwen3.5-4B-4bit
```

### 3. Wire OBD folder watcher (high value)
A parallel agent session built a complete OBD Fusion CSV watcher in
`/Users/jacobbrizinski/Library/Application Support/Claude/local-agent-mode-sessions/beae0a60-*/outputs/app/agents/automotive/data_sources/folder_watch.py`

It watches iCloud OBD paths, debounces 3s, parses CSVs, writes `.context/latest.md`.
Mike's fuel trim knowledge is useless without real OBD data — this is the highest-value
unshipped feature. Port to `src/data_sources/obd_watcher.py` and inject via Mike's specialist.

### 4. Test UI on phone
Restart server → hit `http://172.16.1.161:3000` (or whatever the LAN IP is) → verify:
- Orange tabby mascot
- Warm brown/orange theme (not black terminal)
- Markdown renders in responses
- ☰ menu opens sidebar on mobile
- Mic button works (iOS MIME fix is in page.tsx)

### 5. Remaining UI polish
- Light/warm theme toggle (v2 had `#FAF7F2` cream palette ready to go)
- Mode indicator pill in header (`● HARDWARE`)
- Thinking bubble slide-in animation

## Key Files to Know
| File | Purpose |
|------|---------|
| `web.py` | Flask app entry point, `create_app()` |
| `src/api/web_orchestrator.py` | NL chat routing (fast/balanced/max), SOUL injection |
| `src/space_kitty/core_orchestrator.py` | Slash command routing, specialist dispatch |
| `src/space_kitty/personality.py` | Loads SOUL.md sections |
| `config/specialists/SOUL.md` or `src/space_kitty/SOUL.md` | Jacob's profile, communication style |
| `config/specialists/mike.md` | Mike's automotive personality + J35A9 expertise |
| `garage-ui/app/page.tsx` | Main dashboard — all state, sockets, SSE |
| `garage-ui/app/components/ChatInterface.tsx` | Chat UI with markdown rendering |
| `garage-ui/app/globals.css` | Design tokens (warm dark palette) |

## Model Routing
| Tier | Model | When |
|------|-------|------|
| Fast (default) | MLX Qwen3.5-4B local | All queries when model is downloaded |
| Balanced | openrouter/free | MLX fallback |
| Max | deepseek/deepseek-r1-0528 | Explicit `/max` or reasoning flag |
| Emergency | claude-haiku-4-5 | All else fails |

## Known Issues / Watch Points
- `src/core/specialist_framework.py` imports `src.agents.custom_agents.AgentSpec` — that file exists at `src/agents/custom_agents.py`, import resolves fine
- `evals/artifacts/` accumulates JSON files on every eval run — add to `.gitignore`
- MLX model is not cached yet — first run will try to download; if offline it will fail and fall through to OpenRouter
- `garage-ui/next.config.js` must exist for LAN access to work (allowedDevOrigins)
