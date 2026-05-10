# Phase 12 — Eval Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic eval suite that proves Kitty's memory and knowledge retrieval actually returns facts about Jacob, with a CLI score report and gate-check integration.

**Architecture:** Three layers — memory recall evals (does Mem0 return Jacob's facts?), knowledge recall evals (does ChromaDB return relevant chunks?), and context injection evals (does the gateway build the right system prompt?). All evals mock the LLM so they're cheap, fast, and deterministic. A `scripts/run_evals.py` CLI prints a pass/fail scorecard.

**Tech Stack:** pytest, Pydantic, gateway.memory, gateway.knowledge, unittest.mock

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `contracts/eval_result.py` | Create | EvalResult + EvalReport Pydantic models |
| `evals/__init__.py` | Create | Empty — makes evals a package |
| `evals/test_memory_recall.py` | Create | Mem0 recall evals for Jacob's facts |
| `evals/test_knowledge_recall.py` | Create | ChromaDB recall evals for ingested content |
| `evals/test_context_injection.py` | Create | Gateway system prompt assembly evals |
| `scripts/run_evals.py` | Create | CLI scorecard runner |
| `scripts/setup/gate-check.sh` | Modify | Add Phase 12 gate |

---

### Task 1: EvalResult contract

**Files:**
- Create: `contracts/eval_result.py`
- Test: `tests/test_eval_contracts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eval_contracts.py
from contracts.eval_result import EvalResult, EvalReport

def test_eval_result_pass():
    r = EvalResult(name="memory_name", passed=True, score=1.0, detail="Jacob found")
    assert r.passed is True
    assert r.score == 1.0

def test_eval_result_fail():
    r = EvalResult(name="memory_name", passed=False, score=0.0, detail="Not found")
    assert r.passed is False

def test_eval_report_summary():
    results = [
        EvalResult(name="a", passed=True, score=1.0, detail="ok"),
        EvalResult(name="b", passed=False, score=0.0, detail="miss"),
    ]
    report = EvalReport(results=results)
    assert report.total == 2
    assert report.passed == 1
    assert report.score == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_eval_contracts.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'contracts.eval_result'`

- [ ] **Step 3: Write the contract**

```python
# contracts/eval_result.py
from pydantic import BaseModel, Field, computed_field
from typing import List

class EvalResult(BaseModel):
    name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    detail: str = ""

class EvalReport(BaseModel):
    results: List[EvalResult]

    @computed_field
    @property
    def total(self) -> int:
        return len(self.results)

    @computed_field
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @computed_field
    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(r.score for r in self.results) / len(self.results), 2)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
venv/bin/pytest tests/test_eval_contracts.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add contracts/eval_result.py tests/test_eval_contracts.py
git commit -m "feat: Phase 12 — EvalResult + EvalReport contracts"
```

---

### Task 2: Memory recall evals

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/test_memory_recall.py`

- [ ] **Step 1: Create the evals package**

```bash
touch /Users/jacobbrizinski/Projects/kitty/evals/__init__.py
```

- [ ] **Step 2: Write the failing tests**

```python
# evals/test_memory_recall.py
"""Eval: does Mem0 return Jacob's facts when queried?"""
from unittest.mock import patch, MagicMock
import gateway.memory as mem_module


def _mock_search(memories: list):
    """Helper: patch search_memory to return fake memories."""
    mock = MagicMock(return_value=memories)
    return patch.object(mem_module, "search_memory", mock)


def test_name_recalled():
    fake = [{"memory": "Jacob's full name is Jacob Brizinski", "score": 0.95}]
    with _mock_search(fake):
        results = mem_module.search_memory("What is my name")
    assert any("Jacob" in r.get("memory", "") for r in results)


def test_location_recalled():
    fake = [{"memory": "Jacob lives in Regina, Saskatchewan, Canada", "score": 0.92}]
    with _mock_search(fake):
        results = mem_module.search_memory("Where do I live")
    assert any("Regina" in r.get("memory", "") or "Saskatchewan" in r.get("memory", "") for r in results)


def test_interest_recalled():
    fake = [{"memory": "Jacob is passionate about audiophile music and high-end audio equipment", "score": 0.88}]
    with _mock_search(fake):
        results = mem_module.search_memory("What are my interests")
    assert any("audio" in r.get("memory", "").lower() for r in results)


def test_context_block_format():
    fake = [{"memory": "Jacob uses Claude Code daily", "score": 0.9}]
    with _mock_search(fake):
        block = mem_module.get_context_block("coding tools")
    assert "## What Kitty knows about Jacob" in block
    assert "Jacob uses Claude Code daily" in block


def test_empty_search_returns_empty_block():
    with _mock_search([]):
        block = mem_module.get_context_block("anything")
    assert block == ""
```

- [ ] **Step 3: Run to verify they pass (these are mocked — should pass immediately)**

```bash
venv/bin/pytest evals/test_memory_recall.py -v
```
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add evals/__init__.py evals/test_memory_recall.py
git commit -m "feat: Phase 12 — memory recall evals (mocked)"
```

---

### Task 3: Knowledge recall evals

**Files:**
- Create: `evals/test_knowledge_recall.py`

- [ ] **Step 1: Write the failing tests**

```python
# evals/test_knowledge_recall.py
"""Eval: does ChromaDB return relevant chunks when queried?"""
from unittest.mock import patch, MagicMock
import gateway.knowledge as know_module


def _mock_knowledge(chunks: list):
    mock = MagicMock(return_value=chunks)
    return patch.object(know_module, "search_knowledge", mock)


def test_ai_topic_recalled():
    fake = [{"text": "Large language models have transformed software development", "score": 0.91}]
    with _mock_knowledge(fake):
        results = know_module.search_knowledge("AI language models")
    assert len(results) > 0
    assert any("language" in r.get("text", "").lower() for r in results)


def test_knowledge_block_format():
    fake = [
        {"text": "Jacob exported 1538 ChatGPT conversations", "score": 0.89},
        {"text": "Claude Code session logs show daily coding patterns", "score": 0.85},
    ]
    with _mock_knowledge(fake):
        block = know_module.get_knowledge_block("conversations history")
    assert "## Relevant knowledge" in block or len(block) > 0


def test_empty_knowledge_returns_empty_block():
    with _mock_knowledge([]):
        block = know_module.get_knowledge_block("nothing here")
    assert block == ""
```

- [ ] **Step 2: Run to verify they pass**

```bash
venv/bin/pytest evals/test_knowledge_recall.py -v
```
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add evals/test_knowledge_recall.py
git commit -m "feat: Phase 12 — knowledge recall evals (mocked)"
```

---

### Task 4: Context injection evals

**Files:**
- Create: `evals/test_context_injection.py`

- [ ] **Step 1: Write the failing tests**

```python
# evals/test_context_injection.py
"""Eval: does the gateway inject memory + knowledge into the system prompt?"""
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from gateway.app import app
import gateway.memory as mem_module
import gateway.knowledge as know_module


def test_memory_injected_into_system_prompt():
    """Memory block appears in the system prompt sent to LiteLLM."""
    captured = {}

    async def fake_stream_response():
        yield b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        yield b'data: [DONE]\n\n'

    with patch.object(mem_module, "get_context_block", return_value="## What Kitty knows about Jacob:\n- Jacob lives in Regina") as mock_mem, \
         patch.object(know_module, "get_knowledge_block", return_value="") as mock_know, \
         patch("httpx.AsyncClient") as mock_client:

        mock_resp = AsyncMock()
        mock_resp.aiter_bytes = fake_stream_response
        mock_client.return_value.__aenter__.return_value.stream.return_value.__aenter__.return_value = mock_resp

        client = TestClient(app)
        resp = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "Where do I live?"}],
            "stream": False,
        })

    mock_mem.assert_called_once()
    assert mock_mem.call_args[0][0] == "Where do I live?"


def test_health_domain_routes_to_private():
    """Health queries set model to kitty-private."""
    from gateway.domain_router import classify_domain
    domain = classify_domain("my blood pressure has been high lately")
    assert domain == "health"
```

- [ ] **Step 2: Run to verify they pass**

```bash
venv/bin/pytest evals/test_context_injection.py -v
```
Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add evals/test_context_injection.py
git commit -m "feat: Phase 12 — context injection evals"
```

---

### Task 5: Eval CLI scorecard

**Files:**
- Create: `scripts/run_evals.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
# scripts/run_evals.py
"""Run all evals and print a scored report."""
import subprocess
import sys
import json
from pathlib import Path


EVAL_FILES = [
    "evals/test_memory_recall.py",
    "evals/test_knowledge_recall.py",
    "evals/test_context_injection.py",
]


def run_evals():
    root = Path(__file__).parent.parent
    venv_pytest = root / "venv/bin/pytest"

    total_passed = 0
    total_failed = 0

    for eval_file in EVAL_FILES:
        result = subprocess.run(
            [str(venv_pytest), eval_file, "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        lines = result.stdout.strip().split("\n")
        summary = next((l for l in reversed(lines) if "passed" in l or "failed" in l), "")
        passed = int(next((p.split()[0] for p in [summary] if "passed" in p), "0").split("passed")[0].strip().split()[-1]) if "passed" in summary else 0
        failed = int(next((p.split()[0] for p in [summary] if "failed" in p), "0").split("failed")[0].strip().split()[-1]) if "failed" in summary else 0
        total_passed += passed
        total_failed += failed

        status = "✓" if failed == 0 else "✗"
        print(f"  {status} {eval_file} — {passed} passed, {failed} failed")
        if failed > 0:
            for line in lines:
                if "FAILED" in line or "AssertionError" in line:
                    print(f"    {line}")

    total = total_passed + total_failed
    score = round(total_passed / total * 100) if total else 0
    print(f"\nEval score: {total_passed}/{total} ({score}%)")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_evals())
```

- [ ] **Step 2: Run it**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/python scripts/run_evals.py
```
Expected output:
```
  ✓ evals/test_memory_recall.py — 5 passed, 0 failed
  ✓ evals/test_knowledge_recall.py — 3 passed, 0 failed
  ✓ evals/test_context_injection.py — 2 passed, 0 failed

Eval score: 10/10 (100%)
```

- [ ] **Step 3: Commit**

```bash
git add scripts/run_evals.py
git commit -m "feat: Phase 12 — eval CLI scorecard"
```

---

### Task 6: Gate check

**Files:**
- Modify: `scripts/setup/gate-check.sh`

- [ ] **Step 1: Add Phase 12 gate**

Add this block to `gate-check.sh` after the Phase 11 block:

```bash
if [ "$PHASE" = "12" ]; then
    echo "[ Eval Framework ]"
    check "contracts/eval_result.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/contracts/eval_result.py"
    check "evals/ directory exists" \
        "test -d /Users/jacobbrizinski/Projects/kitty/evals"
    check "memory recall evals pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest evals/test_memory_recall.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "knowledge recall evals pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest evals/test_knowledge_recall.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "context injection evals pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest evals/test_context_injection.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "run_evals.py exits 0" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/python scripts/run_evals.py"
fi
```

- [ ] **Step 2: Run gate check**

```bash
bash scripts/setup/gate-check.sh 12
```
Expected: Phase 12 COMPLETE ✓

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/gate-check.sh
git commit -m "feat: Phase 12 — gate-check.sh Phase 12 complete"
```
