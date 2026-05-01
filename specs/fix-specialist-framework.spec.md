# Spec: Fix Specialist Framework Bugs

## Problem

Two bugs in `src/core/specialist_framework.py` break core functionality:

1. **Line 9**: `from dataclasses import dataclass` misspelled as `dataclasses` — causes `ImportError` on any import
2. **Line 182**: Broken set comprehension `"".join(filter(str.isalnum, w))` iterates chars of each word instead of filtering whole words, and missing `for` in set comprehension — Memory Weave never fires

## Proposed shape

Two one-line fixes + one new test for the entity extraction helper.

## Allowed files

- `specs/fix-specialist-framework.spec.md` (this file)
- `src/core/specialist_framework.py`
- `tests/test_specialist_framework.py`

## Forbidden files

- All other runtime source
- All other test files
- `docs/` control files (except handoff)

## Validation

```bash
# The typo fix — module imports without error
/opt/homebrew/bin/python3.12 -c "from src.core.specialist_framework import BaseSpecialist; print('import OK')"

# Test for entity extraction logic
/opt/homebrew/bin/python3.12 -m pytest tests/test_specialist_framework.py -q --tb=short

# No regressions
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short

# Control gates
bash scripts/run_gates.sh
```

## Rollback

```bash
git checkout -- src/core/specialist_framework.py
git checkout -- tests/test_specialist_framework.py
```

## Risks

- Low. Two targeted syntax/bug fixes in one file. No architectural changes.

## Minimum safe version

Immediately — two line fixes + one test.
