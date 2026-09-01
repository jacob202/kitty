# KF-WARM-01 — Predictive context warming actually runs and tells the truth

**Initiative:** `kitty-opens-the-doors-20260831-v1`
**Owner:** builder
**Depends on:** none — KT-AUTO-01 is already merged in this base via PR #724
**Free or paid:** free
**Base:** `origin/main` `546565246289e6730b518961de64b7f371013b3b`

## What Jacob can do after this
Hit likely next questions with a warm context cache without Kitty claiming a warm job succeeded when it persisted no warm result.

## Why this is the next thing
The original premise was partly wrong, and this packet records the correction. `gateway/prefetcher.py:207-222` already implements real predictive warming: it predicts likely queries and calls `memory_graph.unified_context(..., _record=False)` for uncached ones; `tests/test_prefetcher.py:74-92` proves the cache is populated.

The real gap is reachability and truth. `gateway/app.py:245-248` wraps `warm()`, and `272` registers `prefetch.warm`, but the startup schedule block at `306-310` never schedules that action. The wrapper also discards `warm()`'s integer result; `gateway/automation_actions.py:128-135` normalizes `None` to `completed`, so zero useful work is indistinguishable from a successful warm.

There is a second truth edge in `prefetcher.warm()`: line 219 increments `warmed` after `unified_context()` returns, but `memory_graph.unified_context()` may deliberately drop its cache write if `invalidate_all()` changed the cache generation while the compute was in flight. A warm counts only if the query is actually present in the cache afterward.

The cache TTL is exactly 300 seconds (`gateway/prefetcher.py:41`). Use an interval of exactly `5` minutes. A shorter interval is counterproductive with the current skip-if-cached algorithm: it can run just before expiry, do nothing, advance the cron cursor, then leave the cache cold until the following run.

MemoryGraph's public contract intentionally degrades individual stores and still returns a partial context. Do not reinterpret a partial or legitimately empty context as `source_unavailable`; that status is only for a run with no fresh persisted entry where at least one attempted `unified_context()` call actually raised.

The brief is not part of this defect. `gateway/app.py:306` already schedules `brief.refresh` every 15 minutes. Do not build a second brief cache here.

## Plan
1. In `gateway/prefetcher.py`, preserve the predictor/cache algorithm but return structured evidence: predicted count, already-cached count, attempted count, freshly persisted warm count, and raised-failure count.
2. Count a query as freshly warmed only when `get_cached(query)` confirms the cache entry exists after `unified_context()` returns. A generation-invalidated stale write is not success.
3. Keep failures isolated per predicted query. MemoryGraph's per-store degradation remains its own contract; only exceptions escaping `unified_context()` count as warm failures.
4. In `gateway/app.py`, make `_action_warm_prefetch` return an existing `automation_actions.ActionResult`: `completed` when at least one fresh cache entry persisted; `source_unavailable` when no fresh entry persisted and at least one attempted computation raised; `condition_false` when no fresh entry persisted and no computation raised (no predictions, all already cached, or a clean stale-generation discard). For the two non-completed statuses, populate `ActionResult.error` with a short plain-English reason so `automation_runs.finish_run()` persists why no warm result was produced; do not expose exception dumps as the user-facing reason.
5. Seed `cron.schedule("predictive context warm", "prefetch.warm", "interval", "5")` beside the existing startup schedules. Reuse PR #724's stable-name seed semantics; no new scheduler, daemon, or background loop.
6. Add RED tests in `tests/test_prefetcher.py` for structured evidence, already-warm/no-prediction behavior, the generation-invalidation race, and total raised failure. Add startup coverage in `tests/test_app_lifespan_hermetic.py` for exactly one five-minute warm schedule and preservation of an edited existing row.
7. Keep `brief.refresh` and its cache untouched.

PR #724 / KT-AUTO-01 is already present in this base. Preserve its morning-brief seed guard and cron identity semantics exactly.

## Not in scope
Changing prediction scoring, fingerprint contents, the 300-second cache TTL, `memory_graph.py`, brief generation, morning-brief timing, cron identity semantics, or any frontend file. No paid/model generation is added; this remains retrieval/cache work. This packet creates no new files.

## Verification
**Tier 1 — mechanical.** `python -m pytest -q tests/test_prefetcher.py tests/test_automation_actions.py tests/test_app_lifespan_hermetic.py tests/test_cron.py` and `python -m ruff check gateway/app.py gateway/prefetcher.py tests/test_prefetcher.py tests/test_app_lifespan_hermetic.py`. Observed at this exact base: the existing pytest gate is green (`70 passed in 2.88s`) and Ruff is clean, because it does not yet assert the missing schedule, persisted-warm truth, or generation-race behavior. That green baseline is **not** acceptance proof. Before implementation the worker must add the tests in Plan step 6, run this same pytest command, record the behavioral failures, then make the implementation pass them. Keep the existing `tests/test_cron.py` PR #724 assertions unchanged.

**Tier 2 — running app.** None; this packet changes no user-visible surface.

**Tier 3 — product acceptance.** None; later Home/why-not surfaces make the durable run evidence visible.

## Stop condition
If the five-minute schedule cannot be added without changing PR #724's stable-name seed semantics, or if truthful warm evidence requires changing `memory_graph.py`, stop and report the mismatch instead of widening the packet.

## Recovery
No irreversible side effects are permitted. Tests use isolated stores; do not run a real scheduled warm against user data as proof. A failed attempt can be reverted and restarted after the automation base is current.
