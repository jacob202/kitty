# Task 4: Multi-File Refactor (Extract Logger + Update Imports)

**Category**: Multi-file refactor

**Goal**: Test the agent's ability to extract a function from one file to a new file, wire imports, and handle cross-module dependencies correctly.

**Files involved**:
- `src/core/error_handler.py` (source — `log_error` function at line 274)
- `src/tools/base.py` (caller — imports `log_error`)
- New file `src/core/error_logger.py` (target)

**The task**: Extract the `log_error` function from `src/core/error_handler.py` into a new file `src/core/error_logger.py`, update all imports across the project, and ensure everything still works.

**The `log_error` function** (line 274-289):
```python
def log_error(error: Exception, context: dict | None = None):
    """Log error to file for debugging"""
    from datetime import datetime
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "error_type": classify_error(error),
        "error_message": str(error),
        "context": context or {},
    }
    log_path = Path("data/logs/error_log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```

Dependencies of `log_error`:
- Uses `classify_error` (stays in `error_handler.py`)
- Uses `json`, `Path`, `datetime` (standard lib)
- Uses `datetime.now().isoformat()` (standard lib)

So the new `error_logger.py` needs to import `classify_error` from `error_handler.py`.

Callers of `log_error` (need import updates):
- `src/tools/base.py` (if it imports from error_handler)

**Prompt**: Ask the agent to extract `log_error` into a new file.

**Success criteria**:
- New file `src/core/error_logger.py` exists with the extracted `log_error` function
- `log_error` still present in `src/core/error_handler.py` OR imported from new file (depends on approach — check if agent uses re-export or removal)
- All imports in caller files updated correctly
- No circular imports created
- `from src.core.error_logger import log_error` works

**How to verify**:
- `python -c "from src.core.error_logger import log_error"`
- Check `error_handler.py` for import addition or function removal
- Check `base.py` for import update

**Files to add to context**: `src/core/error_handler.py`, `src/tools/base.py`

**Max turns**: 10
