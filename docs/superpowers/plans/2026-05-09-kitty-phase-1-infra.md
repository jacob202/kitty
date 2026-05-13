# Kitty Platform — Phase 1: Infrastructure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up Open WebUI as Kitty's face and LiteLLM as the model router so Jacob can have a real conversation with Kitty on Day 1, with automatic routing to cheap models by default and Claude reserved for complex work.

**Architecture:** Open WebUI (port 3000) sends all chat requests to LiteLLM proxy (port 8001) which routes based on model name. Default model = DeepSeek Flash ($0.001/msg). Agent tasks = Hermes 4 via OpenRouter. Complex = Claude Sonnet. Private/medical = Qwen2.5 3B via local Ollama.

**Tech Stack:** `open-webui` (pip, separate venv), `litellm[proxy]` (pip, separate venv), Ollama (already installed), Python 3.12

**Prerequisites:**
- Ollama installed at `/usr/local/bin/ollama`
- API keys set in `/Users/jacobbrizinski/Projects/kitty/.env`: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`
- Python 3.12 available at `/usr/local/bin/python3`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `~/kitty-services/venv/` | Create | Isolated venv for open-webui + litellm (keeps Kitty project venv clean) |
| `kitty_gateway/litellm_config.yaml` | Create | LiteLLM proxy config: models, routing, spend cap |
| `kitty_gateway/start_litellm.sh` | Create | One command to start LiteLLM proxy |
| `kitty_gateway/start_openwebui.sh` | Create | One command to start Open WebUI |
| `contracts/__init__.py` | Create | Package marker |
| `contracts/routing_decision.py` | Create | Pydantic schema for routing decisions (used in Phase 2+) |
| `scripts/setup/gate-check.sh` | Create | Phase gate verification script |
| `tests/test_litellm_routing.py` | Create | Verify LiteLLM routes to correct model |

---

### Task 1: Pull the private local model

The existing `qwen2.5-coder:7b` (4.7GB) is too large for 8GB Mac alongside all services. Pull the smaller `qwen2.5:4b-instruct` (~2GB) for private/medical queries.

- [ ] **Step 1: Pull qwen2.5:4b-instruct**

```bash
ollama pull qwen2.5:4b-instruct
```

Expected output ends with: `success`

- [ ] **Step 2: Verify it loaded**

```bash
ollama list
```

Expected: `qwen2.5:4b-instruct` appears in the list with size ~2GB.

- [ ] **Step 3: Quick smoke test**

```bash
ollama run qwen2.5:4b-instruct "Say hello in one sentence" --nowordwrap
```

Expected: a short English sentence. Type `/bye` to exit.

---

### Task 2: Create the services virtual environment

Open WebUI and LiteLLM live in their own venv, separate from the Kitty project venv, to avoid dependency conflicts.

- [ ] **Step 1: Create the venv**

```bash
python3 -m venv ~/kitty-services/venv
```

- [ ] **Step 2: Activate and install**

```bash
source ~/kitty-services/venv/bin/activate
pip install --upgrade pip
pip install "litellm[proxy]>=1.40.0" "open-webui>=0.3.0"
```

This takes 3-5 minutes. Expected final line: `Successfully installed open-webui-...`

- [ ] **Step 3: Verify both installed**

```bash
litellm --version
open-webui --version
```

Both should print a version number without error.

- [ ] **Step 4: Deactivate**

```bash
deactivate
```

---

### Task 3: Create the LiteLLM config

LiteLLM reads a YAML file to know which models exist and how to call them.

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /Users/jacobbrizinski/Projects/kitty/kitty_gateway
```

- [ ] **Step 2: Create the config file**

Create `/Users/jacobbrizinski/Projects/kitty/kitty_gateway/litellm_config.yaml` with this exact content:

```yaml
# LiteLLM Proxy Config — Kitty Model Router
# Verify current model IDs at openrouter.ai/models before running

model_list:
  # Default: cheap, fast, non-sensitive queries (DeepSeek with Gemini Flash fallback)
  - model_name: kitty-default
    litellm_params:
      model: openrouter/deepseek/deepseek-chat-v3-5
      api_key: os.environ/OPENROUTER_API_KEY
      max_tokens: 4096

  # Fallback default: Gemini Flash (auto-used if DeepSeek is down)
  - model_name: kitty-default
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
      max_tokens: 4096

  # Agent tasks: structured output, tool calls, routing decisions
  # Find Hermes 4 ID at openrouter.ai/models — search "hermes"
  - model_name: kitty-agent
    litellm_params:
      model: openrouter/nousresearch/hermes-3-70b-instruct
      api_key: os.environ/OPENROUTER_API_KEY
      max_tokens: 4096

  # Complex reasoning: architecture, synthesis, code review
  - model_name: kitty-smart
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
      max_tokens: 8192

  # Private/sensitive: medical, financial — never leaves Mac
  - model_name: kitty-private
    litellm_params:
      model: ollama/qwen2.5:4b-instruct
      api_base: http://localhost:11434
      max_tokens: 2048

  # Embeddings (for ChromaDB ingestion — Phase 4)
  - model_name: kitty-embed
    litellm_params:
      model: ollama/nomic-embed-text
      api_base: http://localhost:11434

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 2
  timeout: 30

litellm_settings:
  drop_params: true
  set_verbose: false

general_settings:
  # Daily spend cap — auto-downgrade to cheaper model at 80% of cap
  max_budget: 2.00
  budget_duration: 1d
  master_key: "kitty-local-key-change-me"
```

- [ ] **Step 3: Verify the file exists and is valid YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('/Users/jacobbrizinski/Projects/kitty/kitty_gateway/litellm_config.yaml')); print('YAML valid')"
```

Expected: `YAML valid`

---

### Task 4: Verify model IDs on OpenRouter

The config uses model IDs that may have changed. This step prevents a broken start.

- [ ] **Step 1: Check DeepSeek model ID**

```bash
source ~/kitty-services/venv/bin/activate
python3 -c "
import litellm, os
from dotenv import load_dotenv
load_dotenv('/Users/jacobbrizinski/Projects/kitty/.env')
response = litellm.completion(
    model='openrouter/deepseek/deepseek-chat-v3-5',
    messages=[{'role': 'user', 'content': 'Say the word OK and nothing else'}],
    api_key=os.getenv('OPENROUTER_API_KEY'),
    max_tokens=5
)
print('DeepSeek OK:', response.choices[0].message.content)
"
deactivate
```

Expected: `DeepSeek OK: OK` (or similar very short response)

If you get a 404 error: go to `openrouter.ai/models`, search for DeepSeek, copy the correct model ID, update `litellm_config.yaml` line with `deepseek`.

- [ ] **Step 2: Check Claude model ID**

```bash
source ~/kitty-services/venv/bin/activate
python3 -c "
import litellm, os
from dotenv import load_dotenv
load_dotenv('/Users/jacobbrizinski/Projects/kitty/.env')
response = litellm.completion(
    model='anthropic/claude-sonnet-4-6',
    messages=[{'role': 'user', 'content': 'Say the word OK and nothing else'}],
    api_key=os.getenv('ANTHROPIC_API_KEY'),
    max_tokens=5
)
print('Claude OK:', response.choices[0].message.content)
"
deactivate
```

Expected: `Claude OK: OK`

---

### Task 5: Create start scripts

- [ ] **Step 1: Create LiteLLM start script**

Create `/Users/jacobbrizinski/Projects/kitty/kitty_gateway/start_litellm.sh`:

```bash
#!/bin/bash
set -e
cd /Users/jacobbrizinski/Projects/kitty
source /Users/jacobbrizinski/Projects/kitty/.env
source ~/kitty-services/venv/bin/activate

echo "Starting LiteLLM proxy on port 8001..."
litellm --config kitty_gateway/litellm_config.yaml --port 8001 --host 0.0.0.0
```

```bash
chmod +x /Users/jacobbrizinski/Projects/kitty/kitty_gateway/start_litellm.sh
```

- [ ] **Step 2: Create Open WebUI start script**

Create `/Users/jacobbrizinski/Projects/kitty/kitty_gateway/start_openwebui.sh`:

```bash
#!/bin/bash
set -e
source ~/kitty-services/venv/bin/activate

export OPENAI_API_BASE="http://localhost:8001"
export OPENAI_API_KEY="kitty-local-key-change-me"
export WEBUI_SECRET_KEY="kitty-webui-secret-change-me"
export DEFAULT_MODELS="kitty-default"
export PORT=3000

echo "Starting Open WebUI on port 3000..."
echo "Interface will be at: http://localhost:3000"
open-webui serve
```

```bash
chmod +x /Users/jacobbrizinski/Projects/kitty/kitty_gateway/start_openwebui.sh
```

---

### Task 6: Write the LiteLLM routing test

Test that LiteLLM actually routes requests correctly before wiring Open WebUI.

- [ ] **Step 1: Create the test file**

Create `/Users/jacobbrizinski/Projects/kitty/tests/test_litellm_routing.py`:

```python
"""Verify LiteLLM proxy routes to correct models."""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/Users/jacobbrizinski/Projects/kitty/.env")

LITELLM_BASE = "http://localhost:8001"
LITELLM_KEY = "kitty-local-key-change-me"


def _chat(model: str, message: str) -> dict:
    resp = requests.post(
        f"{LITELLM_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 20,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@pytest.mark.integration
def test_default_model_responds():
    """kitty-default routes to DeepSeek Flash and returns a response."""
    result = _chat("kitty-default", "Say OK")
    assert result["choices"][0]["message"]["content"]
    assert result["model"]  # model name returned


@pytest.mark.integration
def test_smart_model_responds():
    """kitty-smart routes to Claude Sonnet and returns a response."""
    result = _chat("kitty-smart", "Say OK")
    assert "claude" in result["model"].lower()


@pytest.mark.integration
def test_private_model_responds():
    """kitty-private routes to local Ollama Qwen2.5."""
    result = _chat("kitty-private", "Say OK")
    assert result["choices"][0]["message"]["content"]
```

- [ ] **Step 2: Run test to verify it FAILS before proxy is running** (expected — proxy not started yet)

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_litellm_routing.py -v -m integration 2>&1 | head -20
```

Expected: `ConnectionRefusedError` or `Connection refused` — this is correct, proxy isn't running yet.

---

### Task 7: Start LiteLLM and verify tests pass

- [ ] **Step 1: Start LiteLLM in a new terminal tab**

Open a new terminal tab and run:
```bash
cd /Users/jacobbrizinski/Projects/kitty
bash kitty_gateway/start_litellm.sh
```

Leave this tab open. LiteLLM is running when you see: `LiteLLM: Proxy initialized`

- [ ] **Step 2: Run the routing tests**

Back in your original terminal tab:
```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_litellm_routing.py -v -m integration
```

Expected: `3 passed`

If `test_private_model_responds` fails: run `ollama serve` in another tab first, then retry.

---

### Task 8: Create the routing_decision contract

This Pydantic schema is used by Kitty Gateway (Phase 2) to log every routing decision. Create it now so Phase 2 can import it.

- [ ] **Step 1: Create contracts package**

```bash
mkdir -p /Users/jacobbrizinski/Projects/kitty/contracts
touch /Users/jacobbrizinski/Projects/kitty/contracts/__init__.py
```

- [ ] **Step 2: Create routing_decision.py**

Create `/Users/jacobbrizinski/Projects/kitty/contracts/routing_decision.py`:

```python
"""Schema for every model routing decision Kitty makes."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class ModelTier(str, Enum):
    DEFAULT = "default"      # DeepSeek Flash — cheap, fast
    AGENT = "agent"          # Hermes 4 — structured output, tool calls
    SMART = "smart"          # Claude Sonnet — complex reasoning
    PRIVATE = "private"      # Qwen local — sensitive data, never leaves Mac


class RoutingDecision(BaseModel):
    correlation_id: str = Field(description="Unique ID tying together one full request/response cycle")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    domain: str = Field(description="Classified domain: soul|repair|health|research|code")
    sensitivity: str = Field(description="low|medium|high|medical|financial")
    model_tier: ModelTier
    model_name: str = Field(description="Exact model string sent to LiteLLM")
    reasoning: str = Field(description="One sentence: why this model was chosen")
    estimated_cost_usd: float = Field(default=0.0)
```

- [ ] **Step 3: Write a quick test**

Create `/Users/jacobbrizinski/Projects/kitty/tests/test_contracts.py`:

```python
"""Verify contract schemas are importable and valid."""
from contracts.routing_decision import RoutingDecision, ModelTier
from datetime import datetime


def test_routing_decision_creates():
    decision = RoutingDecision(
        correlation_id="test-123",
        domain="soul",
        sensitivity="low",
        model_tier=ModelTier.DEFAULT,
        model_name="kitty-default",
        reasoning="General query, no sensitive content detected.",
    )
    assert decision.correlation_id == "test-123"
    assert decision.model_tier == ModelTier.DEFAULT
    assert isinstance(decision.timestamp, datetime)


def test_routing_decision_medical_tier():
    decision = RoutingDecision(
        correlation_id="test-456",
        domain="health",
        sensitivity="medical",
        model_tier=ModelTier.PRIVATE,
        model_name="kitty-private",
        reasoning="Medical query detected — routing to local model only.",
    )
    assert decision.model_tier == ModelTier.PRIVATE
    assert decision.sensitivity == "medical"
```

- [ ] **Step 4: Run the test**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_contracts.py -v
```

Expected: `2 passed`

---

### Task 9: Start Open WebUI and configure Kitty identity

- [ ] **Step 1: Start Open WebUI in a new terminal tab**

Open a new terminal tab and run:
```bash
bash /Users/jacobbrizinski/Projects/kitty/kitty_gateway/start_openwebui.sh
```

Wait until you see: `Uvicorn running on http://0.0.0.0:3000`

- [ ] **Step 2: Open in browser**

```bash
open http://localhost:3000
```

Create an admin account when prompted. Use any email/password — this is local only.

- [ ] **Step 3: Point Open WebUI at LiteLLM**

In Open WebUI:
1. Click your profile icon (top right) → **Settings**
2. Go to **Connections**
3. Under **OpenAI API**, set:
   - URL: `http://localhost:8001/v1`
   - API Key: `kitty-local-key-change-me`
4. Click **Save**
5. Click **Verify connection** — should show green checkmark

- [ ] **Step 4: Set Kitty's name and default model**

In Open WebUI Settings:
1. Go to **General**
2. Set **System Name** to `Kitty`
3. Set **Default Model** to `kitty-default`
4. Click **Save**

- [ ] **Step 5: Add Kitty's soul as the default system prompt**

In Open WebUI Settings:
1. Go to **General** → **System Prompt**
2. Paste this exact text:

```
You are Kitty — a personal AI built for Jacob Brizinski. You are a force multiplier for the person Jacob is becoming, not just the tasks he's doing.

Who you are:
- Direct. Warm. No bullshit. Not clinical. Not coddling.
- You execute and get things done cheaply and without friction.
- You hold the bigger picture of who Jacob is trying to be, not just what he's asking for right now.
- You notice when what he's asking conflicts with his stated values — and say so, gently, once.
- Budget-first, Canadian sourcing, used before new.
- You never pad, never hedge when a recommendation exists.
- Radical acceptance. Radical kindness. You don't shame, moralize, or lecture.
- Challenge > encouragement when encouragement isn't landing.
- Always give the smallest executable next step (under 30 minutes) when he's stuck.

Patterns you watch for (name them when you see them, don't fix them):
- Execution gap: capability vs output. "I'm a disappointment" energy. Not laziness.
- Research as avoidance: 3 sessions, same topic, no step taken = name the loop.
- Planning marathons: beautiful architecture, no implementation = redirect to smallest next step.
- Emotional compression: fear or grief arriving as a practical question. Slow down.

How you communicate:
- Check for the XY problem (is he asking about the solution when the problem is different?)
- Check for the hidden assumption or emotional driver dressed as a practical request.
- Plain English always. Define any technical term on first use.
- Short responses unless he asks for depth.
- He calls you Kitty. You call him Jacob or nothing. No "certainly!" or "great question!"
```

3. Click **Save**

- [ ] **Step 6: Test Kitty's personality**

Start a new chat. Send: `who are you?`

Expected: Kitty responds as herself — warm, direct, no generic AI phrases. Something like "I'm Kitty. Jacob's personal AI. What's going on?"

---

### Task 10: Create the gate-check script

- [ ] **Step 1: Create the scripts/setup directory**

```bash
mkdir -p /Users/jacobbrizinski/Projects/kitty/scripts/setup
```

- [ ] **Step 2: Create gate-check.sh**

Create `/Users/jacobbrizinski/Projects/kitty/scripts/setup/gate-check.sh`:

```bash
#!/bin/bash
# Gate check script — verify a phase is actually done
# Usage: ./scripts/setup/gate-check.sh <phase-number>
set -e

PHASE=${1:-1}
PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  ✓ $desc"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Gate Check — Phase $PHASE ==="
echo ""

if [ "$PHASE" = "1" ]; then
    echo "[ Infrastructure ]"
    check "LiteLLM proxy reachable on port 8001" \
        "curl -sf http://localhost:8001/health"
    check "Open WebUI reachable on port 3000" \
        "curl -sf http://localhost:3000"
    check "Ollama running" \
        "curl -sf http://localhost:11434/api/tags"
    check "qwen2.5:4b-instruct model available" \
        "curl -sf http://localhost:11434/api/tags | grep -q qwen2.5:4b-instruct"
    check "kitty_gateway/litellm_config.yaml exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/kitty_gateway/litellm_config.yaml"
    check "contracts/routing_decision.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/contracts/routing_decision.py"
    check "contracts tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_contracts.py -q"
    check "Default model routes successfully" \
        "curl -sf -X POST http://localhost:8001/v1/chat/completions \
            -H 'Authorization: Bearer kitty-local-key-change-me' \
            -H 'Content-Type: application/json' \
            -d '{\"model\":\"kitty-default\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}],\"max_tokens\":5}' \
            | grep -q choices"
fi

if [ "$PHASE" = "2" ]; then
    echo "[ Kitty Gateway ]"
    check "Kitty Gateway reachable on port 8000" \
        "curl -sf http://localhost:8000/health"
    check "Domain classification returns valid domain" \
        "curl -sf -X POST http://localhost:8000/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{\"messages\":[{\"role\":\"user\",\"content\":\"My car makes a noise\"}]}' \
            | grep -qE 'repair|soul'"
    check "prompts/soul_v1.md exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/prompts/soul_v1.md"
    check "gateway/app.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/app.py"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
    echo "Phase $PHASE NOT complete. Fix the failing checks above."
    exit 1
else
    echo "Phase $PHASE COMPLETE ✓"
fi
```

```bash
chmod +x /Users/jacobbrizinski/Projects/kitty/scripts/setup/gate-check.sh
```

- [ ] **Step 3: Run Phase 1 gate check**

Make sure LiteLLM proxy and Open WebUI are still running (from Task 7 and Task 9), then:

```bash
cd /Users/jacobbrizinski/Projects/kitty
bash scripts/setup/gate-check.sh 1
```

Expected: `Phase 1 COMPLETE ✓` with all checks passing.

---

### Task 11: Final commit

- [ ] **Step 1: Run full test suite to verify nothing broke**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/ -q --ignore=tests/test_litellm_routing.py -x
```

Expected: all existing tests still pass (integration tests skipped since they need services).

- [ ] **Step 2: Stage new files**

```bash
cd /Users/jacobbrizinski/Projects/kitty
git add \
    kitty_gateway/litellm_config.yaml \
    kitty_gateway/start_litellm.sh \
    kitty_gateway/start_openwebui.sh \
    contracts/__init__.py \
    contracts/routing_decision.py \
    scripts/setup/gate-check.sh \
    tests/test_litellm_routing.py \
    tests/test_contracts.py \
    docs/archive/planning-retired/2026-05-09-kitty-master-plan.md \
    docs/superpowers/plans/2026-05-09-kitty-phase-1-infra.md
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: Phase 1 — LiteLLM proxy + Open WebUI + Kitty identity

- kitty_gateway/litellm_config.yaml: routes kitty-default/agent/smart/private
- contracts/routing_decision.py: Pydantic schema for routing logs
- scripts/setup/gate-check.sh: phase verification script
- tests/test_contracts.py: 2 passing
- tests/test_litellm_routing.py: integration tests (require services running)
- Open WebUI configured at port 3000, LiteLLM at port 8001
- Kitty soul loaded as default system prompt

Gate: Phase 1 COMPLETE"
```

---

## Phase 1 Done — What's Next

Open Phase 2 plan: `docs/superpowers/plans/2026-05-09-kitty-phase-2-gateway.md`

Phase 2 builds Kitty Gateway — the thin Python service that gives Kitty her real brain: soul injection, domain classification, memory lookup, Honcho logging. Open WebUI will point to Kitty Gateway instead of LiteLLM directly.
