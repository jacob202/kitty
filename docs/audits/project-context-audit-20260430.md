# Project Context Audit - 2026-04-30

Agent: Codex
Lane: `audit-001`
Scope: read-only audit of legacy git checkout and active migrated runtime.

## Workspaces Audited

| Workspace | Role | Finding |
| --- | --- | --- |
| `/Users/jacobbrizinski/Projects/kitty` | Legacy rollback and canonical git history | Git repo on `main`; latest commit `4ae9aa6`; dirty with control-doc/runtime drift and many ignored/generated artifacts. |
| `/Users/jacobbrizinski/Projects/kitty-system/kitty-app` | Active migrated runtime | Not a git repo; server is running from this path on port 5001 as PID 29515. Treat as runtime copy, not history source. |

## Executive Summary

Kitty is usable enough for the current migration baseline, but it is not yet a fully operational/polished product surface.

Working baseline:

- `/api/brief`, `/api/command` with `/stuck`, `/api/chat`, `/api/eval/dashboard`, `/api/capabilities`, and `/stream` respond on the live migrated server.
- Garage UI builds according to Cursor's frontend inventory, and its main dashboard surface is identifiable and coherent.
- The P2 review issue about no-mode `/stream` requests has been addressed in both workspaces: `default_web_chat_mode()` defaults to `fast` when `KITTY_WEB_DEFAULT_MODE` is unset, and `tests/test_default_web_chat_mode.py` covers the no-mode `/stream` path.

Main gaps:

- `/health` and `/api/health` are registered but return **404** unless internal API mode is enabled (`ENABLE_INTERNAL_API` / env wiring per `system_routes.py`). This is an intentional gate, not stale server code.
- **Post–`runtime-001`:** `memory_weave` is present in `DB_PATHS` and `tests/test_memory_weave.py` locks import; remaining risk is runtime behaviour when MemoryWeave is exercised beyond import.
- **Post–`runtime-001`:** `route_specialist` routes code keywords to `KittyCoder`; deeper KittyCoder behaviour (LLM/KB wiring vs stub answers) is still a follow-up spec, not this audit snapshot.
- Route surface is broad: 75 non-static routes in current disk app, with only 31 string-matched in tests and 44 lacking obvious direct test references.
- Garage UI hardcodes Flask/Socket.IO to `http://<hostname>:5001`; changing `KITTY_PORT` breaks the frontend unless the UI is updated or proxied.
- Frontend polish gaps remain: no error boundary found, many failures are swallowed or console-only, inspector renders backend SVG via `dangerouslySetInnerHTML`, and there is no light theme or reduced-motion support.

## Evidence Commands

Read-only or audit-only commands used:

- `git status --short` and `git log --oneline -5` in legacy checkout.
- `git status --short` and `git log --oneline -5` in migrated workspace, which confirmed it is not a git repo.
- `rg`/`find` inventory over `src/api`, `src/core/specialists`, `tests`, `garage-ui/app`, `config/specialists`, `data/lightrag`, and `data/vector_store`.
- `cmp -s` and targeted `diff -u` for drift between key legacy and migrated files.
- `/opt/homebrew/bin/python3.12 -c 'from web import create_app; ...'` to list current disk routes.
- `/opt/homebrew/bin/python3.12 -c 'import src.memory.memory_weave'` to verify the MemoryWeave import failure.
- `./kitty status`, `ps -p 29515 -o pid,command`, and `lsof -p 29515 -a -d cwd` to confirm the live runtime path.
- `curl` smoke checks against live port 5001.

I did not restart the server, run destructive cleanup, or implement fixes.

## Live Runtime Smoke

Live server:

- `./kitty status`: running, PID 29515, `http://localhost:5001`.
- `ps`/`lsof`: PID 29515 is `/opt/homebrew/.../Python web.py` with cwd `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`.

HTTP results:

| Endpoint | Result | Notes |
| --- | --- | --- |
| `GET /api/brief` | 200 | Working. |
| `POST /api/command` with `/stuck` | 200 | Working. |
| `GET /api/eval/dashboard` | 200 | Working. |
| `GET /api/capabilities` | 200 | Working. |
| `POST /api/chat` | 200 | Responded with provider-key warning, not a real LLM response. |
| `GET /stream?query=audit%20ping` | 200 | SSE path responds. |
| `GET /health` | 404 | Expected when `ENABLE_INTERNAL_API` is false in app config (internal API gate); set config/env as documented for internal diagnostics — not stale code. |
| `GET /api/health` | 404 | Same gate as `/health`. |

## API Route Map

Current disk app exposes 76 total Flask rules, 75 excluding static.

Major route groups:

- Core chat/routing: `/api/chat`, `/api/route`, `/api/chatbox/start`, `/api/chatbox/stop`.
- SSE and legacy chat UI: `/`, `/stream`, `/chat`, `/unified`, `/council`, `/brief`, `/optic`, `/horizon`, `/interrupt`.
- Brief and commands: `/api/brief`, `/api/command`.
- System/settings/capabilities: `/health`, `/api/health`, `/api/capabilities`, `/api/capabilities/explain`, `/api/settings`, `/api/settings/update`, `/api/settings/profiles`, `/api/settings/profiles/active`, `/api/usage/openrouter`, `/api/diagnostics`, `/api/resilience/status`.
- Memory/journal: `/api/memory`, `/api/memory/forget`, `/api/memory/pin`, `/api/memory/library`, `/api/memory/feedback`, `/api/journal/entries`, `/api/journal/search`, `/api/journal/add`, `/api/journal`.
- Reasoning/evals/RLHF: `/api/reasoning/last`, `/api/reasoning/traces`, `/api/reasoning/traces/<trace_id>`, `/api/eval/run`, `/api/eval/dashboard`, `/api/eval/scorecard`, `/api/rlhf/options`, `/api/rlhf/preference`, `/api/feedback`.
- Hardware/BOM: `/api/schematic/analyze`, schematic component/viewer/equivalent routes, `/api/datasheet/fetch`, `/api/crossref/<part_number>`, BOM export/pricing/shopping-list/compare/search routes.
- Voice: `/api/transcribe`, `/api/transcribe-legacy`.
- AI dev monitor: `/ai-dev`, `/api/ai-dev/items`, `/api/ai-dev/refresh`.
- Swarm routes exist in code but are gated by `KITTY_ENABLE_EXPERIMENTAL_SWARM`.

Coverage estimate:

- 31 of 75 non-static routes had direct string matches in `tests/test_*.py`.
- 44 had no obvious direct string match. This is a heuristic, not a full coverage report.
- Notable untested/low-evidence surfaces: AI-dev monitor, most BOM/hardware routes, `/api/chatbox/*`, `/api/journal/*`, `/api/memory/library`, reasoning trace list/delete/detail, `/api/schematic/*`, `/api/search`, `/api/usage/openrouter`, `/unified`, `/optic`, `/horizon`, `/interrupt`.

## Specialists And KB State

Registered specialists from `src/core/specialists/registry.py`:

| Name | Domain | Class | KB path |
| --- | --- | --- | --- |
| Alex | audio | `AlexAudioSpecialist` | `data/knowledge_bases/audio/` |
| Mike | automotive | `MikeAutomotiveSpecialist` | `data/knowledge_bases/automotive/` |
| KittyCoder | code | `KittyCoderSpecialist` | `data/knowledge_bases/code/` |
| Avery | creative | `AveryCreativeSpecialist` | `data/knowledge_bases/creative/` |
| Jonny | design | `JonnyDesignSpecialist` | `data/knowledge_bases/design/` |
| Kelly | fitness | `KellyFitnessSpecialist` | `data/knowledge_bases/fitness/` |
| Taylor | growth | `TaylorGrowthSpecialist` | `data/knowledge_bases/growth/` |
| Morgan | infrastructure | `MorganInfrastructureSpecialist` | `data/knowledge_bases/infrastructure/` |
| KnowledgeAcquisition | knowledge_acquisition | `KnowledgeAcquisitionSpecialist` | `data/knowledge_bases/knowledge_acquisition/` |
| Rowan | research | `RowanResearchSpecialist` | `data/knowledge_bases/research/` |
| Kitty | general | `KittySoulSpecialist` | none |
| News | news | `NewsFeedSpecialist` | `data/knowledge_bases/news/` |

KB inventory currently records only audio, automotive, and code sources:

- Audio: Sansui AU-7900 summary.
- Automotive: 2006-2008 Honda Ridgeline service manual and DIY diagnostics material.
- Code: Claude Code context cleanup guide, agentic case study, Python Cookbook.

LightRAG files exist only for:

- `data/lightrag/audio`
- `data/lightrag/automotive`
- `data/lightrag/code`

This means most registered specialist domains currently have config/persona files but no obvious ingested LightRAG domain state.

Specialist risks:

- `KittyCoderSpecialist` is not a `BaseSpecialist` subclass and only returns canned Python/JavaScript answers.
- `src/core/specialists/router.py` returns `"alex"` for code/program/script/function/bug/Python/JavaScript keywords, which conflicts with the registry's code specialist.
- Soul/config files are richer than the KB state. There are many `config/specialists/*.md` persona files, but the durable KB inventory is narrow.

## Memory, Vector, And LightRAG State

Working/partially working:

- `src/services/context_service.py` uses LightRAG first, then falls back to `KittyMemoryEnhanced`/Chroma when LightRAG is unavailable or returns empty markers such as `no-context`.
- `KittyMemoryEnhanced` initializes Chroma collections for conversations, user facts, and documents, and has a deterministic-hash fallback if local embeddings are unavailable.
- `data/vector_store/library.json` and `data/vector_store/chroma_db/processed_files.txt` exist.
- `data/lightrag/ingest_registry.sqlite` exists.

Broken (at audit capture; **MemoryWeave DB key fixed** in `runtime-001` — import now succeeds when `DB_PATHS` includes `memory_weave`):

- ~~Importing `src.memory.memory_weave` fails immediately~~ **Resolved:** `get_db_path("memory_weave")` is wired; see `tests/test_memory_weave.py`.
- Remaining risk: runtime paths that *use* MemoryWeave beyond import are not fully exercised here.

Open risk:

- There are multiple memory systems: LightRAG, Chroma, vector store modules, JournalDB, correction memory, MemoryWeave, Mem0 stores, task tracker. The storage-routing rule is documented, but the runtime surface is broad enough that regression tests should be added before memory migration or cleanup.

## Frontend State

Cursor's read-only Garage UI inventory is incorporated here from `docs/audits/cursor-garage-ui-inventory-20260430.md`.

Frontend facts:

- Framework: Next.js 16.2.3 App Router with Turbopack.
- Main route: `/`.
- Entry: `garage-ui/app/page.tsx`.
- Components: `ActiveNodes`, `ChatInterface`, `CollapsiblePanel`, `CommandPalette`, `DensityContext`, `EvalDashboard`, `Inspector`, `JournalDashboard`, `Mascot`, `SettingsModal`, `Sidebar`, `SourcePill`, `SuggestionSidebar`, `ThinkingMonologue`.
- Frontend test found: `garage-ui/app/components/__tests__/EvalDashboard.test.tsx`.
- Cursor reported `npm run build` passed on 2026-04-30. I did not rerun build in this audit.

Backend coupling:

- `garage-ui/app/page.tsx` opens Socket.IO at `http://{window.location.hostname}:5001`.
- Chat and `/brief` stream through `EventSource('http://{host}:5001/stream?query=...')`.
- Schematic upload, memory library, voice transcription, settings, journal, and eval dashboard all target port 5001 directly.
- `SourcePill.tsx` uses relative `/api/source/{entityId}`, which resolves against the Next origin unless a proxy handles it.

Polish gaps:

- No error boundary found.
- Several fetch/media failures are swallowed or only logged.
- User-facing SSE error is hardcoded to "backend running on :5001".
- `Inspector.tsx` renders backend-provided SVG via `dangerouslySetInnerHTML`; this needs a sanitizer or strict trusted-source guarantee.
- No light theme found; current CSS is warm dark plus mode palettes.
- No `prefers-reduced-motion` handling found despite glitch/scanline/node animations.
- Mobile has a sidebar overlay, but the inspector is desktop-only and no mobile inspector replacement was found.

## Legacy vs Migrated Drift

The migrated runtime path is not a git repo, so drift must be tracked by file comparison or sync discipline.

Key comparisons:

| File | Status |
| --- | --- |
| `src/api/shared.py` | Same in both workspaces. P2 stream default fix is synced. |
| `src/api/core_routes.py` | Same. |
| `src/api/web_orchestrator.py` | Same. |
| `garage-ui/app/page.tsx` | Same. |
| `garage-ui/app/components/EvalDashboard.tsx` | Same. |
| `web.py` | Different. Legacy removes `honcho_bp` and uses `#!/usr/bin/env python3`; migrated still imports/registers `honcho_bp`. |
| `src/api/__init__.py` | Different. Legacy removes `honcho_bp` and adds `news_bp`; migrated still exports `honcho_bp` and lacks `news_bp`. |
| `src/api/streaming_routes.py` | Different. Legacy guards `/unified` with a 501 if the supervisor lacks `handle_unified_request`; migrated lacks this guard. |
| `scripts/run_gates.sh` | Different. Legacy has interpreter fallback, shell syntax checks, and agent-coordination checks. |
| `docs/AGENT_COORDINATION.md` | Different. Legacy has latest audit lane state and Cursor inventory handoff. |
| `specs/agent-coordination.spec.md` | Different. Legacy has tightened context-before-create wording. |

Interpretation:

- Runtime-critical chat defaults are synced.
- Control-plane and some route-safety changes are not fully synced back into the active migrated runtime.
- Because migrated app has no git metadata, commits in legacy do not by themselves guarantee the live runtime has received the same changes.

## Working vs Partial vs Broken

Working now:

- Server launches/runs from migrated path on port 5001.
- Core brief/stuck/chat/eval/capabilities endpoints respond.
- No-mode `/stream` defaults to `fast` on current disk code.
- Garage UI main page, SSE chat path, Socket.IO connection model, eval dashboard component, journal/settings/modal surfaces are present.
- Voice upload backend route exists, and frontend supports webm/mp4/wav MIME candidates.

Partial:

- `/api/chat` returns HTTP 200 but currently falls back to "No LLM API key configured..." on the live server, so provider/local model readiness is not proven in this smoke.
- Health routes are present on current disk and hidden behind the internal API gate in the default runtime config.
- Specialist configs and persona files are broader than actual KB ingestion.
- Memory stack has Chroma fallback; MemoryWeave import path is fixed (`runtime-001`); deeper MemoryWeave behaviour still needs coverage.
- Route tests cover important recent stabilization paths, but not the full API surface.
- Mobile has basic sidebar access but not the full inspector/workbench experience.

Broken or high-risk:

- ~~`src.memory.memory_weave` import failure.~~ **Resolved** under `runtime-001` (import + `DB_PATHS`).
- `KittyCoderSpecialist` is a stub compared with other specialists.
- ~~Specialist router maps code queries to Alex.~~ **Superseded:** router maps code keywords to `KittyCoder` (`runtime-001`); registry vs stub depth remains a product gap.
- ~~Migrated `/unified` route lacks the legacy guard for missing supervisor support.~~ **Addressed** in `runtime-001` / `streaming_routes.py` (controlled `501` when shim lacks `handle_unified_request`); confirm parity on migrated deploy.
- Health endpoint expectations are inconsistent: code hides health behind the internal API gate, while some validation docs treat health as public.
- Frontend is tightly bound to port 5001 and cannot follow alternate `KITTY_PORT` without code/proxy changes.

## Recommended Next Specs

1. Runtime parity sync spec:
   Sync the known legacy safety/control/runtime deltas into migrated app or explicitly reject them. Include `web.py`, `src/api/__init__.py`, `src/api/streaming_routes.py`, `scripts/run_gates.sh`, and coordination docs.

2. Critical runtime defects spec:
   Fix MemoryWeave `DB_PATHS`, specialist router/code specialist parity, and `/unified` guard parity. Validate with focused tests plus live curl. Separately reconcile whether health should remain internal-only or become public.

3. Route coverage hardening spec:
   Add focused regression tests for high-risk untested route families: hardware/BOM, journal/memory library, reasoning traces, chatbox, `/unified`, `/council`, `/optic`, `/horizon`, `/interrupt`.

4. Frontend configuration and safety spec:
   Replace hardcoded `:5001` with a single backend URL config, add error boundary/toast path, sanitize inspector SVG, and cover SourcePill origin behavior.

5. Specialist KB completion spec:
   Decide which specialist domains are first-class now, ingest or park the empty domains, and align persona/config/KB/test expectations.

## Validation For This Audit Artifact

Required assignment validation:

```bash
test -f docs/audits/project-context-audit-20260430.md
```

Status: passed (`test -f docs/audits/project-context-audit-20260430.md`).
