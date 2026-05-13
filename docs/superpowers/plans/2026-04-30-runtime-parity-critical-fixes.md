# Runtime Parity Critical Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the smallest audited runtime blockers: MemoryWeave import failure, specialist router code-query misroute, and `/unified` uncontrolled supervisor-shim failure.

**Architecture:** Keep changes narrow and test-first. Use the existing centralized database path registry, preserve the existing simple specialist router shape, and make `/unified` fail closed when the web shim lacks the required method.

**Tech Stack:** Python 3.12, Flask blueprints, pytest, Kitty legacy checkout plus copied migrated runtime workspace.

---

## File Structure

- Modify `src/core/db_config.py`: add the missing `memory_weave` path to `DB_PATHS`.
- Create `tests/test_memory_weave.py`: import regression for MemoryWeave DB path wiring.
- Modify `src/core/specialists/router.py`: route code/programming queries to the code specialist identifier instead of Alex.
- Modify `tests/test_specialist_router.py`: add or adjust the code-query routing regression.
- Modify `src/api/streaming_routes.py`: guard `/unified` when supervisor lacks `handle_unified_request`.
- Create `tests/test_unified_route.py`: verify `/unified` returns controlled `501` in web-shim mode.
- Sync `src/api/news_routes.py` and `src/services/domain_news_monitor.py` if migrated test collection requires the legacy news blueprint files already referenced by `src/api/__init__.py`.

Do not edit `web.py`, launch scripts, `kitty-chat/`, or generated data files in this plan.

### Task 1: MemoryWeave Import Regression

**Files:**
- Create: `tests/test_memory_weave.py`
- Modify: `src/core/db_config.py`

- [ ] **Step 1: Write the failing import test**

Add this file:

```python
"""Regression tests for MemoryWeave database path wiring."""

import importlib


def test_memory_weave_imports_with_configured_db_path():
    module = importlib.import_module("src.memory.memory_weave")

    assert module._DB_PATH.name == "memory_weave.db"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py -q --tb=short
```

Expected before implementation:

```text
FAILED tests/test_memory_weave.py::test_memory_weave_imports_with_configured_db_path
ValueError: Unknown database: memory_weave
```

- [ ] **Step 3: Add the database path**

In `src/core/db_config.py`, add this key inside `DB_PATHS`:

```python
    "memory_weave": DATA_ROOT / "memory_weave.db",
```

Keep the existing `get_db_path()` behavior unchanged.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py -q --tb=short
```

Expected after implementation:

```text
1 passed
```

### Task 2: Specialist Router Code Query Regression

**Files:**
- Modify: `tests/test_specialist_router.py`
- Modify: `src/core/specialists/router.py`

- [ ] **Step 1: Inspect current router tests**

Run:

```bash
sed -n '1,220p' tests/test_specialist_router.py
```

Expected: identify the existing style for `route_specialist()` assertions and add the new test beside related routing tests.

- [ ] **Step 2: Add the failing code routing test**

Add this assertion to `tests/test_specialist_router.py`:

```python
def test_code_query_routes_to_code_specialist():
    from src.core.specialists.router import route_specialist

    assert route_specialist("debug this python function bug") in {
        "code",
        "kittycoder",
        "KittyCoder",
    }
```

- [ ] **Step 3: Run the focused router test**

Run:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_specialist_router.py -q --tb=short
```

Expected before implementation:

```text
FAILED ... assert 'alex' in {'code', 'kittycoder', 'KittyCoder'}
```

- [ ] **Step 4: Fix the route target**

In `src/core/specialists/router.py`, change the code keyword branch from:

```python
    if any(w in low for w in ["code", "program", "script", "function", "bug", "python", "javascript"]):
        return "alex"  # code
```

to:

```python
    if any(w in low for w in ["code", "program", "script", "function", "bug", "python", "javascript"]):
        return "KittyCoder"
```

- [ ] **Step 5: Run the focused router test again**

Run:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_specialist_router.py -q --tb=short
```

Expected:

```text
passed
```

### Task 3: `/unified` Guard Regression

**Files:**
- Create: `tests/test_unified_route.py`
- Modify: `src/api/streaming_routes.py`

- [ ] **Step 1: Write the failing route guard test**

Add this file:

```python
"""Regression tests for /unified behavior in web-shim mode."""

from flask import Flask

from src.api.streaming_routes import streaming_bp


class SupervisorWithoutUnified:
    pass


def test_unified_returns_501_when_supervisor_lacks_handler():
    app = Flask(__name__)
    app.secret_key = "test"
    app.supervisor = SupervisorWithoutUnified()
    app.register_blueprint(streaming_bp)

    client = app.test_client()
    response = client.post("/unified", json={"message": "hello"})

    assert response.status_code == 501
    assert response.get_json() == {
        "ok": False,
        "error": "Unified request not yet implemented",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_unified_route.py -q --tb=short
```

Expected before implementation:

```text
FAILED tests/test_unified_route.py::test_unified_returns_501_when_supervisor_lacks_handler
AttributeError: 'SupervisorWithoutUnified' object has no attribute 'handle_unified_request'
```

- [ ] **Step 3: Add the route guard**

In `src/api/streaming_routes.py`, inside the `/unified` route after:

```python
    sup = current_app.supervisor
```

add:

```python
    if not hasattr(sup, "handle_unified_request"):
        return jsonify({"ok": False, "error": "Unified request not yet implemented"}), 501
```

- [ ] **Step 4: Run the route guard test again**

Run:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_unified_route.py -q --tb=short
```

Expected:

```text
1 passed
```

### Task 4: Legacy Focused Validation

**Files:**
- Read/validate only.

- [ ] **Step 1: Run all focused tests**

Run:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py tests/test_specialist_router.py tests/test_unified_route.py tests/test_default_web_chat_mode.py -q --tb=short
```

Expected:

```text
passed
```

- [ ] **Step 2: Check for generated DB files**

Run:

```bash
git status --short data src/core/db_config.py src/core/specialists/router.py src/api/streaming_routes.py tests/test_memory_weave.py tests/test_specialist_router.py tests/test_unified_route.py
```

Expected: source/test changes only; generated DB files in `data/` must not be staged or committed.

### Task 5: Sync To Migrated Runtime

**Files:**
- Copy to migrated runtime:
  - `src/core/db_config.py`
  - `src/core/specialists/router.py`
  - `src/api/streaming_routes.py`
  - `src/api/news_routes.py`
  - `src/services/domain_news_monitor.py`
  - `tests/test_memory_weave.py`
  - `tests/test_specialist_router.py`
  - `tests/test_unified_route.py`

- [ ] **Step 1: Copy exact files**

Run the copy commands from the legacy checkout. These may require approval because the migrated runtime is outside the writable root:

```bash
cp src/core/db_config.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/core/db_config.py
cp src/core/specialists/router.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/core/specialists/router.py
cp src/api/streaming_routes.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/api/streaming_routes.py
cp src/api/news_routes.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/api/news_routes.py
cp src/services/domain_news_monitor.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/services/domain_news_monitor.py
cp tests/test_memory_weave.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/tests/test_memory_weave.py
cp tests/test_specialist_router.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/tests/test_specialist_router.py
cp tests/test_unified_route.py /Users/jacobbrizinski/Projects/kitty-system/kitty-app/tests/test_unified_route.py
```

- [ ] **Step 2: Verify parity**

Run:

```bash
for f in src/core/db_config.py src/core/specialists/router.py src/api/streaming_routes.py src/api/news_routes.py src/services/domain_news_monitor.py tests/test_memory_weave.py tests/test_specialist_router.py tests/test_unified_route.py; do cmp -s "$f" "/Users/jacobbrizinski/Projects/kitty-system/kitty-app/$f" || exit 1; done
```

Expected: exit code 0.

### Task 6: Migrated Validation And Live Smoke

**Files:**
- Read/validate only.

- [ ] **Step 1: Run focused tests in migrated runtime**

Run:

```bash
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app
/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py tests/test_specialist_router.py tests/test_unified_route.py tests/test_default_web_chat_mode.py -q --tb=short
```

Expected:

```text
passed
```

- [ ] **Step 2: Check live server status**

Run:

```bash
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app
./kitty status
```

Expected: running on port 5001 from `kitty-system/kitty-app`.

- [ ] **Step 3: Smoke core public routes**

Run:

```bash
curl -sS -o /tmp/kitty_brief_smoke.json -w '%{http_code}' http://localhost:5001/api/brief
curl -sS -o /tmp/kitty_command_smoke.json -w '%{http_code}' -X POST http://localhost:5001/api/command -H 'Content-Type: application/json' -d '{"command":"/stuck"}'
curl -sS -o /tmp/kitty_caps_smoke.json -w '%{http_code}' http://localhost:5001/api/capabilities
```

Expected:

```text
200
200
200
```

- [ ] **Step 4: Note health route gate**

Run:

```bash
curl -sS -o /tmp/kitty_health_smoke.json -w '%{http_code}' http://localhost:5001/health
curl -sS -o /tmp/kitty_api_health_smoke.json -w '%{http_code}' http://localhost:5001/api/health
```

Expected with default runtime config:

```text
404
404
```

Reason: both routes call `_require_internal_api()` and are hidden unless `KITTY_ENABLE_INTERNAL_API=1`.

### Task 7: Completion Report

**Files:**
- Modify: `docs/AGENT_COORDINATION.md`

- [ ] **Step 1: Mark lane complete**

In `docs/AGENT_COORDINATION.md`, set `runtime-001` to `complete`.

- [ ] **Step 2: Add handoff**

Add a handoff that includes:

```markdown
**Lane**: `runtime-001`
**Files changed**: list source and test files
**Files synced**: list migrated files
**Validation**: focused tests in legacy and migrated
**Live smoke**: brief, command, capabilities results; health gate noted
**Restart needed**: yes/no
**Known gaps**: route coverage, UI backend config, broader specialist KB completion
```
