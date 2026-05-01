# Phase 4 Merge Gate Run

Date: 2026-04-30
Generated at: 11:59:39
Runtime path: `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`
Port: 5001
Status: running

## Full Suite

Skipped via --skip-full

## Focused Route Suite

Command:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_web_chat_phase1.py tests/test_brief_route.py tests/test_commands_route.py -q --tb=short
```

Exit code: 0

```text
......................                                                   [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
22 passed, 2 warnings in 38.39s
```

