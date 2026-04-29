# Spec: Memory Inspect/Forget
## Source Request
Phase 6 — Memory and Source-Grounded Specialist: Build memory inspect/forget.

## Problem
Kitty needs memory inspect (list) and forget (delete) capabilities with vector store.

## Non-goals
- Do not wire into web.py yet
- Do not use LLM for embeddings (use substring search for now)

## Files Allowed To Change
- src/memory/inspect.py
- tests/test_memory_inspect.py
- specs/memory-inspect.spec.md (this file)
- src/memory/vector_store/sqlite_vec_store.py (already exists)
- src/memory/vector_store/null_store.py (already exists)

## Files Forbidden To Change
- web.py
- src/api/__init__.py
- src/memory/task_repo.py

## Required Behaviour
- `list_memories(store=None, limit=10) -> list[dict]`: list recent memories
- `forget(store=None, doc_id=None, query=None) -> dict`: delete by ID or query
- Uses SQLiteVecStore or NullStore
- Returns proper dict with deleted status and reason

## Acceptance Tests
- test_list_empty: empty store returns empty list
- test_list_with_data: returns added memories
- test_forget_by_id: deletes by ID
- test_forget_by_query: deletes by query match
- test_forget_nothing: returns deleted=False with reason

## Smoke Test
```bash
python3 -c "from src.memory.inspect import list_memories; print(list_memories())"
```
Expected: list (empty or with items)

## Validation
```bash
python3 -m pytest tests/test_memory_inspect.py -q
bash scripts/run_gates.sh
```

## Completion Report Required
- files read: src/memory/inspect.py, tests/test_memory_inspect.py
- files changed: new files only
- tests passed: 5/5
- gates passed: 65 passed
- docs updated: SESSION_SUMMARY.md, TASKS.md
- known risks: none
- next smallest action: specialist prototype (Alex code specialist)
