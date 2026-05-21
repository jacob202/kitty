# Kitty end-to-end polish — design spec

**Date:** 2026-05-18  
**Status:** Draft after grill + zoom-out  
**Authority:** Complements `SESSION_HANDOFF.md`, `docs/ARCHITECTURE.md`; `CURRENT_FOCUS.md` not present in repo — scope validated against recent handoff (gateway + KittyChat integration).

---

## Stage 1 — Ideate (options)

### Approach A — **Thin integration polish** (recommended)

Tighten the already-built path: gateway proxy + `gateway.ts` + `page.tsx` with **explicit connection state**, **non-silent errors**, **debounced search**, and **consistent loading skeletons**. Minimal new abstractions.

- **Pros:** Low risk, matches current stack; ships in days; tests stay focused.  
- **Cons:** State still local to `page.tsx`; scaling to more panels adds prop drilling unless refactored later.  
- **Depends on:** Gateway reachable at `/proxy`, `/api/models`, `/brief`, `/search` stable.

### Approach B — **Client data layer** (TanStack Query / SWR)

Centralize fetches, retries, staleness, and deduplication for models/brief/search.

- **Pros:** One pattern for loading/error/retry; great if we add more endpoints.  
- **Cons:** New dependency + wiring cost; overlaps with simple `useEffect` today.  
- **Depends on:** Decision to invest in frontend architecture beyond “polish.”

### Approach C — **Unified “stack health” dashboard**

Expose `/health`+ combined status in UI before chat.

- **Pros:** Operators see LiteLLM/WebUI/gateway at a glance.  
- **Cons:** Extra backend surface; not required for “polish” if chat already works.

**Recommendation:** **Approach A** for this initiative; keep B as a follow-up if duplicate fetches or retry logic become painful.

---

## Stage 2 — Design (recommended approach)

### Goal

**Users always know** whether KittyChat is talking to the live gateway, **what failed** (models, brief, search, chat stream), and **what to do** — without losing the warm, dense layout.

### Architecture (components)

| Layer | Responsibility |
|--------|------------------|
| **Next proxy** (`gateway/kitty-chat/src/app/proxy/[...path]/route.ts`) | Same-origin bridge to FastAPI; must forward errors and timeouts clearly. |
| **`lib/gateway.ts`** | Single place for timeouts, parsing, fallbacks; should expose **typed result** (success vs failure), not only `null` on failure. |
| **`page.tsx`** | Owns chat state, streaming; should own **gateway connection slice** (models/brief/search status). |
| **`TopBar`** | Model picker + signal when model list is default/fallback vs live. |
| **`BriefPanel`** | Handles empty/partial brief; shows backend `error` if present. |
| **`RightBar`** | Search snapshot + brief; should show “search unavailable” vs “no hits.” |

### Data flow (happy path)

1. Mount → parallel `fetchGatewayModels()` + `fetchGatewayBrief()` (already parallel).  
2. User activity → `latestSearchQuery(activeChat)` → `fetchGatewaySearch` when the active chat’s **last user message** changes (today: effect on `activeChat`).  
3. Send → `streamChat` via proxy to Open WebUI/LiteLLM path (existing).

### Data flow (failure / degradation)

Today, `fetchGatewayModels` / `fetchGatewayBrief` / `fetchGatewaySearch` **return fallbacks or null on any error** — the UI cannot distinguish “no data” from “gateway down.”

**Target behavior:**

- Introduce a small **connection / gateway status** enum in the client, e.g. `live | degraded | offline`, derived from:
  - failed fetch vs 4xx/5xx vs `AbortError` (timeout),
  - optional: latency bucket (slow but OK).
- **Offline/degraded:** keep local chat UX usable; show a **compact banner** or rail dot (not blocking modals).

### Error handling (requirements)

| Scenario | UX |
|----------|-----|
| Models fetch fails | Keep `MODELS` fallback; show “using offline defaults” + retry. |
| Brief timeout/null | `BriefPanel` already can show structure; add “brief unavailable” when null after load. |
| Search fails | Distinguish empty results vs fetch failure in `RightBar`. |
| Stream errors | Already surfaces `⚠ Error` in message; ensure proxy errors map to readable messages. |
| All gateway dead | Single high-signal banner: “Can’t reach Kitty gateway — check `start_gateway.sh` / port.” |

### Search: performance / noise

- **Weakest current risk:** search runs when `activeChat` changes; rapid chat switching or message updates could spam `/search`.  
- **Mitigation:** debounce search **300–500ms** on derived query string; cancel in-flight request on unmount/query change (`AbortController` in `gateway.ts`).

### Testing

| Layer | Test |
|------|------|
| **Python** | Existing `tests/` for `/api/models`, `/brief`, `/search` contracts; keep green on every change. |
| **Frontend** | Extend `gatewayIntegration` (or RTL tests): mock `fetch` returning 500 → banner/state; mock ok → models list. |
| **Manual** | One checklist (below). |

**Manual smoke checklist (5 min)**

1. Gateway off → open KittyChat → expect degraded/offline signal; no infinite spinners.  
2. Gateway on → models list shows `kitty-default` (or live IDs from gateway).  
3. Brief loads or shows graceful empty.  
4. Send message → stream completes; error path if LiteLLM down.  
5. Switch chats → search updates without layout thrash.

### Scope

**In scope**

- Gateway visibility, error surfaces, debounced search, loading consistency, copy for degraded mode, tests for failure paths.

**Out of scope (this pass)**

- Open WebUI CSS parity, new gateway features, OpenCode/NIM (local dev tools), replacing proxy with direct LiteLLM from browser.

---

## Stage 3 — Grill (gaps)

| # | Gap | Severity | Mitigation in spec |
|---|-----|----------|--------------------|
| 1 | Silent `catch` → `null` / default models hides outages | **High** | Typed fetch results + UI signal |
| 2 | Search request churn on rapid navigation | **Med** | Debounce + abort |
| 3 | No single “health” URL — banner copy is heuristic | **Med** | Document: optional follow-up `GET /health` |
| 4 | `page.tsx` growth | **Med** | Keep slice small; extract `useGatewayFeed` hook only if file exceeds comfort (~400 lines after changes) |
| 5 | Token estimate is heuristic | **Low** | Document; don’t expose as billing truth |

**Contradiction check:** Brief timeout is 1500ms in `gateway.ts` while backend may cache longer — OK; UI must not assume fresh RSS every load.

---

## Stage 4 — Zoom out (go / no-go)

- **`CURRENT_FOCUS.md`:** Missing file — no formal conflict; aligned with `SESSION_HANDOFF` “next: frontend polish.”  
- **Smallest shippable slice:** (1) typed gateway fetch + banner, (2) debounced search, (3) RightBar failure copy, (4) one RTL test for 500 path.  
- **YAGNI:** No TanStack Query until duplication hurts.

**Decision:** **Go** on Approach A with the ordered implementation backlog:

1. Refactor `lib/gateway.ts` to return `{ ok, data, error }` (or discriminated union) without breaking call sites in one PR.  
2. Add **debounced** search + abort.  
3. Add **TopBar** or **layout-level** degraded indicator + retry buttons where cheap.  
4. Tests + manual checklist + update `SESSION_HANDOFF.md` / `HANDOFF.md` when done.

---

## Open questions (resolve during implementation)

1. Should the banner link to `docs` runbook or only show localhost port hints?  
2. Is `npm test` in CI for `kitty-chat` required on every PR or optional until stabilized?
