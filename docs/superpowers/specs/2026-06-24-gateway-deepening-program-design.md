---
date: 2026-06-24
accepted: 2026-06-24
topic: Gateway Architecture Deepening Program
status: ACCEPTED
branch: codex/phase-4-workflow
related:
  d7-amendment: docs/DECISIONS.md#d7-amendment-2026-06-24
  prior-adr: docs/DECISIONS.md#d7
---

# Gateway Architecture Deepening Program

## Executive Summary

Architecture review of `gateway/` surfaced **15 distinct friction points** across 6 clusters, plus 2 sub-frictions inside other rows (16 and 17 below). Of the 15, 6 are HIGH severity, 6 MEDIUM, 3 LOW. The dominant patterns are **read-path with no locality** (the 15-way fan-in through `context_builder` → `memory_graph` → `context_enrichment` with silent failures) and **routes as islands** (7 route files embedding their only copy of domain logic with `try/except → in-memory mock` fallbacks).

This plan addresses all 15 (and the 2 sub-frictions) by deepening the modules they sit in, in dependency order. **No new storage systems, no new auth, no new services** — the program tightens what already exists, in line with the active Phase 4 focus ("workflow polish and source-of-truth cleanup").

The program is **6 phases, sequenced**. Each phase is a shippable commit with its own green-test gate. Phases can be aborted after any one; nothing later depends on earlier phase *content*, only on earlier phase *direction*.

The current test count is **684 passing**. Every phase must end with ≥ 684 passing plus new tests for the deepened module.

---

## The 15 Frictions (+ 2 sub-frictions), Mapped to Phases

| Friction # | Severity | Cluster | Phase |
|---|---|---|---|
| 1 — `storage_router.py` is a pass-through | HIGH | Storage | 1 |
| 2 — `StorageRouter` realization is partial | HIGH | Storage | 1 |
| 3 — `routes/chat.py` dead shim | LOW | Cleanup | 0 |
| 4 — Read-path chain has no locality | HIGH | Read path | 2 |
| 5 — `StoreAdapter` shape fragmentation | MEDIUM | Read path | 2 (rolls into 1) |
| 6 — `sync.py` vs `storage_io.py` parallel impls | MEDIUM | Storage | 1 |
| 7 — Routes embed business logic | HIGH | Routes | 3 |
| 8 — In-memory mocks + try/except fallback | MEDIUM | Routes | 3 |
| 9 — Direct sqlite3/jsonl/os.environ bypass | HIGH | Storage | 1 |
| 10 — `swarm/` dead directory (the `lib/` directory was originally flagged but `lib/load_env_safe.sh` has 12 callers — see "Verified before delete" below) | LOW | Cleanup | 0 |
| 11 — `llm_client` 5 provider copies, 2 HTTP clients | MEDIUM | LLM | 4 |
| 12 — `journal.py` + `journal_store.py` divergence | MEDIUM | Storage | 1 |
| 13 — `http_client` global hides loop-bound re-init | LOW (latent) | Cleanup | 0 |
| 14 — Tests cover easy path, hard paths silent | HIGH | Tests | 5 (its own phase) |
| 15 — `try/except → mock` repeated in 6 places | MEDIUM | Routes | 3 |
| 16 — `plugin_registry` writes DB + legacy JSON | sub-friction of 2 | Storage | 1 |
| 17 — `routes/status.py` builds path from `__file__` | sub-friction of 9 | Storage | 1 |

**Verified before delete:** `lib/load_env_safe.sh` was originally listed as dead. Grep proves 12 callers across shell scripts, the `kitty` launcher, and tests. The `lib/` directory stays. This kind of "looks dead" assessment is exactly why Phase 0 has explicit grep gates.

---

## Approach Considered

Three options were weighed. See `Approach A` below for the chosen shape; `B` and `C` are documented in the planning conversation but rejected for reasons stated there.

- **A (chosen):** Sequenced deepening, cluster-by-cluster, dependency-ordered, each phase shippable.
- **B (rejected):** Top-down by severity — misses dependencies.
- **C (rejected):** Foundation-first big bang — user-facing wins too far away.

---

## Phase 0 — Foundation Cleanup

**Goal:** Delete the load-bearing-nothing modules, dead directories, and harden the small latent-bug seam. No behavior change. Green tests required.

**Frictions:** 3, 10 (partial — only `swarm/`), 13.

### Changes

| File | Action | Why |
|---|---|---|
| `gateway/routes/chat.py` | **Delete** | Dead shim. The only Python import touching the singular `chat` is the shim itself; `tests/test_chats_route.py:7` imports `routes.chats` (plural), not `chat`. `__all__` lists names (`_non_stream_response`, `_stream_response`) that don't exist in the module it re-exports from — silent AttributeError waiting to happen. |
| `gateway/swarm/` | **Delete** | Empty directory. Contributes zero code. |
| `gateway/http_client.py:1-33` | **Harden** | Add a docstring explaining the loop-bound re-init workaround (why we don't `await aclose()` on a closed loop). Add a test (`tests/test_http_client.py`) that exercises the loop-switch path with a fresh event loop. Not a rewrite — just make the workaround visible and tested. |
| `gateway/lib/` | **Keep** | `lib/load_env_safe.sh` has 12 callers (8 shell scripts, the `kitty` launcher, 3 test files). The original "dead directory" assessment was wrong; reverified with grep before any deletion. |

### Test

- `pytest tests/ -q --tb=short` — 684 passing, unchanged.
- New: `tests/test_http_client.py` with 3 tests covering (a) same-loop reuse, (b) loop-switch re-init, (c) closed-client eviction.

### Ship gate

- All targeted files changed.
- Tests green.
- `git grep -E "from gateway\.routes(\.|\s+import\s+)chat\b"` returns empty (the `\b` excludes `chats`).
- `git grep -l "gateway/swarm"` returns empty.
- `git grep -l "load_env_safe"` returns ≥ 10 hits (actual count: 11 — proves the script's callers were not deleted accidentally).

---

## Phase 1 — Storage Substrate

**Goal:** Make the storage substrate the real seam the docs claim it is. The substrate (paths, StorageRouter, `chats_store`, `journal_store`, `todo_store`, `plugin_registry`, `sync`, `storage_io`) becomes deep — small surface, real behavior behind it. `paths.py` stops being bypassed.

**Frictions:** 1, 2, 6, 9, 12, 16, 17.

### Decision: keep `storage_router.py`, deepen it

The deletion test fails for `storage_router.py` as currently written (it's a pass-through), but the *role* it occupies is real — there's a need for a single seam where state writes register, because Phase B's "single SQLite story" can't be enforced any other way. The right move is to **deepen the module, not delete it**. The depth comes from:

1. **Validation** — typed entry points reject bad shapes before they hit a store.
2. **Migration triggers** — when a store's underlying schema changes, the router runs the migration before forwarding.
3. **Telemetry** — every write logs to the **existing** `data/kitty_token_log.jsonl` with a `kind=storage_write` discriminator and `{ts, store, op, key, ms}`. No new log file — Phase 4 focus forbids new storage.
4. **Adapter registration** — the router is the place stores register themselves; routes never import a store directly.

### Inbox race fix (sub-friction G3)

`gateway/inbox_watcher.py:16` reads `inbox.jsonl` while `gateway/desktop_store.py` writes the same file. Two writers/readers on one file is a race surface (torn reads on slow disks). Phase 1 makes `desktop_store` the single writer through `StorageRouter`, and the watcher's read becomes a read-only handle. The file stays at `gateway/paths.py:INBOX_FILE` — no migration to SQLite (Phase B explicitly excluded the inbox).

### Substrate merge: `sync.py` + `storage_io.py` (sub-friction G6)

The two modules do parallel export/import with **different top-level shapes**:
- `storage_io.py:48-57` exports `{"format_version": 1, "stores": {plugin_settings, todos}}`
- `sync.py:24-73` exports `{version: 1, memories, journal_entries, todos, plugin_settings, preferences}`

The merge reuses `storage_io`'s shape (the `format_version` header and `stores` dict generalize better). `sync.py`'s `journal_entries` and `preferences` blocks move into `storage_io`'s `stores` dict under the same keys. `sync.py` is deleted. The wire shape of `/sync/export` and `/sync/import` stays the same — `routes/integrations.py:101-114` is unchanged.

### Changes

| File | Action |
|---|---|
| `gateway/storage_router.py` | **Deepen.** Add validation, migration, telemetry, registration. Stop being a pass-through. |
| `gateway/storage_io.py` + `gateway/sync.py` | **Merge** into one `gateway/storage_sync.py`. `storage_io`'s shape wins. `sync.py` deleted. `routes/integrations.py:101-114` wire shape unchanged. |
| `gateway/plugin_registry.py:236-249` | **Stop mirroring to legacy JSON.** Remove `_save_settings`'s JSON write. Add a one-shot `migrate_legacy_settings()` that's called from `plugin_registry.init_db()`. |
| `gateway/journal.py:24, 27-36` | **Pick one substrate.** `save_journal_entry` already goes through `journal_store`. The legacy `JOURNAL_LOG` constant stays read-only (so `sync.py:45-56` can finish migrating — moot after the sync merge), but every read path eventually goes through `journal_store.search_entries()`. Add a deprecation comment. |
| `gateway/sync.py:45-71` | **Reroute to `journal_store` + `plugin_registry`'s new SQLite-only path** as part of the merge above. |
| `gateway/inbox_watcher.py:16` | **Use `gateway.paths.INBOX_FILE`**, not the local redefinition. |
| `gateway/desktop_store.py` | **Writes go through `StorageRouter`**, not raw `open()`. Single writer. |
| `routes/feedback.py:25, 36, 65, 77` | **Route through a new `gateway/feedback.py` domain module** that uses `StorageRouter` for write. (See Phase 3.) The route file becomes a thin wrapper. |
| `routes/perf.py:24, 43, 77` | **Same pattern** — extract `gateway/perf.py` domain module, route goes through it. |
| `routes/status.py:13, 31` | **Use `gateway.paths` for `data/test-status.json`.** Stop computing from `__file__`. |
| `gateway/mempalace_adapter.py:84` | **Route the JSONL write through `paths.MEMPALACE_LOG_FILE`** (new constant). |
| `gateway/storage_router.py:18-21` | **Update the docstring** to match the new depth — no longer a "passthrough," now a real seam. |

### Test

- `pytest tests/ -q --tb=short` — 684 passing + new tests:
  - `tests/test_storage_router.py`: validation rejects bad shapes, migration triggers fire, telemetry recorded.
  - `tests/test_storage_sync.py` (renamed from `test_sync.py` + new): export/import round-trip, journal handled, plugin_settings handled.
  - `tests/test_plugin_registry.py`: legacy JSON migration is one-shot; post-migration, no JSON writes.
  - `tests/test_paths.py` (new): every module's import paths resolve to the right file under a tmp DATA_DIR.
- Grep checks: `git grep -l "DATA_DIR / " gateway/` returns empty (no module should construct a path inline). `git grep -l "with open(" gateway/` returns only `paths.py` and `desktop_store.py` (the latter is an explicit append-only inbox, kept as-is per Phase B scope).

### Ship gate

- All modules routed through `StorageRouter` or `paths.py`.
- `sync.py` and `storage_io.py` merged.
- Legacy JSON mirror removed from `plugin_registry`.
- All new tests passing.
- 684 + new tests, all green.

---

## Phase 2 — Read-Path Unification

**Goal:** The 15-way fan-in that builds context for a turn becomes one deep module with one testable surface. The two enrichment layers (`memory_graph.StoreAdapter` + `context_enrichment._ENRICHMENTS`) collapse into one. The `format_items+correlate` vs `Callable→str` interface split disappears.

**Frictions:** 4, 5 (rolled in), 14 (partial).

**Out of scope (sub-friction G1):** `voice_gate.get_drift_nudge` is **response-time**, not request-time. It fires after the response, based on session drift, not the incoming message. Putting it in the request-time assembler conflates two different time axes. Voice-gate stays in `voice_gate.py` and is called by `routes/completions.py` after the response, unchanged.

### New module: `gateway/context_assembler.py`

A single entry point: `async def assemble_context(message: str, parts_mode: bool, domain: str) -> ContextBundle` returning a structured object: `ContextBundle(system: str, memory_items: list[Item], live_blocks: list[str], warnings: list[str])`. Every call site that today goes through `context_builder.get_system_prompt` becomes a caller of `assemble_context`.

### Partial-result semantics (sub-friction G4)

The assembler **always returns a `ContextBundle`**, even when individual sources fail. The system prompt is built from whatever sources succeeded; `warnings: list[str]` records each failure with `{source_name, exc_type, message}`. Warnings are logged at WARN level and surfaced in `/status/glance` (Jacob's existing endpoint, added in this branch). The assembler only **raises** on total infrastructure failure: no LLM reachable AND no DB reachable. Any single source failing produces a partial result + warning, never an exception.

### Changes

| File | Action |
|---|---|
| `gateway/context_assembler.py` | **New.** Owns the full chain. `context_builder`, `memory_graph`, `context_enrichment` become internal seams (private to the assembler). |
| `gateway/context_builder.py` | **Becomes a thin façade** that delegates to `assemble_context` and returns the joined system prompt. Kept for one release to avoid breaking the route layer; deleted in a follow-up. |
| `gateway/memory_graph.py:38-77` | **Adapter ABC drops `format_items` and `correlate`.** Adapters return `list[Item]` where `Item` is a dataclass with `text: str`, `source: Source`, `score: float`, `ts: datetime`. Formatting and correlation live in the assembler, not in the adapter. The `routes/search.py:26` `or`-chain disappears — `item.text` is always there. |
| `gateway/mempalace_adapter.py` | **Migrate to the new Item shape.** Same for all 7 adapters. |
| `gateway/context_enrichment.py:118-119` | **Stop swallowing exceptions.** A failed enrichment becomes a `Warning` in the `ContextBundle.warnings` list. Logged at WARN, surfaced in `/status/glance`. |
| `gateway/voice_gate.py` | **Unchanged in this phase.** Drift-nudge remains response-time, called by `routes/completions.py`. (G1: response-time ≠ request-time.) |
| `routes/completions.py:65-69`, `routes/ask.py:36-44` | **Call `assemble_context`** instead of `get_system_prompt`. The response is built from the `ContextBundle`, not just the system string. |

### Test

- 684 + Phase 0 + Phase 1 tests, all green.
- New: `tests/test_context_assembler.py` (renamed from `test_context_builder.py` + new):
  - Adapter failure surfaces as a `Warning`, not silent skip. **This is the test the current suite doesn't have.**
  - `Item` shape is uniform across all 7 adapters — `item.text` works for every adapter.
  - Voice-gate is **not** called by the assembler (explicit negative test) — it's a response-time concern.
  - Partial result: 12 of 15 sources succeed, 3 fail, `ContextBundle` is returned with 3 warnings, system prompt is non-empty.
  - Total failure: 0 of 15 sources succeed (simulated), assembler raises `KittyError` with the source list.
  - End-to-end with a fake fan-in (3 in-memory adapters + 2 fake enrichments) — proves the orchestrator's logic.
- Deletable: `test_context_builder.py:45-62` (the "mock both halves" test) — its coverage is subsumed by `test_context_assembler.py` end-to-end tests.

### Ship gate

- `assemble_context` is the only entry point for context.
- Adapters return uniform `Item`.
- Failures surface as `Warning` or `KittyError` (per partial-result policy).
- `routes/search.py:26` no longer has the `or`-chain.
- 684 + new tests, all green.

---

## Phase 3 — Route Island Extraction

**Goal:** Each of the 7 route files that embeds its only copy of domain logic becomes a thin FastAPI wrapper around a domain module. In-memory mock state moves with the logic. **Every `try/except` that catches and returns fake data is removed** (user decision 2026-06-24, against the prime directive). If the route's intent was "show the user that there's no data," that becomes `if not real_data: return []` in the domain module — explicit and testable.

**Frictions:** 7, 8, 15.

### New domain modules

| New module | Wraps | Substrate |
|---|---|---|
| `gateway/feedback.py` | `routes/feedback.py` | `StorageRouter` (Phase 1) — `data/feedback.jsonl` and `data/kitty_errors.jsonl` move behind a `feedback_store` that the router manages. |
| `gateway/perf.py` | `routes/perf.py` | Same pattern — `perf_store` through `StorageRouter`. |
| `gateway/dream_insights.py` | `routes/dream.py` and `routes/insights.py` | `StorageRouter` + parser. The two routes collapse to one (`/insights`) with the storage and parsing in the domain module. |
| `gateway/loops.py` | `routes/loops.py` | A new `loops_store` behind `StorageRouter`. The 3 hardcoded loops become real data. |
| `gateway/monitors.py` | `routes/monitors.py` | Same — `monitors_store` through `StorageRouter`. |
| `gateway/insights.py` | `routes/insights.py` | A `insights_store` that *deliberately returns empty when there's no real data* (not mock data). The route surfaces "no insights" to the UI, never invented ones. |
| `gateway/prompts_catalog.py` | `routes/prompts.py` | A read-only catalog module. No state. |

### Changes

| File | Action |
|---|---|
| 7 new domain modules | **New** |
| 7 route files | **Slim to FastAPI wrapper** — request parsing, response shaping, nothing else. |
| `routes/dream.py:34-113` | **Move parser into `gateway/dream_insights.py`.** The route's `save_dream_insights` becomes a one-line domain call. |
| `routes/insights.py` | **Slim to wrapper** that delegates to `gateway/insights.py`. **No dedup** with `routes/dream.py` (G2: dedup is a UI-affecting wire change, out of scope). |
| `routes/integrations.py` (the cron/search portions) | **Slim the wrapper** for cron and search. **No move** of endpoints to `routes/cron.py` or `routes/search.py` (G2). |
| `routes/cron.py` (separate file) | **Slim to wrapper** around `cron` calls. The `/cron/...` and `/integrations/.../cron/...` both stay — same wire shape, both slim. |

### What this phase does NOT do (sub-friction G2)

No endpoint is renamed, deleted, or merged. The two-route-per-domain duplications (cron in both `routes/cron.py` and `routes/integrations.py`; insights in both `routes/insights.py` and `routes/dream.py`; search in both `routes/search.py` and `routes/integrations.py`) stay. The routes just become thin. **Dedup is a UI-touching wire change** — out of scope for this program. If the user wants dedup, it goes in a follow-up that includes the `kitty-chat` UI changes.

### Test

- 684 + previous phase tests, all green.
- New: `tests/test_feedback.py`, `tests/test_perf.py`, `tests/test_dream_insights.py`, `tests/test_loops.py`, `tests/test_monitors.py`, `tests/test_insights.py`, `tests/test_prompts_catalog.py`. Each tests the domain module's interface directly — no FastAPI.
- Deletable: the route-layer tests for these endpoints that exercised the in-memory mocks (they tested the wrong thing).

### Ship gate

- 7 domain modules exist and are tested.
- 7 routes are thin wrappers.
- Two-route-per-domain duplications collapsed (cron, dream/insights, search).
- `try/except ImportError → in-memory mock` pattern count: 0.
- **No `try/except` anywhere in the route layer catches and returns fake data.** (User decision 2026-06-24.) If a route previously hid an empty state behind a try/except, that empty state is now an explicit `return []` in the domain module. The route never invents data.
- Each fixed route is flagged in the Phase 3 PR description for review.
- 684 + new tests, all green.

---

## Phase 4 — LLM Client Collapse

**Goal:** Five near-identical provider functions collapse to one dispatcher driven by a `Provider` table. The two HTTP clients in one file become one (async `http_client.get_http_client`). Adding a new provider becomes data, not code.

**Frictions:** 11.

### Changes

| File | Action |
|---|---|
| `gateway/llm_client.py:336-694` | **Refactor.** One `_call_provider(provider: ProviderConfig, messages, ...)` that reads from a `PROVIDERS` table. The 5 copies die. |
| `gateway/llm_client.py:17` (sync `requests` import) | **Delete.** All call paths go through `http_client.get_http_client()`. |
| `gateway/llm_client.py:601-615` (AgentRouter alt-UA retry) | **Move into `ProviderConfig` as a `request_mutator` and `post_processor` pair.** The dispatcher calls them generically. |
| `gateway/llm_client.py:771-822` | **Already async.** Stays. The two-HTTP-client split is gone. |

### Test

- 684 + previous phase tests, all green.
- New: `tests/test_llm_client_dispatcher.py`:
  - Adding a fake provider to the table works (data, not code).
  - AgentRouter alt-UA retry fires on the right error and not on others.
  - The sync `requests` path is unreachable (covered by a `grep` check in CI, not by a runtime test).
  - Provider config from env vars is read once at startup, not 5 times per call.

### Ship gate

- One `_call_provider` function.
- One HTTP client (`http_client.get_http_client`).
- `PROVIDERS` table replaces 5 copies.
- 684 + new tests, all green.

---

## Phase 5 — Test Surface Tightening

**Goal:** The hard failure modes are tested, not just the easy paths. This is its own phase (sub-friction G7) — not a "consequence" of Phases 1–4. The deepened modules have better test surfaces, but several orchestration modules have weak coverage of their actual failure modes regardless. Phase 5 is a real ~1-day chunk of test-writing work.

**Frictions:** 14 (the part not already covered by Phases 1–4).

### Changes

| File | Action |
|---|---|
| `brief.py:567` (5 tests, ~10% coverage) | **Add tests** for `generate_brief`, `synthesize_brief_with_llm`, `detect_research_themes`, `rank_headlines_by_relevance`, `detect_brief_novelty`. The orchestration is the actual product; it must be tested. |
| `tests/test_memory_graph.py:171-192` (JournalAdapter test using legacy JSONL) | **Rewrite** to use `journal_store` — the test currently exercises the *old* code path. |
| `tests/test_llm_client.py` (AgentRouter alt-UA, `disable_agentrouter`, `KITTY_OPENROUTER_DIRECT_MODEL`) | **Add tests** for the 3 untested branches. |
| New: `tests/fakes/` | **A small fakes module** — `FakeInbox`, `FakeCalendar`, `FakeWeather`, `FakeHealth`, `FakeImessage`, `FakeAmbient`, `FakePatterns`, `FakeLearning`, `FakeNudges` — so the assembler can be tested with a real fan-in shape, not by mocking. The fakes are the test surface for "Kitty knows what's in my calendar." |
| `tests/test_context_builder.py:45-62` (the "mock both halves" test) | **Delete** — its coverage is subsumed by Phase 2's `test_context_assembler.py` end-to-end tests. |

### Test

- 684 + previous phase tests, all green.
- New: orchestration tests for `brief.py`, rewrites for the 2 test files above, fake sources for the assembler.
- Target: `brief.py` coverage ≥ 70%, `context_assembler` end-to-end with fakes covers all 15 fan-in sources.

### Ship gate

- Every orchestration module (assembler, brief, llm_client dispatcher) has tests for its real failure modes.
- No test relies on the legacy substrate where the new substrate is canonical.
- 684 + new tests, all green. The exact target isn't fixed, but should be ≥ 750.

---

## Cross-Cutting Concerns

### Error handling

The "Fail loud, never mask" prime directive from `AGENTS.md` is currently violated by:
- `context_enrichment.py:118-119` (silent `logger.debug`)
- 6 route functions (`try/except ImportError → in-memory mock`)

Phase 2 fixes the first. Phase 3 fixes the second. **Every phase must end with a `git grep -nE "(logger\.debug|except \(ImportError|except Exception)" gateway/` audit** and a written list of remaining sites with rationale (some silent logs are correct — e.g. expected retry paths).

### Observability

`StorageRouter` telemetry (Phase 1) feeds `/status/glance` (already exists at `routes/status.py`). The assembler warnings (Phase 2) feed the same endpoint. The fakes (Phase 5) are not for production — they exist only to make the assembler testable.

### Documentation

- `docs/ARCHITECTURE.md:39` lists `gateway/context_builder.py` as "Prompt/context assembly." After Phase 2, the canonical name is `gateway/context_assembler.py`. **Update the doc.**
- `docs/ARCHITECTURE.md:40` lists `gateway/memory_graph.py` as "Unified read path across memory stores." After Phase 2, the unified read path is `gateway/context_assembler.py` and `memory_graph.py` is internal. **Update.**
- `docs/ARCHITECTURE.md:42` lists `gateway/llm_client.py` as "Model routing and provider fallback." Stays accurate.
- `docs/PROJECT_STATUS.md` is updated at every phase gate.

### Documentation conflicts

- `docs/ARCHITECTURE.md:56` says "Phase B consolidates app-owned episodic state behind a single SQLite story. It does not migrate ChromaDB, mem0, imported raw knowledge, logs, or backups first." — this is **not** a conflict. The deepening program deepens Phase B's substrate, doesn't migrate out-of-scope stores.
- `docs/ARCHITECTURE.md:60-64` "Architecture Rules" are honored: "New context reads go through `memory_graph`" — *was* honored, becomes "go through `context_assembler`" after Phase 2.

### What this plan is NOT

- Not a rewrite. Every existing module continues to exist (in thinned form) until its tests prove the new shape works.
- Not a new storage system. No new databases, no new queues, no new cloud services. Forbidden by `docs/PROJECT_STATUS.md:14`.
- Not a new auth surface. No new middleware, no new tokens, no new headers.
- Not a UI change. The Next.js chat UI (`gateway/kitty-chat/`) is untouched. Routes may move or slim, but the wire shape of every endpoint stays the same.

---

## Risks

| Risk | Mitigation |
|---|---|
| Phase 1 substrate changes break callers outside the gateway. | Run the full test suite. Grep for `from gateway.todo_store`, `from gateway.journal_store`, etc. — every direct import outside the deepened module is a fail. |
| Phase 2 adapter shape change breaks 7 adapter classes that have subtly different fields. | The new `Item` dataclass is enforced at the type level; mypy/ruff catches any adapter that returns the old shape. |
| Phase 3 route slimming changes the wire shape of an endpoint the UI depends on. | Wrapper routes are exact-shape — no field added, removed, or renamed. UI integration tests in `gateway/kitty-chat/` catch drift. |
| Phase 4 dispatcher refactor breaks the 5 fallback chains. | Each provider has a fake adapter for tests; the fallback order is a list, not control flow. |
| Test count target (≥ 750) is missed. | Each phase has a test gate; the gate is pass/fail, not a target. |
| The user asks to abort after a phase. | Each phase is independently shippable; no later phase depends on earlier phase *content*. |

---

## Execution Order and Timeline

1. **Phase 0** — Foundation cleanup. ~half a day.
2. **Phase 1** — Storage substrate. ~2 days.
3. **Phase 2** — Read-path unification. ~3–4 days. **Buffer this one.** It's the highest-risk phase (touches 7 adapters, 9 enrichments, partial-result semantics, the `routes/search.py:26` shape, and the assembler interface). Budget for 4 days, not 2.
4. **Phase 3** — Route island extraction. ~2–3 days.
5. **Phase 4** — LLM client collapse. ~1 day.
6. **Phase 5** — Test surface tightening. ~1 day.

**Total: ~10–14 working days** (sub-friction G9: original 7–10 was optimistic). Each phase ends with a commit, a green test suite, and a `docs/PROJECT_STATUS.md` line.

The phases can also be parallelized across worktrees:
- Phase 0 alone, then merge.
- Phases 1 and 4 in parallel **if** the shared files between them are zero. Verification: `llm_client.py` reads `paths.py` (env vars), `http_client.py` (already async, no change in Phase 1), and `config.py` (env reads, not paths). Phase 1 doesn't touch any of these. **Safe to parallelize** (sub-friction G11).
- Phases 2 and 3 in parallel: Phase 2 touches `gateway/context_*.py` and `gateway/memory_graph.py`; Phase 3 touches `gateway/routes/*.py`. The only shared file is `routes/completions.py` and `routes/ask.py` (Phase 2 changes the call site; Phase 3 doesn't touch them). **Safe to parallelize with a careful merge** at the call site.
- Phase 5 last, after all the others land.

If parallelizing, use the `worktree` skill and run `/qg` between merges.

---

## Scope

### In scope

- 17 frictions listed above.
- Their dependent code paths.
- Test surface for each.
- Doc updates for `docs/ARCHITECTURE.md` and `docs/PROJECT_STATUS.md`.

### Out of scope

- New storage systems (forbidden by current focus).
- New auth surface (forbidden by `AGENTS.md:28`).
- UI changes (forbidden — wire shape stays the same).
- The `kitty-chat` Next.js app (`gateway/kitty-chat/`).
- MemPalace, ChromaDB, mem0 — Phase B explicitly excluded these.
- The `mempalace_adapter` subprocess path is not changed in this plan; only the JSONL write goes through `paths.py`.
- The `.claude/settings.local.json` review-required file is not part of this program.

---

## Decisions to Record

After approval, the following decisions deserve ADRs at `docs/adr/`:

1. **"StorageRouter is the seam, not a pass-through"** — recorded because future reviews will re-suggest deleting it.
2. **"Read path lives in `context_assembler`, not `context_builder`"** — recorded because the old name will keep appearing in older docs and search results.
3. **"No silent in-memory mocks in routes"** — recorded because the pattern has appeared in 6 places and will appear again.

ADRs are added *after* the phase lands, not before, so the rationale reflects what actually shipped.

---

## Open Questions for User

All three resolved 2026-06-24:

1. **Phase 1 vs Phase 4 ordering.** User confirmed: Phase 1 first, then Phase 4, each as a separate commit. Sequential, not parallel. The history stays clean and Phase 4 rebases safely on top of Phase 1's substrate work.
2. **Phase 2 façade length.** User confirmed: keep `context_builder.py` as a thin façade for one release. The 2 route-layer callers (`routes/completions.py`, `routes/ask.py`) keep their existing import. Delete the façade in the release *after* the assembler has proven stable — at that point a fast revert is no longer needed.
3. **The 6 `try/except → mock` routes.** User confirmed: none are load-bearing graceful-degradation features. All 6 are plain violations of the "Fail loud" prime directive. **Phase 3 removes every `try/except` that catches and returns fake data.** If the *intent* of a route was to surface "no data" to the UI, that logic moves into the domain module as `if not real_data: return []` — explicit, testable, and still respects domain rules. Each fix gets a flag in the Phase 3 PR description for easy review.

Route dedup (sub-friction G2) confirmed out of scope. Both routes stay; both slim to wrappers. Dedup is a separate roadmap item that needs UI changes.

The three must-fix changes (G1, G2, G5) from the Stage 3 grill are already applied to the spec above. ADRs will follow as the phases land.
