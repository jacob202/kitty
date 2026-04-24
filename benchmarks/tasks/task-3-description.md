# Task 3: Rename Internal Function Across Single File

**Category**: Single-file refactor

**Goal**: Test the agent's ability to rename a private function and all its callers within a single file.

**File**: `src/utils/circuit_breaker.py`

**Changes needed**: Rename `_resolve_state` to `_compute_state` (definition at line 68, call at line 114). The function is an internal helper that determines circuit state from failure count and last_failure timestamp.

**Prompt**: Ask the agent to rename the function.

**Success criteria**:
- Function definition at line 68 renamed from `_resolve_state` to `_compute_state`
- All call sites (line 114) updated
- No other changes to file
- Imports, docstrings, and other code untouched

**How to verify**: `grep -n "_resolve_state" src/utils/circuit_breaker.py` returns no matches. `grep -n "_compute_state" src/utils/circuit_breaker.py` returns 2 matches (definition + call site). Python import succeeds.

**Files to add to context**: `src/utils/circuit_breaker.py`

**Max turns**: 3
