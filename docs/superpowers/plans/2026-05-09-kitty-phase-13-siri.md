# Phase 13 — Siri Shortcut → Kitty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/ask` endpoint to the gateway that returns plain JSON (no SSE streaming), then document the exact iOS Shortcut steps so Jacob can say "Hey Siri, ask Kitty" and hear a spoken response.

**Architecture:** The existing `/v1/chat/completions` streams SSE which iOS Shortcuts can't parse. A new `/ask` endpoint accepts `{"message": "..."}` and returns `{"reply": "..."}` as a single JSON object. The iOS Shortcut calls this via "Get Contents of URL", extracts the reply, and speaks it. No new Python packages needed — this reuses the existing gateway pipeline.

**Tech Stack:** FastAPI, httpx (existing), iOS Shortcuts app, Tailscale (100.84.78.1)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `gateway/app.py` | Modify | Add `/ask` endpoint (non-streaming) |
| `tests/test_ask_endpoint.py` | Create | Tests for `/ask` |
| `docs/SIRI_SHORTCUT.md` | Create | Step-by-step Shortcuts setup guide |
| `scripts/setup/gate-check.sh` | Modify | Add Phase 13 gate |

---

### Task 1: `/ask` endpoint

**Files:**
- Modify: `gateway/app.py`
- Test: `tests/test_ask_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ask_endpoint.py
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from gateway.app import app
import gateway.memory as mem_module
import gateway.knowledge as know_module


def _mock_litellm(reply_text: str):
    """Patch httpx to return a fake non-streaming LiteLLM JSON response."""
    fake_json = {
        "choices": [{"message": {"role": "assistant", "content": reply_text}}]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_json
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return patch("httpx.AsyncClient", return_value=mock_client)


def test_ask_returns_reply():
    with patch.object(mem_module, "get_context_block", return_value=""), \
         patch.object(know_module, "get_knowledge_block", return_value=""), \
         _mock_litellm("I am Kitty, your personal AI."):
        client = TestClient(app)
        resp = client.post("/ask", json={"message": "Who are you?"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "I am Kitty, your personal AI."


def test_ask_empty_message_returns_400():
    client = TestClient(app)
    resp = client.post("/ask", json={"message": ""})
    assert resp.status_code == 400


def test_ask_missing_message_returns_422():
    client = TestClient(app)
    resp = client.post("/ask", json={})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_ask_endpoint.py -v
```
Expected: FAIL with `404 Not Found` (endpoint doesn't exist yet)

- [ ] **Step 3: Add `/ask` to gateway/app.py**

Add this after the `/brief` endpoint (around line 34):

```python
@app.post("/ask")
async def ask(request: Request):
    """Plain-JSON chat endpoint for iOS Shortcuts / scripts. No SSE."""
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="message is required")

    domain = classify_domain(message)
    system_prompt = load_prompt(domain)

    from gateway.memory import get_context_block
    from gateway.knowledge import get_knowledge_block
    memory_context = ""
    knowledge_context = ""
    try:
        memory_context = get_context_block(message, limit=5)
    except Exception:
        pass
    try:
        knowledge_context = get_knowledge_block(message, limit=3)
    except Exception:
        pass

    extra = "\n\n".join(filter(None, [memory_context, knowledge_context]))
    if extra:
        system_prompt = system_prompt + "\n\n" + extra

    model = "kitty-private" if domain == "health" else "kitty-default"

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{LITELLM_BASE}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
        resp.raise_for_status()
        data = resp.json()

    reply = data["choices"][0]["message"]["content"]
    return {"reply": reply}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/pytest tests/test_ask_endpoint.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add gateway/app.py tests/test_ask_endpoint.py
git commit -m "feat: Phase 13 — /ask endpoint for Siri Shortcuts"
```

---

### Task 2: iOS Shortcut documentation

**Files:**
- Create: `docs/SIRI_SHORTCUT.md`

- [ ] **Step 1: Write the setup guide**

```markdown
# Kitty Siri Shortcut Setup

## Prerequisites
- Tailscale running on Mac (Kitty at 100.84.78.1)
- `bash kitty_gateway/start_all.sh` run on Mac
- iOS Shortcuts app

## Build the Shortcut

Open **Shortcuts** app → "+" → name it **"Ask Kitty"**

Add these actions in order:

### 1. Dictate Text
- Action: **Dictate Text**
- Language: English
- Prompt: "What do you want to ask Kitty?"

### 2. Get Contents of URL
- Action: **Get Contents of URL**
- URL: `http://100.84.78.1:8000/ask`
- Method: **POST**
- Request Body: **JSON**
- Add field: Key = `message`, Value = **Dictated Text** (tap the variable)

### 3. Get Dictionary Value
- Action: **Get Dictionary Value**
- Key: `reply`
- Dictionary: **Contents of URL** (tap the variable)

### 4. Speak Text
- Action: **Speak Text**
- Text: **Dictionary Value** (tap the variable)

## Add to Siri
Shortcut settings → "Add to Siri" → say "Ask Kitty"

## Test
Say: "Hey Siri, Ask Kitty" → dictate "What do I have going on today?" → hear Kitty respond.

## Troubleshooting
- No response: check `curl http://100.84.78.1:8000/health` from phone browser
- Timeout: Mac may be asleep — check Energy Saver settings
- "Connection refused": run `bash kitty_gateway/start_all.sh` on Mac first
```

- [ ] **Step 2: Verify the file was written**

```bash
cat /Users/jacobbrizinski/Projects/kitty/docs/SIRI_SHORTCUT.md | head -10
```
Expected: prints the first 10 lines of the guide

- [ ] **Step 3: Live-test the `/ask` endpoint**

With the gateway running (`bash kitty_gateway/start_all.sh`):

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my name?"}' | python3 -m json.tool
```
Expected: `{"reply": "...Jacob..."}` — the reply should mention Jacob

- [ ] **Step 4: Commit**

```bash
git add docs/SIRI_SHORTCUT.md
git commit -m "docs: Phase 13 — Siri Shortcut setup guide"
```

---

### Task 3: Gate check

**Files:**
- Modify: `scripts/setup/gate-check.sh`

- [ ] **Step 1: Add Phase 13 gate**

Add this block to `gate-check.sh`:

```bash
if [ "$PHASE" = "13" ]; then
    echo "[ Siri Shortcut — /ask endpoint ]"
    check "/ask endpoint in app.py" \
        "grep -q 'def ask' /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
    check "/ask endpoint tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_ask_endpoint.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "SIRI_SHORTCUT.md exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/docs/SIRI_SHORTCUT.md"
    check "/ask returns 400 on empty message" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_ask_endpoint.py::test_ask_empty_message_returns_400 -q --tb=no 2>/dev/null | grep -q 'passed'"
fi
```

- [ ] **Step 2: Run gate check**

```bash
bash scripts/setup/gate-check.sh 13
```
Expected: Phase 13 COMPLETE ✓

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/gate-check.sh
git commit -m "feat: Phase 13 complete — gate check added"
```
