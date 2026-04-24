# Task 2: Add Type Annotations

**Category**: Simple code change / type hygiene

**Goal**: Test the agent's ability to add type annotations to an untyped Python module without changing behavior.

**File**: `src/utils/fuzzy_matcher.py`

**Context**: This module has no type annotations on any of its 6 functions. Several functions have `list[tuple[str, float]]` return types. There is an unused variable `score` at line 93.

**Prompt**: Ask the agent to add type annotations to all function signatures in the file and fix the unused variable.

**Success criteria**:
- All 6 functions annotated with types
- `score` variable at line 93 is handled (rename to `_` or use it)
- File behavior is unchanged
- Type checker reports fewer warnings

**How to verify**: Run `git diff` to check annotations were added. Run Python import to confirm no syntax errors.

**Files to add to context**: `src/utils/fuzzy_matcher.py`

**Max turns**: 5
