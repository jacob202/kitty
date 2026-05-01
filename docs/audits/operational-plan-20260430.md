# Kitty Operational Plan — Fully Operational & Polished

Date: 2026-04-30
Source: Cross-agent audit (specialists, API, frontend, memory)

## Audit Summary

| Area | Status | Key Finding |
|------|--------|------------|
| Specialists | 10/12 full, 2 broken | KittyCoder is hard stub; KittySoul has no SOUL.md |
| API Routes | 78 routes, 28% tested | 2 routes crash, ~8 slash commands crash, 1 dead blueprint |
| Frontend | 14 components, 1 tested | No error boundaries, dark-only theme, no mobile sidebar/inspector |
| Memory | Mixed | MemoryWeave broken (import crash), CorrectionWorker cascaded broken, SQLiteVecStore is NOT vector search |
| Tests | 355 passing | Missing: 8 specialist tests, ~54 route tests, 13 component tests |

## Milestone Plan

### Phase A — Critical Fixes (Blockers)
**Goal**: Zero crashes. All registered features work.

| # | Task | Severity | Est. Time |
|---|------|----------|-----------|
| A1 | Wire KittyCoderSpecialist to BaseSpecialist — LLM, KB, devin.md loading | BLOCKER | 15m |
| A2 | Fix MemoryWeave — add `memory_weave` to DB_PATHS in db_config.py | BLOCKER | 5m |
| A3 | Remove honcho_bp dead blueprint or add routes | BLOCKER | 5m |
| A4 | Add supervisor shim methods for 8 crashy slash commands | HIGH | 20m |
| A5 | Remove or guard `/unified` and `/council` broken routes | BLOCKER | 5m |
| A6 | Create `config/SOUL.md` with proper personality content | HIGH | 10m |

### Phase B — Polish & UX (User-Facing)
**Goal**: Exceptional user experience. Dark/light toggle, mobile complete, error states.

| # | Task | Severity | Est. Time |
|---|------|----------|-----------|
| B1 | Add light theme variant (cream `#FAF7F2` palette from v2) + toggle | HIGH | 30m |
| B2 | Add React ErrorBoundary component wrapping app | HIGH | 10m |
| B3 | Mobile: make sidebar + inspector accessible on small screens | HIGH | 20m |
| B4 | Fix silent error swallowing — add toast notification system | HIGH | 20m |
| B5 | Inspector: sanitize SVG before dangerouslySetInnerHTML | MEDIUM | 5m |
| B6 | SettingsModal: persist model dropdowns to backend | MEDIUM | 15m |
| B7 | Add click-outside-to-close for CommandPalette + SettingsModal | MEDIUM | 10m |
| B8 | Mode indicator pill in header showing current mode name | LOW | 10m |

### Phase C — Hardening & Coverage
**Goal**: Production-grade reliability. Tests, error handling, slash commands.

| # | Task | Severity | Est. Time |
|---|------|----------|-----------|
| C1 | Implement broken slash commands (deepsearch, watch, scrape, repair, image, clear, cal, status) | HIGH | 40m |
| C2 | Add specialist unit tests for uncovered specialists (8) | MEDIUM | 30m |
| C3 | Add route tests for critical untested routes (brief, chatbox, /stream) | MEDIUM | 30m |
| C4 | Add frontend component tests (ChatInterface, CommandPalette, SettingsModal) | MEDIUM | 30m |
| C5 | Fix SQLiteVecStore to use actual vector search or rename | MEDIUM | 15m |
| C6 | Add `prefers-reduced-motion` support to animations | LOW | 5m |
| C7 | TypeScript strict mode: enable in tsconfig, fix errors | LOW | 20m |

### Phase D — Capability Completion
**Goal**: All advertised features actually work.

| # | Task | Severity | Est. Time |
|---|------|----------|-----------|
| D1 | Complete OBD folder watcher injection for Mike specialist | HIGH | 30m |
| D2 | Download MLX Qwen3.5-4B model for local inference | HIGH | 10m |
| D3 | Wire voice recording end-to-end (transcription → chat → response) | MEDIUM | 20m |
| D4 | Add specialist KB ingestion for domains with empty lightrag dirs | MEDIUM | 20m |

---

## Build Order

**Today**: Phase A (all blockers) → commit → sync.
**Then**: Phase B items B1-B5 (highest UX impact) → commit → sync.
**Then**: Phase C item C1 (slash commands) + Phase D items D1-D2 (OBD + MLX).
**Remaining**: Phase B polish + Phase C hardening + Phase D completion.

## Validation Gates

After each milestone:
```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
./kitty status
curl -sS http://localhost:5001/api/brief
curl -sS -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
curl -sS -X POST http://localhost:5001/api/chat -H "Content-Type: application/json" -d '{"message":"status smoke test","domain":"chat"}'
```
