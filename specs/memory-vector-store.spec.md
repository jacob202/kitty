# Spec: Memory Inspect/Forget + Vector Adapter
## Source Request
Phase 6 — Memory and Source-Grounded Specialist: Build memory inspect/forget, vector adapter.

## Problem
Kitty needs memory inspect/forget capabilities and a vector store adapter for semantic search.

## Non-goals
- Do not wire to web.py yet
- Do not use LLM for embeddings (use simple substring for now)

## Files Allowed To Change
- src/memory/vector_store/base.py
- src/memory/vector_store/null_store.py
- src/memory/vector_store/sqlite_vec_store.py
- tests/test_vector_store.py
- src/core/specialists/router.py
- src/core/specialists/validator.py
- tests/test_specialist_router.py
- tests/test_specialist_validator.py
- specs/memory-vector-store.spec.md (this file)

## Files Forbidden To Change
- web.py
- src/api/__init__.py
- src/memory/task_repo.py

## Required Behaviour

### VectorStore (base.py)
- Abstract base with: add(), search(), delete(), get()
- NullStore: no-op for testing
- SQLiteTextStore: sqlite3 backend with substring search

### Specialist Router (router.py)
- route_specialist(message) -> specialist name or None
- get_specialist_context(name) -> dict with context and source

### Specialist Validator (validator.py)
- validate_answer(specialist, answer, source) -> dict: {valid, confidence, issues}
- Rules: source required for device/medical/procedural claims

## Acceptance Tests
- TestNullStore: add, search, delete, get work
- TestSQLiteTextStore: init creates db, add+get, search, delete
- TestSpecialistRouter: routes to mike/kelly/alex/research correctly
- TestSpecialistValidator: validates answers, flags missing source

## Smoke Test
```bash
python3 -c "from src.memory.vector_store import SQLiteTextStore; s=SQLiteTextStore('/tmp/test.db'); print('OK')"
```

## Validation
```bash
python3 -m pytest tests/test_vector_store.py tests/test_specialist_router.py tests/test_specialist_validator.py -q`
bash scripts/run_gates.sh`
```

## Completion Report Required
- files read: vector_store/*, specialists/*
- files changed: new files only
- tests passed: 20/20 Phase 6
- gates passed: 65 passed
- docs updated: SESSION_SUMMARY.md, TASKS.md
- known risks: none
- next smallest action: test wired routes, run chat consolidation
