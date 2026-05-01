# Phase 4 Merge Gate Run

Date: 2026-04-30
Generated at: 23:25:11
Runtime path: `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`
Port: 5001
Status: running

## Full Suite

Command:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```

Exit code: 0

```text
........................................................................ [ 18%]
........................................................................ [ 36%]
........................................................................ [ 54%]
........................................................................ [ 73%]
........................................................................ [ 91%]
.................................                                        [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
393 passed, 2 warnings in 23.60s
sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

