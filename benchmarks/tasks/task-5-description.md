# Task 5: Find and Fix a Bug (Real LSP-Identified Bug)

**Category**: Bug finding / code analysis

**Goal**: Test the agent's ability to find, understand, and fix a real bug that exists in the codebase, identified by the type checker.

**File**: `src/core/domain_router.py`

**The bug (LSP error at line 534)**:
```python
specialist=self.domain_patterns[best_domain]["specialist"],
```

The `RoutingDecision.__init__` expects `specialist: str`, but `self.domain_patterns` is a dict where values have heterogeneous types (`list[str]` for keywords, `str` for specialist). The type checker flags this as `list[str] | str` being passed where `str` is expected. While at runtime this works (the value is always a `str`), the type issue needs to be fixed.

Additionally, the `domain_patterns` dict values have no schema — they use magic strings for keys ("keywords", "specialist", "description") which is fragile.

**Prompt**: Ask the agent to find and fix the bug in domain_router.py.

**Success criteria**:
- The LSP error at line 534 is fixed (ensure `specialist` gets a `str`)
- The runtime behavior is unchanged
- No other bugs introduced
- Bonus: The `get_domain_info` method's return type is also fixed (line 548)

**How to verify**: Check that `src/core/domain_router.py` still works. Verify `python -c "from src.core.domain_router import DomainRouter; r = DomainRouter(); print(r.route('fix my amp'))"` works.

**Files to add to context**: `src/core/domain_router.py`

**Max turns**: 8
