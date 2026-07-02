# Agent Handoff

**Date: 2026-07-02**
**Branch:** `main`
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`

---

## Where Things Stand

Phase B (storage consolidation), Phase C (chat + journal SQLite migration), and Phase E (PWA seam) are all shipped to main. The codebase compiles clean: 80 mypy errors cleared (#51), typecheck is now a blocking CI gate. Session persistence is wired (#765caa3 — sessions survive restart, SOUL is read from the real config file, stream errors are detected).

**Open PR #65** is the current gate: autonomous action queue (`action_queue.py` + `routes/actions.py` + `009_actions.sql`), calendar write (`calendar.event.create` T2 executor), and the tier sheet (`config/action_tiers.json`). Jacob's sign-off on the tier sheet is the only blocker.

## Known Issues (do not hide, do not "fix" without reading first)

| Issue                                                        | File                                                          | Status                                                                                                                                    |
| ------------------------------------------------------------ | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Fake data: loops and insights routes return hardcoded arrays | `gateway/routes/loops.py:12`, `gateway/routes/insights.py:12` | Still live on main — violates non-negotiable #1                                                                                           |
| Collection error in test suite                               | `tests/test_llm_client_alt_ua.py`                             | 1 file fails to collect; ~803 tests still run                                                                                             |
| `AGENT_HANDOFF.md` staleness gate                            | `tests/test_check_continuity_state.py`                        | Green when this doc has a fresh ISO date; update date on each handoff                                                                     |
| Local-only branches                                          | `codex/raycast-quick-capture`, `backup-local-main-0628`       | On Jacob's Mac only — not on origin. Will be lost on disk failure.                                                                        |
| SIRI_SHORTCUT.md                                             | `docs/SIRI_SHORTCUT.md`                                       | References a retired launcher (`kitty_gateway/start_all.sh`) and a hardcoded Tailscale IP. Tombstone or rewrite before anyone follows it. |
| Fake-data panels not in 004 acceptance criteria              | packet queue                                                  | 004's spec covers the UI side; the backend routes also need deleting/binding                                                              |

## Services

| Service           | Port | Start command |
| ----------------- | ---- | ------------- |
| Gateway (FastAPI) | 8000 | `./kitty up`  |
| LiteLLM proxy     | 8001 | `./kitty up`  |

`./kitty doctor --json` is the health oracle. Run it before claiming anything is broken or working.

## Gateway Layout

```
gateway/
├── app.py                 FastAPI app, lifespan, middleware, /health, /mood
├── chats_store.py         Chat session SQLite CRUD (sessions persist)
├── journal_store.py       Journal SQLite CRUD
├── memory_graph.py        Unified context retrieval — ALL reads go through here (D3)
├── context_builder.py     Prompt assembly
├── context_enrichment.py  Live-state enrichment (calendar/weather/todos/…)
├── llm_client.py          Model routing (domain_router → LiteLLM)
├── brief.py               Daily brief (RSS + journal themes; no fake fallback)
├── knowledge.py           Ingestion orchestration → Clerk → Librarian → Archivist
├── pdf_pipeline.py        PDF parsing (LlamaCloud → PyMuPDF fallback)
├── ingestion_queue.py     Background worker with circuit-breaker
├── archivist.py           ChromaDB vector store + embeddings
├── notify.py              Pushover push (complete module — currently no scheduler calls it)
├── nudge.py               Initiative engine (computes nudges; output currently orphaned)
├── action_queue.py        Autonomous action queue (in PR #65)
├── routes/
│   ├── chats.py           Chat CRUD
│   ├── completions.py     LiteLLM proxy + streaming
│   ├── actions.py         Action queue surface (in PR #65)
│   ├── loops.py           FAKE DATA — hardcoded arrays (fix before trusting)
│   ├── insights.py        FAKE DATA — hardcoded arrays (fix before trusting)
│   └── ...
└── kitty-chat/            Next.js frontend (PWA-ready, sessions rehydrate on load)
```

## Packet Queue

Work is organised into numbered packets in `docs/packets/`. Read `docs/packets/README.md` for the queue state (001–007 + 008–013 proposed).

**Current blocker:** Jacob's tier-sheet sign-off on PR #65 (packet 003). Packets 004 and 007 are stack-waiting.

## Decisions in Force

See `docs/DECISIONS.md`. D1–D8 are settled. Most relevant to new work:

- **D3**: All context reads go through `memory_graph.py`. Do not bypass.
- **D7**: `storage_router.py` is a thin write seam only. Do not expand it.
- **D8**: Ruff enforces E/F/W/I but not E501.

## Verification

Run these before calling anything done:

```bash
python3.12 -m pytest tests/ -q --tb=short --ignore=tests/test_llm_client_alt_ua.py
cd gateway/kitty-chat && npm test && npm run build
python3.12 -m mypy gateway/ --ignore-missing-imports --no-error-summary 2>&1 | tail -1
```

Expected: ≥803 passed, 0 failed (excluding the known collection error file), mypy clean.
