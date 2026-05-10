# Phase 15 — LLM 3-Decision Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the approved 3-decision routing into `llm_client.py` so every chat turn automatically picks the right model: offline → local Qwen 7B (MLX), reasoning questions → deepseek-r1-0528, explicit "best" requests → claude-sonnet-4-6, everything else → qwen/qwen3-235b-a22b-2507.

**Architecture:** A new `route_model(message)` function in `gateway/llm_client.py` does keyword matching in O(1) — no LLM call to route. In `gateway/app.py`'s `chat_completions`, replace the hardcoded `"kitty-default"` fallback with `route_model(user_text)` for non-health domains. Health stays on `"kitty-private"`. The routing decision is logged at DEBUG level so cost tracking can pick it up later.

**Tech Stack:** Python stdlib (socket for offline check), existing gateway/llm_client.py, gateway/app.py

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `gateway/llm_client.py` | Modify | Add `route_model()` + `_is_offline()` |
| `gateway/app.py` | Modify | Use `route_model()` in `chat_completions` |
| `tests/test_llm_routing.py` | Create | Unit tests for routing logic |
| `scripts/setup/gate-check.sh` | Modify | Phase 15 gate |

---

### Task 1: route_model() in llm_client.py

**Files:**
- Modify: `gateway/llm_client.py`
- Test: `tests/test_llm_routing.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm_routing.py
"""Unit tests for the 3-decision model router."""
from unittest.mock import patch
from gateway.llm_client import route_model


def test_default_routes_to_qwen():
    with patch("gateway.llm_client._is_offline", return_value=False):
        assert route_model("What should I have for breakfast?") == "qwen/qwen3-235b-a22b-2507"


def test_reasoning_keyword_routes_to_deepseek():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Can you explain why the sky is blue?")
    assert result == "deepseek/deepseek-r1-0528"


def test_analyze_keyword_routes_to_deepseek():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Analyze the pros and cons of this approach")
    assert result == "deepseek/deepseek-r1-0528"


def test_best_trigger_routes_to_claude():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Use your best model for this important decision")
    assert result == "claude-sonnet-4-6"


def test_use_claude_routes_to_claude():
    with patch("gateway.llm_client._is_offline", return_value=False):
        result = route_model("Use claude for this")
    assert result == "claude-sonnet-4-6"


def test_offline_routes_to_local():
    with patch("gateway.llm_client._is_offline", return_value=True):
        result = route_model("Anything at all")
    assert result == "mlx-local"


def test_offline_checked_first():
    """Offline beats reasoning and best triggers."""
    with patch("gateway.llm_client._is_offline", return_value=True):
        result = route_model("Use your best model and explain why")
    assert result == "mlx-local"
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_llm_routing.py -v
```
Expected: FAIL with `ImportError: cannot import name 'route_model' from 'gateway.llm_client'`

- [ ] **Step 3: Add route_model() and _is_offline() to gateway/llm_client.py**

Append this to the bottom of `gateway/llm_client.py` (after the existing `_fallback_openrouter` function):

```python
_REASONING_KEYWORDS = frozenset({
    "explain", "why", "analyze", "analyse", "reason", "think through",
    "break down", "compare", "pros and cons", "pros cons", "step by step",
    "walk me through", "how does", "what causes",
})

_BEST_TRIGGERS = frozenset({
    "best model", "use claude", "use sonnet", "use your best",
    "most capable", "smartest model",
})

_DEFAULT_MODEL = "qwen/qwen3-235b-a22b-2507"
_REASONING_MODEL = "deepseek/deepseek-r1-0528"
_BEST_MODEL = "claude-sonnet-4-6"
_LOCAL_MODEL = "mlx-local"


def _is_offline() -> bool:
    """True if we cannot reach OpenRouter (2s timeout)."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("openrouter.ai", 443))
        s.close()
        return False
    except OSError:
        return True


def route_model(message: str) -> str:
    """3-decision router — returns the LiteLLM model string for a user message."""
    if _is_offline():
        logger.debug("routing: offline → %s", _LOCAL_MODEL)
        return _LOCAL_MODEL

    msg_lower = message.lower()

    if any(t in msg_lower for t in _BEST_TRIGGERS):
        logger.debug("routing: best trigger → %s", _BEST_MODEL)
        return _BEST_MODEL

    if any(kw in msg_lower for kw in _REASONING_KEYWORDS):
        logger.debug("routing: reasoning keyword → %s", _REASONING_MODEL)
        return _REASONING_MODEL

    logger.debug("routing: default → %s", _DEFAULT_MODEL)
    return _DEFAULT_MODEL
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/pytest tests/test_llm_routing.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add gateway/llm_client.py tests/test_llm_routing.py
git commit -m "feat: Phase 15 — 3-decision model router in llm_client"
```

---

### Task 2: Wire route_model() into chat_completions

**Files:**
- Modify: `gateway/app.py`

In `chat_completions`, the model is currently set at line ~166:
```python
model = body.get("model", "kitty-default")
```

This stays as-is (captures what Open WebUI sends). After the domain classification and before building the payload, override the model using the router for non-health domains.

- [ ] **Step 1: Add the import at the top of gateway/app.py**

Find the existing imports block and add (near the other gateway imports):

```python
from gateway.llm_client import route_model
```

- [ ] **Step 2: Replace the model selection in chat_completions**

Find this section in `chat_completions` (around line 178-180 where domain is set):

```python
    domain = classify_domain(user_text)
    system_prompt = load_prompt(domain)
```

After those two lines, add:

```python
    if domain == "health":
        model = "kitty-private"
    else:
        model = route_model(user_text)
```

This replaces whatever model Open WebUI sent with the routed model (unless health domain, which always uses kitty-private for privacy).

- [ ] **Step 3: Run full test suite to verify no regressions**

```bash
venv/bin/pytest tests/ -q --tb=short
```
Expected: same or higher pass count (no failures introduced)

- [ ] **Step 4: Smoke test against live gateway (if running)**

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain why memory consolidation happens during sleep"}' | python3 -m json.tool
```
Expected: reply is present; check `logs/gateway_trace.jsonl` — last entry should show `deepseek/deepseek-r1-0528` as the model.

If gateway isn't running, skip this step.

- [ ] **Step 5: Commit**

```bash
git add gateway/app.py
git commit -m "feat: Phase 15 — wire route_model() into chat_completions"
```

---

### Task 3: Gate check

**Files:**
- Modify: `scripts/setup/gate-check.sh`

- [ ] **Step 1: Add Phase 15 gate**

Add this block before the final `echo "Results..."` line:

```bash
if [ "$PHASE" = "15" ]; then
    echo "[ LLM 3-Decision Router ]"
    check "route_model() in llm_client.py" \
        "grep -q 'def route_model' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
    check "_is_offline() in llm_client.py" \
        "grep -q 'def _is_offline' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
    check "route_model imported in app.py" \
        "grep -q 'route_model' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "routing tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_llm_routing.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "full test suite passes" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/ -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "qwen3-235b in router default" \
        "grep -q 'qwen3-235b' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
    check "deepseek-r1 in router" \
        "grep -q 'deepseek-r1' /Users/jacobbrizinski/Projects/kitty/gateway/llm_client.py"
fi
```

- [ ] **Step 2: Run gate check**

```bash
bash /Users/jacobbrizinski/Projects/kitty/scripts/setup/gate-check.sh 15
```
Expected: Phase 15 COMPLETE ✓

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/gate-check.sh
git commit -m "feat: Phase 15 complete — gate check added"
```
