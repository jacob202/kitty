# Parallel project review — 2026-04-30

**Assignment**: `msg-20260430-02` (OpenCode → claude)  
**Author**: Cursor (Composer) — draft filed to unblock synthesis; a future `claude` pass may amend or supersede this file while keeping the same path.  
**Inputs**: `docs/audits/project-context-audit-20260430.md` (Codex), `docs/audits/cursor-kitty-chat-inventory-20260430.md`, `docs/audits/operational-plan-20260430.md`, legacy checkout `src/`, `tests/`, `CURRENT_FOCUS.md`.

## 1. Executive take

Kitty’s **control layer and stabilization tests are ahead of the “product polish” story**. The codebase is large, route-heavy, and multi-memory; the highest leverage is **runtime parity** (legacy vs migrated), **one true backend URL for Garage UI**, and **narrowing broken optional paths** (MemoryWeave, specialist routing) before any broad UX or MCP work.

`CURRENT_FOCUS.md` correctly blocks UI polish and MCP expansion until specs exist — this review does not propose violating that.

## 2. Architecture and boundaries

**Strengths**

- Clear separation between Flask API (`src/api/`), orchestration (`src/orchestrator/`, `web.py`), specialists (`src/core/specialists/`), memory (`src/memory/`), and the Next app (`kitty-chat/`).
- Specialist framework centers on `BaseSpecialist` + registry + router; most specialists align with that model.
- Storage routing is documented (LightRAG vs JournalDB vs MCP memory); the risk is **runtime enforcement** across many optional subsystems, not the diagram.

**Fracture points**

- **Multiple “front doors” to intelligence**: REST chat, SSE `/stream`, Socket.IO events, legacy HTML routes (`/unified`, `/council`, …) coexist. Each path needs explicit contract tests or explicit deprecation.
- **Memory stack multiplicity** (LightRAG, Chroma, journal, MemoryWeave, correction paths): consistent with migration notes in the Codex audit; tests should lock **happy-path routing** per domain before migration specs expand scope.
- **Garage UI vs Flask origin**: hardcoded `:5001` plus relative `/api/source` is a **deployment topology** bug class, not a cosmetic issue (see inventory doc).

## 3. Test coverage and regression risk

Cross-check with Codex audit heuristics (~31 / 75 non-static routes touched by test string matches):

- **Well-covered areas** (by project history): Phase 3 brief/commands, default web chat mode, builder intake/file governance gates, eval dashboard backend tests, several memory/specialist modules.
- **High regression value, low obvious coverage**: hardware/BOM family, journal API family, `/api/chatbox/*`, reasoning trace CRUD, `/unified` / `/council` when supervisor features are partial, AI-dev monitor, many `/api/schematic/*` variants.
- **Recommendation**: tracer-bullet tests per **route family** (one happy path + one auth/validation failure) beat blanket route scanning.

## 4. Backward compatibility — legacy vs migrated

The Codex drift table is the source of truth for concrete file pairs. **Interpretation for planners**:

- Syncing **only** `shared.py` / Garage UI is insufficient when `web.py`, blueprint registration, and streaming guards diverge — users hit “works in git, fails in kitty-system” until copy discipline is spec’d.
- **Health routes**: disk vs live mismatch is a **process management** signal (stale PID) as much as a code signal; any cutover checklist should include “restart after copy” or health-based orchestration.

## 5. Specialist framework soundness

- **Registry vs router**: routing code keywords to `alex` while registry advertises `KittyCoder` is a product bug (wrong persona, wrong KB expectations). Fix belongs in a small spec: router table + tests + one golden routing example per domain keyword set.
- **KittyCoderSpecialist** outside `BaseSpecialist`: breaks uniform KB loading, eval assumptions, and future tooling. Either formally demote it in registry/docs or bring it under `BaseSpecialist` with real KB wiring (Codex operational plan A1 direction).
- **KB vs persona breadth**: many `config/specialists/*.md` files vs narrow LightRAG dirs — expect user confusion until domains are explicitly “parked” or ingested.

## 6. Polish and capability gaps (planning-only)

Aligned with `CURRENT_FOCUS` (no implementation here):

- **Config**: single env for public API base URL consumed by Garage UI (and optional Next rewrites).
- **Safety**: error boundary + user-visible failure path for SSE/Socket.IO; sanitizer or trust contract for inspector SVG.
- **Accessibility**: reduced-motion and theme variants are explicitly deferred by focus rules unless a spec opens them.

## 7. Conflicts / consolidation with other audit artifacts

| Artifact | Role |
|----------|------|
| `project-context-audit-20260430.md` | Ground truth for workspaces, routes, drift, smoke evidence |
| `cursor-kitty-chat-inventory-20260430.md` | Exact UI ↔ HTTP/SSE/socket matrix |
| `operational-plan-20260430.md` | Phased fix backlog — must be reconciled to **approved specs** before execution under `CURRENT_FOCUS` |

**Recommendation to head agent**: declare one canonical “pre-spec backlog” (either operational plan only or merged DECISIONS entries) to avoid three parallel truth documents.

## 8. Suggested next specs (priority order)

1. **Migrated runtime parity** — file list from Codex drift + explicit restart/health acceptance.
2. **MemoryWeave DB_PATHS** + import smoke in CI (tiny, high signal).
3. **Specialist router alignment** with registry + golden tests.
4. **Route family smoke bundle** — not 75 tests at once; pick top risk families from §3.
5. **Garage UI backend URL** — env-driven client config + documented proxy story for `/api/source`.

## 9. Validation

```bash
test -f docs/audits/claude-project-review-20260430.md
```

Expected: exit 0 from legacy checkout `/Users/jacobbrizinski/Projects/kitty`.
