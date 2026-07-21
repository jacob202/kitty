# Plan: call_llm ProviderChainExhausted error contract

**Status:** Ready to implement (blast radius audit complete)
**Branch:** Any (independent of image cluster work)
**Candidate:** 4 (call_llm empty-string fake default)

## What changes

### New error type

`gateway/llm_client.py`:
- New `ProviderChainExhausted(RuntimeError)` with `self.errors: list[str]` carrying per-provider diagnostics
- `call_llm`: replace `return ""` on chain exhaustion with `raise ProviderChainExhausted(errors=[...])`
- `_LLM_CHAIN_DEADLINE` exceeded path: same raise
- `iter_chat_completions_stream`: on failure, yield nothing and raise `ProviderChainExhausted` (same contract)

### Caller audit (18 files)

Most callers fall into two patterns:

**Pattern A — blind return (most common):** `return call_llm(...)` in `next_step.py`, `triage.py`, `honcho.py`, `tutor.py`, `deadline_extractor.py`, `reset.py`, `librarian.py`. These propagate to routes which render the result. After the change: the exception propagates to FastAPI's default 500 handler — more correct than rendering an empty message.

**Pattern B — explicit check:** `inventory.py` does `if not content: return []`. After the change: needs `try/except ProviderChainExhausted: return []`.

**Pattern C — JSON parsing:** `learning.py` does `json.loads(response)`. After the change: the exception propagates naturally (same outcome as current `JSONDecodeError` on `""`, but with a better error message).

**Pattern D — strip/transform:** `expert_proactive.py` does `.strip()` on the result. After the change: exception propagates (correct — proactive features should fail visibly, not silently).

**Pattern E — streaming:** `telegram_bot.py` and `voice_pipeline.py` call `chat_completions_non_stream`. After the change: exception propagates to their error handlers.

### Files modified

- `gateway/llm_client.py` — new error type, raise instead of `return ""`
- `gateway/inventory.py` — add `try/except ProviderChainExhausted`
- All other callers: no changes needed (exception propagation is correct behavior)

## Tests

### New: `tests/test_llm_client_contract.py`

```python
async def test_call_llm_raises_on_chain_exhaustion():
    """When LiteLLM and all fallback providers fail, call_llm raises
    ProviderChainExhausted with per-provider diagnostics."""
    # Monkeypatch _post and _call_provider to always fail
    # Assert: ProviderChainExhausted raised
    # Assert: error.errors is non-empty

async def test_stream_raises_on_exhaustion():
    """iter_chat_completions_stream raises ProviderChainExhausted on total failure."""
    # Monkeypatch chat_completions_non_stream to fail
    # Assert: ProviderChainExhausted raised
```

### Existing tests

- Any test that calls `call_llm` and expects `""` needs updating — search for `call_llm` in tests and check assertions
- `tests/test_cold_start_acceptance.py` — likely unaffected (tests routes, not call_llm directly)

## Step order

1. Add `ProviderChainExhausted` to `gateway/llm_client.py`
2. Replace `return ""` in `call_llm` with `raise ProviderChainExhausted`
3. Replace silent yield in `iter_chat_completions_stream` with raise
4. Fix `gateway/inventory.py` caller with `try/except`
5. Write `tests/test_llm_client_contract.py`
6. Run `python3.12 -m pytest tests/ -q --tb=short`
7. `./kitty status` and `./kitty doctor --json` if services are running
