# Plan: memory_graph adapter contract enforcement

**Status:** Ready to implement
**Branch:** Any (independent of image cluster work)
**Candidate:** 3 (memory_graph adapter contract drift)

## What changes

### Adapter error handling

- `gateway/memory_graph.py` `SignalsAdapter.fetch()`: delete try/except wrapper; let exceptions propagate to `search_all`'s isolation
- `gateway/memory_graph.py` `WeaveAdapter.fetch()`: delete try/except wrapper; same reason
- `search_all` already owns failure isolation (`GraphResult.errors`) — no changes needed there

### Source labeling

- `SignalsAdapter.fetch()`: change `source=Source.TRACES` to `source="signals"` (matches adapter name)
- `WeaveAdapter.fetch()`: change `source=Source.MEMORY` to `source="facts"` (matches adapter name)
- These are string values on `Item.source` — downstream formatters group by this field, so signals stop masquerading as traces and facts stop mixing with memory

### KnowledgeAdapter async fix

- `KnowledgeAdapter.fetch()`: change `asyncio.to_thread(lambda: asyncio.run(search(query, limit=3)))` to `await search(query, limit=3)` directly
- `knowledge.search` is already async; the `to_thread(asyncio.run(...))` was a defensive wrapper from when callers were sync

**Files modified:** `gateway/memory_graph.py`

## Tests

### New: `tests/test_memory_graph_contract.py`

One parameterized contract test over all adapters:

```python
@pytest.mark.parametrize("adapter_cls", [
    MemoryAdapter, KnowledgeAdapter, JournalAdapter,
    TracesAdapter, TodosAdapter, InboxAdapter,
    SignalsAdapter, WeaveAdapter,
])
async def test_adapter_failure_surfaces_in_graph_result(adapter_cls):
    """When an adapter's fetch raises, search_all isolates the failure
    into GraphResult.errors and returns [] for that adapter."""
    # Monkeypatch the adapter's fetch to raise RuntimeError
    # Assert: result.errors contains the adapter name
    # Assert: result.results[adapter.name] == []
```

Source label test:

```python
async def test_signals_adapter_source_label():
    """SignalsAdapter items have source='signals', not 'traces'."""
    # Monkeypatch signal_store.list_recent to return a fixture
    # Assert: items[0].source == "signals"

async def test_weave_adapter_source_label():
    """WeaveAdapter items have source='facts', not 'memory'."""
    # Monkeypatch weave.search to return a fixture
    # Assert: items[0].source == "facts"
```

### Existing tests

- `tests/test_memory_graph.py` — should pass unchanged (adapters that already raised still raise)
- `tests/test_search.py` — may need source-value updates if it asserts on `Source.TRACES` for signals

## Step order

1. Fix source labels in `SignalsAdapter` and `WeaveAdapter`
2. Delete try/except in `SignalsAdapter.fetch()` and `WeaveAdapter.fetch()`
3. Fix `KnowledgeAdapter.fetch()` to `await` directly
4. Write `tests/test_memory_graph_contract.py`
5. Run `python3.12 -m pytest tests/test_memory_graph.py tests/test_memory_graph_contract.py tests/test_search.py -q --tb=short`
6. Run full suite: `python3.12 -m pytest tests/ -q --tb=short`
