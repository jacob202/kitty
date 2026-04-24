# Task 6: Write Unit Tests for a Module

**Category**: Test generation

**Goal**: Test the agent's ability to write comprehensive pytest unit tests for a module that has zero existing tests.

**File**: `src/utils/fuzzy_matcher.py`

**Context**: The `tests/` directory does not exist. Tests should be created in a new `tests/` directory.

**Functions to test**:
- `normalize_component_id(text)` — normalizes R761 -> r761, handles spaces
- `fuzzy_match(query, candidates, cutoff, max_results)` — fuzzy matching with scoring
- `extract_component_ids(text)` — extracts component IDs like R101, C47
- `fix_typo(query, known_components)` — typo correction
- `tokenize_query(query)` — token splitting
- `expand_query(query, known_components)` — query expansion

**Prompt**: Ask the agent to write comprehensive pytest unit tests for the fuzzy_matcher module.

**Success criteria**:
- Tests exist in `tests/test_fuzzy_matcher.py`
- All 6 functions have test coverage
- Tests cover: happy paths, edge cases, empty inputs
- Tests pass when run with `python -m pytest tests/test_fuzzy_matcher.py -v`
- Good test structure (test functions named descriptively, using assertions)

**How to verify**: Run `python -m pytest tests/test_fuzzy_matcher.py -v` and all tests pass.

**Files to add to context**: `src/utils/fuzzy_matcher.py`

**Max turns**: 10
