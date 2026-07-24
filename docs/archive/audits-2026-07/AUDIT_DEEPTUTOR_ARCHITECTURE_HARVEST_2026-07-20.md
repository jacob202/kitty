# DeepTutor Architecture Harvest for Kitty

**Date:** 2026-07-20
**Status:** Research-only audit — no Kitty code modified
**Scope:** DeepTutor v1.5.2 vs. Kitty (main, 77a1389)

---

## Repository Identifiers

| Item | Value |
|---|---|
| **Kitty branch** | `main` |
| **Kitty HEAD SHA** | `77a1389cf907743faf5ab7693eb443205d17d41d` |
| **Kitty origin/main SHA** | `77a1389cf907743faf5ab7693eb443205d17d41d` |
| **DeepTutor remote** | `https://github.com/HKUDS/DeepTutor` |
| **DeepTutor inspected SHA** | `b728354863540466f5410bec3530eb55a9fe0edc` (v1.5.2) |
| **DeepTutor license** | Apache 2.0 (HKU Data Intelligence Lab) |

---

## 1. Executive Verdict

**DeepTutor does not materially change Kitty's roadmap.**

DeepTutor is a mature, well-engineered multi-user learning platform with sophisticated RAG, partner/persona systems, and a tutoring engine. However, its architecture is fundamentally oriented around a different product: a multi-user educational SaaS with web UI, partner chat companions, and knowledge-base-centric learning.

Kitty's core product identity — local-first single-user personal AI operating layer with the resume loop, Builder execution control plane, and privacy boundary enforcement — is architecturally incompatible with DeepTutor's design in almost every subsystem. The one exception is **tutoring/mastery**, where DeepTutor has a proven implementation that Kitty's nascent `tutor-design.md` could learn from.

**Bottom line:** DeepTutor is a valuable *reference* for specific patterns (atomic writes, embedding versioning, capability-based access control, spaced repetition scheduling), but Kitty should not adopt or adapt its architecture wholesale. The cost of integration would exceed the benefit in every case where Kitty already has an equivalent.

---

## 2. Adopt / Adapt / Study / Reject Matrix

| Finding | Disposition | Rationale |
|---|---|---|
| Atomic JSON writes (`file_io.py`) | **Study** | Kitty already uses JSONL and SQLite; pattern useful for future `storage_router` writes |
| Embedding signature/versioning (`embedding_signature.py`, `index_versioning.py`) | **Study** | Valuable if Kitty ever re-indexes ChromaDB; currently not needed |
| Spaced repetition scheduler (`scheduler.py`) | **Adapt** | Kitty's `tutor-design.md` has simple spacing; DeepTutor's type-specific intervals are proven |
| Mastery gate system (`mastery.py`, `policy.py`) | **Study** | Kitty's tutor is vocabulary-first; mastery gates add complexity that may not fit |
| Label-driven agentic loop (`loop.py`) | **Reject** | Kitty's agent loop is simpler; DeepTutor's label protocol is over-engineered for Kitty's use case |
| Two-layer plugin model (Tools + Capabilities) | **Reject** | Kitty has skills + agent presets; this would be a rewrite |
| Multi-user grants/partner isolation | **Already Covered** | Kitty is single-user; this architecture has no applicability |
| RAG pipeline abstraction (`RAGPipeline` Protocol) | **Already Covered** | Kitty has `memory_graph.StoreAdapter`; different but equivalent |
| Skill hub with import security | **Study** | Kitty's skill system is simpler; import security patterns (zip-slip, suffix whitelist) are good reference |
| Three-layer memory (L1/L2/L3) | **Reject** | Kitty's memory_graph + memory_palace + journal is different architecture; consolidation pipeline adds complexity without need |
| ChatOrchestrator routing | **Already Covered** | Kitty's `context_assembler` + `llm_client` serve this role |
| Document validation/security | **Study** | Kitty's knowledge upload could benefit from magic-byte validation and extension whitelisting |
| Grant secret rejection (`validate_grant`) | **Study** | Good pattern for any future grant/permission system |
| Index cache freshness (`_freshness_token`) | **Study** | Useful for ChromaDB staleness detection |
| Partner memory split model | **Reject** | Kitty is single-user; no partner concept |
| Persona service | **Already Covered** | Kitty has `config/SOUL.md` + `prompts.py`; DeepTutor's is more featureful but unnecessary |
| Quiz/assessment generation | **Study** | Kitty's tutor-design mentions check-in questions; DeepTutor's grading pipeline is more mature |
| Learning progress persistence | **Study** | Per-book JSON with CAS lock; useful if Kitty's tutor grows |
| Circuit breaker utility | **Already Covered** | Kitty's `llm_client` has tenacity retry; different mechanism, same goal |
| Web search integration | **Already Covered** | Kitty has web_search in skills |
| Code execution sandbox | **Reject** | Kitty doesn't need sandboxed Python execution |
| StreamBus/StreamEvent | **Already Covered** | Kitty's `agent_runner` records steps differently; streaming is UI-level |
| Document extraction pipeline | **Study** | Kitty's knowledge ingestion is simpler; extraction patterns are reference |
| File type routing | **Study** | Kitty's knowledge upload could use magic-byte classification |
| Observability/audit logging | **Already Covered** | Kitty has token_log and storage telemetry |

---

## 3. Subsystem-by-Subsystem Comparison

### 3.1 Agent Loop

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **Core loop** | Label-driven iteration with `LoopHost` protocol hooks (`loop.py:173`) | OBSERVE→ORIENT→DECIDE→ACT→VERIFY→LEARN phases (`agent_runner.py:54`) | Different: DeepTutor is label-driven (LLM emits labels), Kitty is phase-driven (Algorithm reasoning). DeepTutor's is more flexible but more complex. |
| **Tool dispatch** | Parallel via `asyncio.gather`, max 8 concurrent (`tool_dispatch.py:41`) | Sequential LLM calls, no parallel tool dispatch | DeepTutor is more mature; Kitty doesn't need parallel dispatch for single-user |
| **Protocol violation handling** | Emits retry notice, appends repair message to conversation (`loop.py:336`) | No equivalent; agent errors are logged and session marked failed | Study-worthy: repair messages help LLM self-correct |
| **Context window guard** | `host.guard_context_window()` called each iteration (`loop.py:219`) | No explicit guard; relies on token caps in `memory_graph` | Study-worthy: prevents context overflow in long agent runs |
| **Streaming** | StreamBus async fan-out to all consumers (`stream_bus.py`) | No streaming; step-by-step recording to autonomy_state.db | DeepTutor's is more real-time; Kitty's is adequate for background agents |
| **Cancellation** | `resolve_pause`/`force_finalize` via LoopHost (`loop.py:345`) | `stop()` cancels asyncio task + marks DB cancelled (`agent_runner.py:459`) | Equivalent: different mechanisms, same outcome |

### 3.2 Memory

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **Architecture** | Three-layer: L1 raw events (JSONL) → L2 per-surface summaries (Markdown) → L3 cross-surface synthesis (Markdown) | Unified read path via `memory_graph.py` with adapters for memory, knowledge, journal, traces, todos, inbox, memory_palace | Different architectures; Kitty's is simpler and purpose-built |
| **Consolidation** | Four modes: update, audit, dedup, merge with atomic ops (`AddOp`, `EditOp`, `DeleteOp`) | No consolidation pipeline; stores are append-only or direct SQLite | Study-worthy if Kitty's memory grows; currently unnecessary |
| **Provenance** | Footnote citations L3→L2→L1, ULID-based entry IDs | `Item.source` enum traces to which store adapter returned it | Equivalent for different purposes |
| **Retrieval** | L3 concatenated for chat context with token budgets | `memory_graph.search_all()` with per-store timeout and token cap (`CONTEXT_TOKEN_CAP=1200`) | Kitty's is simpler but sufficient |
| **User isolation** | `PathService` + ContextVars, per-user workspace roots | Single-user; no isolation needed | Not applicable |
| **Conflict handling** | Consolidation dedup with seen-id diffs | No conflicts; single-user append stores | Not applicable |

### 3.3 Knowledge / RAG

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **Pipeline abstraction** | `RAGPipeline` Protocol with `initialize()`, `add_documents()`, `search()`, `delete()` | `StoreAdapter` ABC with `name` + `fetch()` | Equivalent interfaces |
| **Multiple backends** | 5 providers: LlamaIndex, PageIndex, GraphRAG, LightRAG, LightRAG-server (`factory.py:35`) | ChromaDB + mem0 (via adapters in `memory_graph.py`) | DeepTutor is more flexible; Kitty has fewer but sufficient |
| **Embedding versioning** | Signature-based version dirs with SHA-256 hash, backward-compatible migration (`index_versioning.py`) | No versioning; ChromaDB manages its own index | Study-worthy if Kitty re-indexes |
| **Chunking** | SentenceSplitter (LlamaIndex), TeX-aware chunker, memory consolidator chunker | ChromaDB default chunking | DeepTutor is more sophisticated |
| **Hybrid retrieval** | Vector + BM25 with reciprocal rank fusion (`retrievers.py:119`) | ChromaDB vector only | Study-worthy if retrieval quality matters |
| **Stale index detection** | Embedding mismatch flags, provider migration detection, linked folder change detection | No equivalent | Study-worthy for ChromaDB staleness |
| **Document ingestion** | `FileTypeRouter` with 100+ extensions, magic-byte sniffing, multi-encoding fallback | Simpler file loading | Study-worthy for validation patterns |
| **Atomic writes** | `atomic_write_json()` with tempfile + fsync + replace | SQLite handles atomicity; JSONL is append-only | Kitty's approach is simpler |
| **Source citations** | `CitationManager` with footnote chain, APA formatting | No citation system | Not needed for Kitty's use case |
| **Crash recovery** | Orphan prune grace period, status recovery, failed version cleanup | SQLite transactions; no crash recovery needed for JSONL | Not applicable |

### 3.4 Skills

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **Format** | `SKILL.md` with YAML frontmatter + optional `references/` dir | `SKILL.md` with YAML frontmatter in `.agents/skills/` | Same convention |
| **Discovery** | System-prompt manifest, `read_skill` on-demand loading | `skill_registry.discover()` scans disk, `invoke()` renders prompt | Equivalent |
| **Hub/import** | Hub ecosystem with verify→fetch→install pipeline, zip-slip guards, suffix whitelist, symlink abort, `always:` stripping | No hub; skills are local files only | Study import security patterns if Kitty ever adds skill sharing |
| **Version locking** | `.hub-lock.json` with provenance (hub, slug, version, verdict, installed_at) | No versioning | Not needed for local skills |
| **Availability gates** | `requires.bins`, `requires.env`, `requires.sandbox` | No gates | Not needed currently |
| **Dynamic loading** | `DeferredToolLoader` for progressive schema loading | Skills loaded at startup, cached in memory | DeepTutor is more dynamic; Kitty's is simpler |
| **Failure isolation** | Tool/capability load failures logged + continue; never crash the system | Skills are static; no dynamic failure possible | Not applicable |

### 3.5 Persistent Companions / Partners

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **Partner system** | Full lifecycle: start/stop/destroy, channel managers, session persistence, auto-start on boot, soul templates | No partner concept; Kitty is single-user | Not applicable |
| **Partner memory** | Split model: read owner's L3 + own L3; write-only to own workspace | No partner memory | Not applicable |
| **Persona service** | `PERSONA.md` files, CRUD API, exactly one active per turn, admin-authored presets | `config/SOUL.md` for voice/persona | Kitty's is simpler; DeepTutor's is more featureful but unnecessary |
| **Cross-persona leakage** | Partner memory tools explicitly scoped via PathService; tests verify isolation | Not applicable | Not applicable |

### 3.6 Tutoring / Mastery

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **Mastery tracking** | `compute_mastery()` with recency-weighted accuracy (0.5/0.7/0.85/0.95/1.0 weights), caps at 0.5 for 1 attempt (`mastery.py`) | Simple 1-3 confidence ratings with fixed intervals (1→3d, 2→1d, 3→next session) (`tutor-design.md:51`) | Study: DeepTutor's is more sophisticated; Kitty's is simpler and may be sufficient |
| **Spaced repetition** | Type-specific intervals: MEMORY [0,1,3,7,14,30,60], CONCEPT [3,7,14,30], PROCEDURE [3,7,14], DESIGN [14,28] (`scheduler.py:26`) | Fixed intervals regardless of type | Study: type-specific intervals are proven |
| **Learning stages** | 7-stage pipeline: DIAGNOSTIC→EXPLAIN→FEYNMAN_CHECK→PRACTICE→ERROR_DIAGNOSIS→REVIEW→COMPLETED | None; single ask/rate loop | Study: stages add structure but complexity |
| **Grading** | Deterministic: choice (exact match), short (≥0.85 similarity), open (≥0.6 keyword overlap) (`grading.py`) | No grading; user self-rates | Study: deterministic grading removes LLM variance |
| **Quiz generation** | Block-level from chapter context, configurable types/difficulty (`quiz.py`) | None | Study if Kitty's tutor grows |
| **Knowledge types** | MEMORY, CONCEPT, PROCEDURE, DESIGN with per-type mastery gates (`policy.py:34-42`) | None | Study: types enable targeted review |
| **Progress persistence** | Per-book JSON with CAS lock, version bump, path traversal guard (`storage.py`) | SQLite `vocabulary_terms` + `user_confidence_logs` | Kitty's is simpler; DeepTutor's is more robust |
| **Error diagnosis** | Classifies errors as metacognitive (blank) vs application (`grading.py:56`) | None | Study: error classification enables targeted remediation |

### 3.7 CLI / API

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **CLI framework** | Typer with sub-apps (partner, chat, kb, skill, plugin) | `./kitty` shell script + Python entry points | Different: DeepTutor is more structured |
| **Structured output** | `--format json` emits JSON envelope | `--json` flags on specific commands | Equivalent |
| **WebSocket** | Unified `/api/v1/ws` endpoint with StreamBus fan-out | HTTP-only; no WebSocket | DeepTutor is more real-time |
| **API routers** | 10+ routers (auth, skills, tools, plugins, knowledge, WS, agent_config, partners, settings) | Thin routes in `gateway/routes/` | Different scope |
| **Machine-readable CLI** | `deeptutor run <capability>` with JSON output | `./kitty builder ... --json` for Builder commands | Equivalent patterns |
| **Background jobs** | asyncio tasks for agents, partner runners | `agent_runner.spawn()` with background asyncio tasks | Equivalent |

### 3.8 Reliability / Security

| Aspect | DeepTutor | Kitty | Assessment |
|---|---|---|---|
| **Fail loud** | Error results returned to LLM; exceptions logged + surfaced | "Fail loud, never mask" constitution article | Same principle |
| **Privacy boundary** | No explicit privacy tiers; auth-based isolation | `PRIVACY_LOCAL_ONLY` content classes, `PrivacyBoundaryError` (`llm_client.py:36-59`) | Kitty is stronger: code-enforced privacy tiers |
| **Input validation** | Document validator (size, extension, MIME, filename sanitization), Pydantic models, username regex | Simpler validation | Study document validation patterns |
| **Secret handling** | JWT auto-generated, bcrypt hashing, hub tokens with chmod 0600 | `.env` files, no JWT | Different: Kitty is local-first |
| **Concurrency** | RLock in ConfigManager, atomic writes, thread-safe user store | SQLite transactions, asyncio tasks | Equivalent |
| **Migration strategy** | Grant v1→v2 normalization, auth user format migration, legacy KB layout detection | SQLite migrations in `gateway/db.py` | Equivalent |
| **Prompt injection defense** | `always:` stripping on import, suffix whitelist, symlink abort | No skill import system; no injection vector | Not applicable |
| **Adversarial tests** | `test_resource_isolation.py`, `test_pocketbase_isolation.py`, `test_tool_access.py` | `tests/test_llm_privacy_boundary.py` | Kitty's coverage is narrower but focused on its actual risks |

---

## 4. "Do Not Reinvent" List

Concepts DeepTutor has proven that Kitty should reference if building similar functionality:

1. **Atomic JSON writes** — `tempfile.NamedTemporaryFile` → `fsync` → `Path.replace()` pattern (`deeptutor/services/file_io.py:12-38`). Use when Kitty needs crash-safe JSON writes outside SQLite.

2. **Embedding signature versioning** — SHA-256 hash of (binding, model, dimension, base_url) as index version key (`deeptutor/services/rag/embedding_signature.py:26`). Reference if Kitty re-indexes ChromaDB.

3. **Type-specific spaced repetition intervals** — Different knowledge types (memory/concept/procedure/design) get different review schedules (`deeptutor/learning/scheduler.py:26`). Reference for Kitty tutor expansion.

4. **Deterministic grading** — Exact match for choices, similarity threshold for short answers, keyword overlap for open-ended (`deeptutor/learning/grading.py`). Reference if Kitty adds quiz grading.

5. **Document validation pipeline** — Magic-byte sniffing, extension whitelist, MIME validation, filename sanitization, size budgets (`deeptutor/utils/document_validator.py`). Reference for knowledge upload hardening.

6. **Import security patterns** — Zip-slip defense, suffix whitelist, symlink abort, `always:` stripping for imported skills (`deeptutor/services/skill/hub.py`, `service.py`). Reference if Kitty ever adds skill sharing.

7. **Grant secret rejection** — `validate_grant()` rejects `api_key`, `secret`, `password`, `token`, `path`, `base_url` fields (`deeptutor/multi_user/grants.py:107-125`). Reference for any future permission system.

8. **Orphan prune grace period** — 60-second grace before `list_knowledge_bases()` deletes directories that haven't been created yet (`deeptutor/knowledge/manager.py:52`). Reference for any auto-discovery system.

---

## 5. "Do Not Import" List

DeepTutor architecture that would conflict with Kitty or create duplicate systems:

1. **Two-layer plugin model (Tools + Capabilities)** — DeepTutor's `ToolRegistry` + `CapabilityRegistry` with `BaseTool` ABC and `BaseCapability` ABC would conflict with Kitty's existing `skill_registry` + `agent_runner` + `llm_client` architecture. Importing this would be a rewrite, not a borrow.

2. **Three-layer memory (L1/L2/L3)** — DeepTutor's raw events → per-surface summaries → cross-surface synthesis pipeline is a different architecture from Kitty's `memory_graph` adapters. Importing would create duplicate memory systems.

3. **ChatOrchestrator** — DeepTutor's unified routing entry point conflicts with Kitty's `context_assembler` → `llm_client` pipeline. Different design, not upgradeable.

4. **Multi-user grants/partner/persona isolation** — DeepTutor's entire `multi_user/` package is irrelevant to Kitty's single-user design. Importing any of it adds complexity without value.

5. **StreamBus/StreamEvent** — DeepTutor's async fan-out streaming conflicts with Kitty's step-recording approach. Different real-time requirements.

6. **Label-driven agentic loop** — DeepTutor's label protocol (`LabelProtocol`, `LoopHost`) is more complex than Kitty's Algorithm phases. Importing would replace a working system with a more abstract one.

7. **Knowledge-base lifecycle management** — DeepTutor's `KnowledgeBaseInitializer`, `DocumentAdder`, status tracking, and progress broadcasting are SaaS-oriented. Kitty's simpler ChromaDB + mem0 approach is sufficient.

8. **Session persistence layer** — DeepTutor's `UnifiedSessionManager` with SQLite + PocketBase backends conflicts with Kitty's `autonomy_state.db` and `db.py` stores.

---

## 6. Top Ten Findings

### Finding 1: Atomic Write Pattern
- **DeepTutor:** `deeptutor/services/file_io.py:12-38` — `atomic_write_json()` and `atomic_write_text()`
- **Kitty affected:** Any future JSON file writes (currently all atomic via SQLite or append-only JSONL)
- **Value:** Proven crash-safe write pattern; reference for `storage_router` if it ever writes JSON files
- **Disposition:** Study

### Finding 2: Embedding Signature Versioning
- **DeepTutor:** `deeptutor/services/rag/embedding_signature.py:26`, `deeptutor/services/rag/index_versioning.py:47-315`
- **Kitty affected:** `gateway/memory_graph.py` ChromaDB adapter
- **Value:** Prevents stale embedding mismatch; automatic migration detection
- **Disposition:** Study (needed only if Kitty re-indexes ChromaDB)

### Finding 3: Type-Specific Spaced Repetition
- **DeepTutor:** `deeptutor/learning/scheduler.py:26` — MEMORY [0,1,3,7,14,30,60], CONCEPT [3,7,14,30], PROCEDURE [3,7,14], DESIGN [14,28]
- **Kitty affected:** `gateway/tutor.py` (future), `docs/tutor-design.md`
- **Value:** Proven type-specific intervals; Kitty's fixed 1/3-day intervals are simpler but less effective
- **Disposition:** Adapt

### Finding 4: Deterministic Grading
- **DeepTutor:** `deeptutor/learning/grading.py:1-64` — choice (exact), short (≥0.85 similarity), open (≥0.6 keyword overlap)
- **Kitty affected:** `gateway/tutor.py` (future)
- **Value:** Removes LLM variance from grading; deterministic and testable
- **Disposition:** Study

### Finding 5: Document Validation Pipeline
- **DeepTutor:** `deeptutor/utils/document_validator.py:58` — magic bytes, extension whitelist, MIME, filename sanitization, size cap
- **Kitty affected:** Knowledge upload paths
- **Value:** Prevents extension spoofing and malicious uploads
- **Disposition:** Study

### Finding 6: Protocol Violation Repair Messages
- **DeepTutor:** `deeptutor/core/agentic/loop.py:336` — `_protocol_violation()` emits retry notice, appends repair message to conversation
- **Kitty affected:** `gateway/agent_runner.py`
- **Value:** Helps LLM self-correct when it emits unexpected output format
- **Disposition:** Study

### Finding 7: Import Security Patterns
- **DeepTutor:** `deeptutor/services/skill/hub.py:175-218`, `deeptutor/services/skill/service.py:723-760` — zip-slip defense, suffix whitelist, symlink abort, `always:` stripping
- **Kitty affected:** `gateway/skill_registry.py` (if skill sharing ever added)
- **Value:** Proven defense against malicious skill imports
- **Disposition:** Study

### Finding 8: Grant Secret Rejection
- **DeepTutor:** `deeptutor/multi_user/grants.py:107-125` — `validate_grant()` rejects api_key, secret, password, token, path, base_url fields
- **Kitty affected:** Any future permission/grant system
- **Value:** Prevents accidental secret leakage through grant data
- **Disposition:** Study

### Finding 9: Context Window Guard
- **DeepTutor:** `deeptutor/core/agentic/loop.py:219` — `host.guard_context_window()` called each iteration before LLM call
- **Kitty affected:** `gateway/agent_runner.py`
- **Value:** Prevents context overflow in long agent runs
- **Disposition:** Study

### Finding 10: Orphan Prune Grace Period
- **DeepTutor:** `deeptutor/knowledge/manager.py:52` — `_ORPHAN_PRUNE_GRACE_SECONDS = 60` prevents deletion of in-flight directories
- **Kitty affected:** Any auto-discovery system (e.g., skill discovery, KB listing)
- **Value:** Prevents race condition between directory creation and listing
- **Disposition:** Study

---

## 7. Proposed Implementation Sequence

### Packet DTH-01: Spaced Repetition Enhancement
- **User value:** Kitty tutor learns from DeepTutor's proven type-specific intervals
- **Kitty files affected:** `gateway/tutor.py` (new), `tests/test_tutor.py`
- **DeepTutor references:** `deeptutor/learning/scheduler.py:26`, `deeptutor/learning/policy.py:34-42`
- **Scope:** Add knowledge-type awareness to Kitty's existing tutor spaced repetition; MEMORY/CONCEPT/PROCEDURE types with different interval sequences
- **Acceptance criteria:** Existing tutor tests pass; new tests verify type-specific scheduling; no new dependencies
- **Required tests:** Unit tests for each knowledge type's interval sequence; edge case: single attempt caps
- **Dependencies:** None
- **Risk level:** Low
- **Recommended model tier:** T0 (free worker)
- **Free worker capable:** Yes
- **ADR required:** No (extends existing tutor-design.md)

### Packet DTH-02: Document Validation Hardening
- **User value:** Knowledge upload rejects extension spoofing and malicious files
- **Kitty files affected:** Knowledge upload route(s), new `gateway/document_validator.py`
- **DeepTutor references:** `deeptutor/utils/document_validator.py:58-91`
- **Scope:** Add magic-byte validation, extension whitelist, and filename sanitization to knowledge upload paths
- **Acceptance criteria:** Spoofed extensions rejected; valid files pass; no new dependencies
- **Required tests:** Test spoofed PDF (actually .exe), test valid PDF, test path traversal in filename
- **Dependencies:** None
- **Risk level:** Low
- **Recommended model tier:** T0
- **Free worker capable:** Yes
- **ADR required:** No

### Packet DTH-03: Deterministic Grading for Tutor
- **User value:** Tutor check-in questions graded deterministically, not by LLM variance
- **Kitty files affected:** `gateway/tutor.py` (new grading function), `tests/test_tutor.py`
- **DeepTutor references:** `deeptutor/learning/grading.py:1-64`
- **Scope:** Add deterministic grading for choice (exact match), short answer (similarity threshold), and open-ended (keyword overlap) question types
- **Acceptance criteria:** Existing tutor tests pass; new tests verify grading accuracy; no LLM calls for grading
- **Required tests:** Test exact match, test near-match above threshold, test below threshold, test blank answer
- **Dependencies:** None
- **Risk level:** Low
- **Recommended model tier:** T0
- **Free worker capable:** Yes
- **ADR required:** No

---

## 8. Recommended First Packet

**Packet DTH-01: Spaced Repetition Enhancement** is the highest-value first step because:

1. Kitty already has `docs/tutor-design.md` specifying a tutor system with spaced repetition
2. DeepTutor's scheduler is proven and small (~100 lines)
3. Adapting it requires no new dependencies
4. It directly improves the tutor product that Kitty is building
5. It's low-risk, independently reviewable, and free-worker capable

**Scope:** Add a `KnowledgeType` enum and type-specific interval sequences to Kitty's tutor module. Map question types to knowledge types. Update the review queue builder to use type-specific intervals instead of fixed 1/3-day spacing.

**Not in scope:** Mastery gates, learning stages, quiz generation, error diagnosis — those are deeper features that can follow if the tutor product proves valuable.

---

## 9. Documentation Updates Needed

1. **`docs/tutor-design.md`** — Update §4 Architecture to reference type-specific spaced repetition; add knowledge type mapping
2. **`docs/AUDIT_DEEPTUTOR_ARCHITECTURE_HARVEST_2026-07-20.md`** — This file (new)
3. **`docs/DECISIONS.md`** — No new ADR needed; findings are reference-only

---

## 10. Decisions Requiring Jacob's Judgment

1. **Should Kitty's tutor adopt type-specific spaced repetition?** DeepTutor's evidence suggests it's more effective, but Kitty's simple 1/3-day system may be sufficient for v1. Decision: adapt now or defer until tutor usage data exists.

2. **Should Kitty add document validation to knowledge upload?** Currently no validation beyond what ChromaDB provides. DeepTutor's pattern is proven but adds code. Decision: harden now or defer until knowledge upload is a real product surface.

3. **Should Kitty ever add skill sharing/hub?** DeepTutor's import security patterns are excellent reference, but Kitty currently has no skill sharing. Decision: defer entirely until skill sharing is a product requirement.

---

*This audit was conducted read-only. No Kitty code was modified. DeepTutor was cloned to `/Users/jacobbrizinski/Projects/DeepTutor` as a reference.*
