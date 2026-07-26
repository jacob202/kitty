# Kitty Master Architecture — Audit and Sequenced Implementation Plan

**Status:** planning input, not roadmap authority
**Authority:** `docs/AUTHORITY_MAP.md`; `docs/ROADMAP.md` remains the only active roadmap (ADR 0020)
**Audited at:** `8ceccc6`
**Hardware profile:** MacBook Air M1, 8 GB unified memory
**Input:** the amalgamated "KITTY_MASTER_ROADMAP" specification supplied in-session

---

## Verdict

The specification was written against a different codebase than the one in this
repository. Four of its assumptions are factually wrong about Kitty as it exists
at `8ceccc6`, three of its items are already built, and one of its central
hardware settings is self-contradictory on 8 GB.

What survives the audit is worth building — roughly 40% of the spec, sequenced
below. The rest should be dropped, retargeted, or deferred until the current
`docs/ROADMAP.md` Phase 1 (trust foundation, honest gates) is closed.

### Governance finding — read this first

`docs/ROADMAP.md` is the only active roadmap under ADR 0020 and CLAUDE.md
Non-Negotiable #8. A `KITTY_MASTER_ROADMAP.md` at repo root would be a second
competing planning authority. This document is therefore filed as a planning
input under `docs/plans/`. Nothing here is active work until it is dispositioned
into `docs/ROADMAP.md` or authored as packets.

Separately: `docs/ROADMAP.md` Phase 1 is currently "restore repository gates and
prove one trustworthy end-to-end loop." Every item in this spec is feature
expansion that competes with that. The plan below is ordered so that the cheap,
low-risk items can land inside Phase 1 without disturbing it, and the expensive
ones are explicitly gated behind it.

---

## Audit — spec claim vs. repository reality

| # | Spec item | Reality at `8ceccc6` | Disposition |
|---|---|---|---|
| 1.1 | "Unified SQLite-vec database" | The vector store is **ChromaDB** (`chromadb==1.5.8`), `PersistentClient` in `gateway/archivist.py:23`, plus `gateway/codebase_search.py`, `gateway/tutor.py`, `gateway/doctor.py:165`. `sqlite-vec` appears **only** in `docs/retired/` and `docs/archive/`. | **Migration, not addition.** Largest cost in the spec, presented as a bullet. Deferred to Phase 5, gated on evidence. |
| 1.2 | FTS5 exact-match index | **No FTS5 anywhere** in the codebase. | **Real gap, cheapest high-value win.** Phase 2. |
| 1.3 | SQLite tuning (WAL, temp_store, mmap, cache_size, `check_same_thread=False`, `timeout=30.0`) | ~60% done. `gateway/db.py:13-17` already sets `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`, `synchronous=NORMAL`. Missing: `temp_store`, `mmap_size`, `cache_size`. `check_same_thread=False` appears once, at `gateway/model_digest.py:22`, not in `db.connect()`. | **Partial.** Phase 1 — but see the threading correction below. |
| 1.4 | Huey cron summarization pipeline | **Huey is not a dependency and is not needed.** `gateway/cron.py` is already a runtime cron scheduler backed by `kitty.db` (`cron_schedules`) with an action registry and asyncio runner; `gateway/brief_scheduler.py` already schedules recurring work. `SESSION_LOG.md` exists only as `docs/archive/SESSION_LOG.md`; `MEMORY_INDEX.md` does not exist. | **Reject the broker; keep the pipeline.** Implement as a registered `cron.py` action against real files. Phase 4. |
| 2.1 | `llama3.2:1b` intent router ("traffic cop") | `gateway/domain_router.py` **already classifies** into `soul \| repair \| health \| research \| code` with a keyword scorer, consumed by `context_assembler` and the completion routes. Cost today: ~0 ms, 0 MB. | **Reject as specified.** A 1B model would add ~1.3 GB resident and a few hundred ms to replace something currently free. Measure first (Phase 3), add the model only as a low-confidence fallback if the data justifies it. |
| 2.2 | `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1` | Ollama is used **only for embeddings** today (`gateway/archivist.py:13`, `nomic-embed-text:latest`). Chat routing goes through LiteLLM → OpenRouter/AgentRouter (`gateway/llm_client.py`). | **`NUM_PARALLEL=1` correct. `MAX_LOADED_MODELS=1` is wrong if the router lands.** See hardware audit. |
| 2.3 | "Pydantic rigidity on the Flask backend" | **There is no Flask.** `requirements.txt` pins `fastapi==0.140.0` + `uvicorn`. Pydantic 2.12.5 is already a dependency and already in use (`gateway/models/`, `contracts/`). | **Retarget.** The gap is not validation — it is that no TypeScript types are generated from it. Phase 3. |
| 2.4 | Zero-cost local embeddings, `nomic-embed-text`, `keep_alive='0'` | `nomic-embed-text` **already shipped** (`gateway/archivist.py:13`). `keep_alive='0'` is **not set — and should not be.** See hardware audit. | **Mostly done; reject `keep_alive=0`.** |
| 2.5 | `@lru_cache` on embeddings, Flask-Compress, Next.js caching | `@lru_cache` **already on both** the collection handle (`archivist.py:18`) and query embeddings (`archivist.py:57`). Flask-Compress does not apply. The Next.js app has **zero** `revalidate` / `revalidateTag` / `force-cache` usage and a near-empty `next.config.ts`. | **lru_cache done. Compression → `GZipMiddleware`. Caching → real gap, Phase 3.** |
| 3.1 | Shadow-mode git staging on `kitty/staging-<patch_id>` branches | **Already exists, in a stronger form.** `gateway/builder_runner.py:115,154` provisions isolated git **worktrees** under `.worktrees/kittybuilder/<task_id>` with branch, run, PID and recovery tracking; `gateway/builder_attempt.py` runs commands inside them. | **Reject.** Worktrees beat branches here (no collision with Jacob's dirty tree). A second staging mechanism would also route around ADRs 0018/0021. |
| 3.2 | `@agent_guardrail` circuit breaker | Partial: `gateway/agent_runner.py` enforces per-preset `max_iterations` (2–5) inside `_run_agent_loop`, plus a poll timeout. No wall-clock kill, no typed exception, no uniform decorator. | **Real gap, small.** Phase 1 — must *wrap* the existing budget, not add a parallel one. |
| 3.3 | `EVALS.md` latency/usage tracking | Already exists: `docs/phases/EVALS.md`, `gateway/eval_runner.py`, `contracts/eval_result.py`, `data/eval_history.jsonl`, `POST /api/eval/run`. Missing: per-call latency, model id, and task category. | **Extend, don't build.** Phase 3 (it is the measurement substrate the router decision depends on). |
| 3.4 | `setup.sh` unified bootstrap | Does not exist. Equivalents already do: `scripts/preflight.sh`, `run.sh`, `./kitty up`, `Makefile`. | **Do not add a fourth entrypoint.** Add `./kitty bootstrap` delegating to preflight. Phase 1. |

---

## Hardware audit — 8 GB M1 Air

The three items the prompt named, plus the one that matters most.

### 1. `OLLAMA_MAX_LOADED_MODELS=1` contradicts the intent router

This is the sharpest finding. On 8 GB, roughly 5–5.5 GB is usable after macOS.
`llama3.2:1b` at q4 is ~1.3 GB resident; `nomic-embed-text` is ~0.3 GB. **Both fit
together comfortably.**

With `MAX_LOADED_MODELS=1`, every `classify → embed → classify` sequence forces an
unload and a cold reload of a model that was already in memory. That is ~1–2 s of
pure thrash per turn, on the exact path the router was supposed to make faster.
The setting protects against a spike that these two models cannot produce.

**Correction:** `OLLAMA_NUM_PARALLEL=1` (keep — it is the setting that actually
bounds concurrent-request memory). `OLLAMA_MAX_LOADED_MODELS=2` **if and only if**
the router ships. Until then `1` is correct, because only one model is loaded.

### 2. `keep_alive='0'` is a latency regression, not an optimization

`keep_alive='0'` flushes the model immediately after each call. Combined with
`gateway/archivist.py:16` — `QUERY_EMBED_TIMEOUT_SECONDS = 5` — a cold model load
on a query path with a 5 s budget is a plausible timeout, not a hypothetical one.
The `@lru_cache` at `archivist.py:57` hides this only for *repeated* query strings;
every novel query pays full cold-load cost.

**Correction:** `keep_alive='5m'` for the embedding model. It is 0.3 GB. Reserve
aggressive flushing for models above ~2 GB, and only under memory pressure.

### 3. `check_same_thread=False` is not a safety configuration

The spec lists it under "SQLite multi-threaded safety." It is the opposite: it
*disables* Python's guard against cross-thread connection use. It makes sharing
one connection across FastAPI's threadpool *possible*, not *safe* — SQLite
serializes at the C level, but Python-side cursor and transaction state is still
shared and will interleave.

**Correction:** open a connection per request or per thread (thread-local), keep
`check_same_thread` at its default `True`, and let WAL handle concurrent readers.
If a shared connection is genuinely required somewhere, it needs an explicit
`threading.Lock`, not a disabled check. The one existing use at
`gateway/model_digest.py:22` should be audited under this rule in Phase 1.

Also note `timeout=30.0` on `sqlite3.connect()` and `PRAGMA busy_timeout` are the
same knob. `gateway/db.py:15` already sets `busy_timeout=5000`. Pick one place —
the pragma — and raise it there if 5 s proves too tight. Do not set both to
different values.

### 4. Flask → Next.js cache invalidation has no counterpart today

There is no Flask, and the Next app does no caching at all, so there is nothing to
invalidate yet. The hook has to be built from both ends: a FastAPI-side emitter
and a Next route handler calling `revalidateTag`, authenticated with a shared
secret.

Scope constraint: most of Kitty's UI is live chat and live status. Caching those
is wrong. Only genuinely static reads — knowledge documents, project registry,
skill registry, packet listings — should be tagged.

### 5. Path inconsistency worth fixing while nearby

`gateway/archivist.py:11` writes Chroma to `data/knowledge_db`;
`gateway/doctor.py:164` health-checks `data/chromadb`. The doctor is checking a
directory the archivist never writes. This is a live false signal.

---

## Sequential implementation plan

Each phase is independently shippable and independently revertible. Acceptance is
a command that was actually run, per CLAUDE.md Non-Negotiable #2.

### Phase 0 — Disposition (no code)

Land this audit as a planning input. Decide, with Jacob, which phases enter
`docs/ROADMAP.md` and which are parked. Author packets only for what is approved.

- **Files:** `docs/plans/kitty-master-architecture-audit.md`, then `docs/ROADMAP.md`
- **Accepts when:** the approved subset appears in `docs/ROADMAP.md` with exit criteria
- **Blocks:** every phase below

### Phase 1 — SQLite correctness and execution bounds

Small, local, no new dependencies. Safe to land inside the current Phase 1 trust work.

1. **Complete the pragma set.** Add `temp_store=memory`, `mmap_size` (start at
   256 MB — on 8 GB, a 1 GB mmap competes with the page cache for no benefit at
   Kitty's data volume), and `cache_size=-16000` (16 MB, negative = KiB) to
   `gateway/db.py:13`. Leave `busy_timeout` as the single timeout knob.
2. **Audit `check_same_thread`.** Confirm `gateway/model_digest.py:22` is
   single-threaded or convert it to per-call connections. Do not propagate the flag
   into `db.connect()`.
3. **`@agent_guardrail` decorator.** New `gateway/guardrail.py`: typed
   `CircuitBreakerException`, wall-clock limit, iteration limit. `agent_runner`'s
   existing per-preset `max_iterations` becomes the value the decorator reads —
   one budget, one enforcement point.
4. **`./kitty bootstrap`.** Thin subcommand delegating to `scripts/preflight.sh`
   plus venv creation and `ollama pull nomic-embed-text`. No `setup.sh`.
5. **Fix the doctor's Chroma path** to `data/knowledge_db`.

- **Files:** `gateway/db.py`, `gateway/guardrail.py` (new), `gateway/agent_runner.py`, `gateway/doctor.py`, `kitty`, `tests/`
- **Accepts when:** `python3.12 -m pytest tests/ -q` passes at or above its current count; `./kitty doctor --json` reports `store:chromadb` PASS against the path the archivist actually writes; a new test proves `CircuitBreakerException` fires on both limits
- **Risk:** low. Reverting is one commit.

### Phase 2 — FTS5 lexical index

The highest value-per-line item in the whole spec, and it needs no new dependency
and no migration off Chroma.

Build an FTS5 table in `kitty.db` over the same chunks the archivist indexes, and
make retrieval hybrid: FTS5 for exact tokens (error codes, symbol names, function
signatures), Chroma for semantics, reciprocal-rank fusion to merge. Because it is a
sidecar, it delivers the exact-match win **independently of** any future sqlite-vec
decision — and it produces the retrieval-quality baseline that decision needs.

- **Files:** new migration under the `db.py` migrations dir, `gateway/archivist.py`, `gateway/memory_graph.py` (`KnowledgeAdapter`, `memory_graph.py:157`), `tests/`
- **Accepts when:** a query for a literal token that semantic search currently misses returns the correct chunk, demonstrated as a before/after in the test suite
- **Risk:** low-medium. Additive; the Chroma path is untouched and remains the fallback.

### Phase 3 — Measurement, then caching

Nothing after this phase should be decided without data, so this phase produces the data.

1. **Extend eval logging.** Add latency, model id, and task category to
   `gateway/eval_runner.py` and `data/eval_history.jsonl`; project a summary table
   into `docs/phases/EVALS.md`. This is the substrate the Phase 5 decision needs.
2. **Log `domain_router` decisions** with the eventual outcome, so its real accuracy
   becomes measurable rather than assumed.
3. **Pydantic → TypeScript generation.** A script emitting `.d.ts` from the existing
   Pydantic models into `gateway/kitty-chat/src/types/`, wired into `make ui-build`
   so drift fails the build.
4. **`GZipMiddleware`** on the FastAPI app (not Flask-Compress).
5. **Cache invalidation hook.** FastAPI emits on writes to cacheable resources; a
   Next route handler calls `revalidateTag`, shared-secret authenticated. Tag only
   static reads — knowledge, registries, packet listings. Never chat or status.

- **Files:** `gateway/eval_runner.py`, `gateway/domain_router.py`, `gateway/app.py`, `scripts/` (new generator), `gateway/kitty-chat/src/`, `docs/phases/EVALS.md`
- **Accepts when:** `make ui-test && make ui-build` passes with generated types committed; a write to a tagged resource demonstrably refreshes the corresponding Next page; `EVALS.md` shows latency rows from a real run
- **Risk:** medium. The cache hook is the piece most likely to produce stale-UI bugs — ship it tag-by-tag, not globally.

### Phase 4 — Memory summarization as a cron action

Only after Phase 3, because the token-budget claim needs measurement to be honest.

Register a `cron.py` action that reads real session artifacts (`.agent/session_logs/`,
not the archived `SESSION_LOG.md`), summarizes via a local model, appends structured
output to a memory index file, and truncates the source to a budget. **No Huey, no
broker process** — a second scheduler on an 8 GB box buys nothing that `cron.py`
does not already provide.

The truncation step deletes user data, so it lands behind an explicit dry-run mode
and a retained pre-truncation copy, per CLAUDE.md Non-Negotiable #4.

- **Files:** `gateway/cron.py`, new `gateway/session_summarizer.py`, `tests/`
- **Accepts when:** a dry run on real logs produces a reviewable diff and truncates nothing; the live run's before/after token counts are recorded
- **Risk:** medium-high — it is the only destructive item in the plan. Dry-run gate is mandatory.

### Phase 5 — sqlite-vec migration (gated, may never run)

Do not start this without Phase 2 and Phase 3 data in hand.

The case for migrating off Chroma is consolidation: one file, one backup, one
connection, joins between vectors and relational metadata. The case against is that
Chroma works today, is depended on by five modules, and the migration touches
retrieval quality — the thing hardest to regression-test.

**Entry gate — all three required:**
1. Phase 2's hybrid retrieval is live and its quality baseline is recorded in `EVALS.md`.
2. A measured problem with Chroma exists (memory, startup time, backup complexity) — with numbers.
3. A dual-read shadow period is planned: write both, read Chroma, compare, then flip.

If the gate is not met, close this out as "Chroma retained, decision recorded" in
`docs/DECISIONS.md`. That is a legitimate outcome, not a failure.

- **Files:** `gateway/archivist.py`, `gateway/codebase_search.py`, `gateway/tutor.py`, `gateway/memory_graph.py`, `gateway/doctor.py`, `requirements.txt`
- **Accepts when:** shadow-period comparison shows no retrieval-quality regression against the Phase 2 baseline
- **Risk:** high. Largest blast radius in the plan.

---

## Dropped, with reasons

| Item | Reason |
|---|---|
| `llama3.2:1b` traffic cop | Replaces a free keyword classifier with 1.3 GB and added latency. Revisit only if Phase 3 data shows `domain_router` misclassifying enough to matter. |
| Huey | `gateway/cron.py` already does this. A broker process on 8 GB is pure overhead. |
| `kitty/staging-<patch_id>` branches | `builder_runner` worktrees are strictly better and already governed by ADRs 0018/0021. |
| Flask-Compress / "Flask backend" | No Flask exists. `GZipMiddleware` is the FastAPI equivalent. |
| `setup.sh` | Fourth bootstrap entrypoint. Folded into `./kitty bootstrap`. |
| `OLLAMA_MAX_LOADED_MODELS=1` (as unconditional) | Correct only while one model is loaded; becomes a thrash source the moment a second one is. |
| `keep_alive='0'` | Latency regression against a 5 s query timeout, for 0.3 GB of savings. |
| `check_same_thread=False` in `db.connect()` | Disables a safety check without adding safety. Per-thread connections instead. |

---

## Open decisions for Jacob

1. **Does any of this enter `docs/ROADMAP.md` before Phase 1 trust work closes?**
   Recommendation: only audit Phase 1 and Phase 2. They are small, local, and
   improve the gates rather than competing with them.
2. **Is there a felt retrieval problem?** If exact-match search failures are not
   something actually experienced, Phase 2 drops from "highest value" to "speculative."
3. **Chroma: measured pain, or tidiness?** Phase 5 is a large migration. If the
   honest answer is tidiness, record the decision and close it.
