# Phase 14 — Gateway Auth + Housekeeping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the gateway with bearer-token auth middleware, archive the 220-file legacy `src/` tree so agents stop importing from it, update `./kitty` to start the new stack on port 8000, and add the Phase 14 gate check.

**Architecture:** A single `BearerAuthMiddleware` class reads `GATEWAY_SECRET` from the env on each request (so tests can patch it). `/health` is exempt so start scripts don't need auth. If `GATEWAY_SECRET` is unset, auth is disabled — safe default for local dev. `src/` moves to `archive/src_legacy/`. `./kitty` gets a new `_start()` that delegates to `kitty_gateway/start_all.sh` and probes port 8000.

**Tech Stack:** FastAPI/Starlette middleware, os.environ, bash

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `gateway/auth.py` | Create | `BearerAuthMiddleware` — reads `GATEWAY_SECRET` per request |
| `gateway/app.py` | Modify | Wire `BearerAuthMiddleware` after CORS |
| `tests/test_auth.py` | Create | Auth middleware tests |
| `./kitty` | Modify | `_start()` delegates to `start_all.sh`, port 8000 |
| `archive/src_legacy/` | Create (mv) | Old `src/` tree — prevents stale imports |
| `scripts/setup/gate-check.sh` | Modify | Phase 14 gate |

---

### Task 1: Auth middleware

**Files:**
- Create: `gateway/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth.py
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from gateway.app import app


def test_health_always_accessible():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/health")
    assert resp.status_code == 200


def test_protected_without_auth_returns_401():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/weekly")
    assert resp.status_code == 401


def test_protected_with_wrong_token_returns_401():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/weekly", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_protected_with_correct_token_passes_auth():
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret"}):
        client = TestClient(app)
        resp = client.get("/weekly", headers={"Authorization": "Bearer test-secret"})
    assert resp.status_code != 401


def test_no_secret_disables_auth():
    with patch.dict(os.environ, {"GATEWAY_SECRET": ""}):
        client = TestClient(app)
        resp = client.get("/health")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_auth.py -v
```
Expected: ImportError or all tests failing because `gateway/auth.py` doesn't exist.

- [ ] **Step 3: Create gateway/auth.py**

```python
# gateway/auth.py
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/health"}


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        secret = os.environ.get("GATEWAY_SECRET", "")
        if request.url.path in EXEMPT_PATHS or not secret:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != secret:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
```

- [ ] **Step 4: Wire into gateway/app.py**

After the `CORSMiddleware` block (around line 39), add:

```python
from gateway.auth import BearerAuthMiddleware
app.add_middleware(BearerAuthMiddleware)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
venv/bin/pytest tests/test_auth.py -v
```
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add gateway/auth.py gateway/app.py tests/test_auth.py
git commit -m "feat: Phase 14 — bearer token auth middleware"
```

---

### Task 2: Archive legacy src/

**Files:**
- Move: `src/` → `archive/src_legacy/`

- [ ] **Step 1: Verify src/ exists and check size**

```bash
ls /Users/jacobbrizinski/Projects/kitty/src/ | wc -l
```
Expected: shows file/dir count (should be non-zero)

- [ ] **Step 2: Move src/ to archive/**

```bash
cd /Users/jacobbrizinski/Projects/kitty
mkdir -p archive
mv src archive/src_legacy
```

- [ ] **Step 3: Verify tests still pass (no broken imports)**

```bash
venv/bin/pytest tests/ -q --tb=short -x
```
Expected: same pass count as before (645+). If any test imports from `src.`, find and fix the import — but there should be none since the gateway replaced src/.

- [ ] **Step 4: Commit**

```bash
git add archive/ && git add -u src/
git commit -m "chore: Phase 14 — archive legacy src/ to archive/src_legacy"
```

---

### Task 3: Update ./kitty script

**Files:**
- Modify: `./kitty`

The current `_start()` launches `web.py` on port 5001. It needs to call `bash kitty_gateway/start_all.sh` and probe port 8000.

- [ ] **Step 1: Update PORT and _start() in ./kitty**

Find and replace the `PORT` line and the `_start` function body. The new `_start()`:

```bash
PORT="${KITTY_PORT:-8000}"

_start() {
  local port_pid=$(_port_pid)
  if [[ -n "$port_pid" ]]; then
    echo "Kitty is already running (PID $port_pid) — http://localhost:$PORT"
    return 0
  fi

  echo "Starting Kitty…"
  bash "$SCRIPT_DIR/kitty_gateway/start_all.sh" &

  # Wait for gateway to be ready (max 30s)
  local waited=0
  until "$CURL" -sf "http://localhost:$PORT/health" > /dev/null 2>&1; do
    sleep 0.5
    (( waited++ ))
    [[ $waited -ge 60 ]] && { echo "Gateway didn't respond after 30s — check logs/"; return 1; }
  done

  local ip=$(_ip)
  echo ""
  echo "  ┌────────────────────────────────────────────┐"
  echo "  │  🐱  Kitty is live                         │"
  echo "  │                                            │"
  printf "  │  Gateway  →  http://localhost:%s         │\n" "$PORT"
  printf "  │  WebUI    →  http://localhost:3000        │\n"
  printf "  │  Phone    →  http://%s:%s    │\n" "$ip" "$PORT"
  echo "  └────────────────────────────────────────────┘"
  echo ""
}
```

- [ ] **Step 2: Test the script parses without errors**

```bash
zsh -n /Users/jacobbrizinski/Projects/kitty/kitty
```
Expected: no output (syntax OK)

- [ ] **Step 3: Test status subcommand works**

```bash
/Users/jacobbrizinski/Projects/kitty/kitty status
```
Expected: prints "stopped" or "running" without crashing.

- [ ] **Step 4: Commit**

```bash
git add kitty
git commit -m "feat: Phase 14 — ./kitty now starts gateway stack on port 8000"
```

---

### Task 4: Gate check

**Files:**
- Modify: `scripts/setup/gate-check.sh`

- [ ] **Step 1: Add Phase 14 gate**

Add this block before the final `echo "Results..."` line:

```bash
if [ "$PHASE" = "14" ]; then
    echo "[ Auth + Housekeeping ]"
    check "gateway/auth.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/auth.py"
    check "BearerAuthMiddleware in app.py" \
        "grep -q 'BearerAuthMiddleware' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "auth tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_auth.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "src/ is archived" \
        "test -d /Users/jacobbrizinski/Projects/kitty/archive/src_legacy && ! test -d /Users/jacobbrizinski/Projects/kitty/src"
    check "./kitty probes port 8000" \
        "grep -q 'KITTY_PORT:-8000' /Users/jacobbrizinski/Projects/kitty/kitty"
    check "full test suite still passes" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/ -q --tb=no 2>/dev/null | grep -q 'passed'"
fi
```

- [ ] **Step 2: Run gate check**

```bash
bash /Users/jacobbrizinski/Projects/kitty/scripts/setup/gate-check.sh 14
```
Expected: Phase 14 COMPLETE ✓

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/gate-check.sh
git commit -m "feat: Phase 14 complete — gate check added"
```
