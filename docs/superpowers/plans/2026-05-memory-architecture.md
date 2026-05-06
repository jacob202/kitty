# Memory Architecture Foundation Implementation Plan

> For agentic workers: required sub-skill is `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Implement task-by-task with validation checkpoints.

Goal: implement the first production-safe memory foundation (`Source Ledger + Memory Router + Quarantine Queue`) without backend migration.

Architecture: keep current memory stores live, introduce a routing contract and candidate lifecycle, and make durable-memory promotion explicit and auditable. Retrieval backends remain adapters behind the router.

Tech Stack: Python 3.12, Flask app runtime, existing SQLite stores, existing LightRAG/Chroma integrations, pytest.

---

### Task 1: Source Ledger Schema

Files:
- Create: `src/memory/source_ledger.py`
- Modify: `src/core/db_config.py`
- Test: `tests/memory/test_source_ledger.py`

Steps:
- [x] Add source-ledger SQLite schema for `raw_source`, `memory_candidates`, `memory_promotions`, `memory_conflicts`.
- [x] Include provenance fields: `source_path`, `source_type`, `source_timestamp`, `chunk_id`, `snippet_hash`.
- [x] Add confidence and lifecycle fields: `confidence`, `state` (`candidate`, `quarantined`, `durable`, `retired`).
- [x] Wire DB path in `DB_PATHS` as `source_ledger`.
- [x] Add tests for create, insert, promote, quarantine, retire, and soft-delete behavior.

Validation:
- `venv/bin/python -m pytest tests/memory/test_source_ledger.py -q --tb=short`

---

### Task 2: Memory Router Contract

Files:
- Create: `src/memory/storage_router.py`
- Modify: `src/services/context_service.py`
- Test: `tests/memory/test_storage_router.py`

Steps:
- [x] Define router API for ingest/query/promote/quarantine/retire operations.
- [x] Route knowledge retrieval with explicit fallback policy and source logging.
- [x] Move direct store decision logic out of callers into router.
- [x] Keep runtime behavior backward-compatible for existing routes.
- [x] Add tests that wrong-store writes are blocked and recorded.

Validation:
- `venv/bin/python -m pytest tests/memory/test_storage_router.py -q --tb=short`

---

### Task 3: Quarantine Queue

Files:
- Create: `src/memory/quarantine_queue.py`
- Test: `tests/memory/test_quarantine_queue.py`

Steps:
- [x] Add queue operations for stage/review/approve/reject/retire.
- [x] Require source evidence for promotion to durable.
- [x] Add conflict marker support for contradictory candidates.
- [x] Ensure personal/sensitive categories default to quarantine.
- [x] Add tests for queue transitions and policy enforcement.

Validation:
- `venv/bin/python -m pytest tests/memory/test_quarantine_queue.py -q --tb=short`

---

### Task 4: Retrieval Reliability Regression

Files:
- Test: `tests/services/test_context_service_retrieval_domain_filter.py`
- Modify: `src/services/context_service.py` (only if needed to pass regression)

Steps:
- [x] Add regression test showing current `domain='general'` retrieval gap from seeded docs.
- [x] Add minimal fix or documented fallback behavior so retrieval does not silently return empty when relevant data exists.
- [x] Verify behavior for `domain=None`, `domain='general'`, and one domain-specific path.

Validation:
- `venv/bin/python -m pytest tests/services/test_context_service_retrieval_domain_filter.py -q --tb=short`

---

### Task 5: Adapter Interface for Backend Swap

Files:
- Create: `src/memory/retrieval_adapter.py`
- Modify: `src/services/context_service.py` or `src/memory/storage_router.py`
- Test: `tests/memory/test_retrieval_adapter_contract.py`

Steps:
- [x] Define a minimal retrieval adapter contract with provenance-aware results.
- [x] Implement current-stack adapter as baseline.
- [x] Stub LanceDB-style adapter behind the same interface (prototype-only wiring).
- [x] Add contract tests to keep adapters swappable without route changes.

Validation:
- `venv/bin/python -m pytest tests/memory/test_retrieval_adapter_contract.py -q --tb=short`

---

### Task 6: Integration and Gate

Files:
- Modify: `docs/DECISIONS.md` (only after approval)
- Modify: `docs/OPEN_LOOPS.md`

Steps:
- [x] Run focused memory test set.
- [ ] Run full suite before merge.
- [ ] Update open loops and decision status with acceptance/rejection notes.

Validation:
- `venv/bin/python -m pytest tests/ -q --tb=short`

---

## 2026-05-06 Progress Checkpoint

- Focused verification passed:
  - `venv/bin/python -m pytest tests/memory/test_source_ledger.py tests/memory/test_quarantine_queue.py tests/memory/test_storage_router.py tests/memory/test_retrieval_adapter_contract.py tests/services/test_context_service_retrieval_domain_filter.py -q --tb=short --noconftest`
  - Result: `20 passed`
- Strict gate attempt hit known metadata blocker:
  - `tests/memory/Icon`
  - `tests/memory/__pycache__/Icon`

---

## Guardrails

- No memory migration in this plan.
- No backend replacement in this plan.
- No MCP expansion.
- No proactive/autonomy feature implementation from parked cognitive set.
- No generated databases committed.

## Completion Criteria

1. Source ledger persists provenance and lifecycle safely.
2. Router enforces storage policy and fallback behavior.
3. Quarantine queue controls promotion to durable memory.
4. Retrieval regression is covered by tests.
5. Backend adapters can be swapped behind one contract.
6. Full test suite remains green.
