# KittyBuilder Intent Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Intent Compiler, Context Compiler, Worker Health Preflight, and Evidence Ledger around KittyBuilder so messy brain dumps become scoped, testable build contracts before execution.

**Architecture:** Keep KittyBuilder as the existing project-manager workbench. Add small focused modules under `src/builder/`, wire them into `scripts/builder_intake.py` first, then expose read-only KittyBuilder commands. Execution remains gated by approved specs and explicit flags.

**Tech Stack:** Python 3.12, dataclasses, JSONL, pytest, existing KittyBuilder token telemetry, optional Promptfoo evals after deterministic tests exist.

---

## File Structure

- Create: `src/builder/__init__.py`
- Create: `src/builder/contracts.py`
- Create: `src/builder/intent_compiler.py`
- Create: `src/builder/context_compiler.py`
- Create: `src/builder/worker_health.py`
- Create: `src/builder/evidence_ledger.py`
- Modify: `scripts/builder_intake.py`
- Modify: `scripts/kitty_builder.py`
- Create: `tests/builder/test_intent_compiler.py`
- Create: `tests/builder/test_context_compiler.py`
- Create: `tests/builder/test_worker_health.py`
- Create: `tests/builder/test_evidence_ledger.py`
- Modify: `tests/test_kitty_builder.py`
- Later optional: `promptfooconfig.yaml`
- Later optional: `evals/intent_compiler/*.jsonl`

Do not modify product runtime routes in this phase. This is a builder/control-layer change.

## Task 1: Contract Types

**Files:**
- Create: `src/builder/__init__.py`
- Create: `src/builder/contracts.py`
- Test: `tests/builder/test_intent_compiler.py`

- [ ] **Step 1: Write the failing contract serialization test**

Create `tests/builder/test_intent_compiler.py`:

```python
from src.builder.contracts import BuilderBrief


def test_builder_brief_round_trips_to_dict():
    brief = BuilderBrief(
        raw_input="fix command stuff and make sure it works",
        normalized_goal="Consolidate command handling behind CommandEngine.",
        non_goals=["Do not change UI styling."],
        success_criteria=["/api/command handles /stuck."],
        validation_commands=["venv/bin/python -m pytest tests/test_command_engine.py -q"],
        allowed_files=["src/core/command_engine.py"],
        forbidden_files=["garage-ui/"],
        assumptions=["Use existing Flask route contracts."],
        ambiguities=[],
        blocking_question="",
        context_targets=["CURRENT_FOCUS.md", "specs/unified-command-system-candidate-c.spec.md"],
        risk_level="medium",
        recommended_execution_mode="single_worker",
        handoff_prompt="Implement the approved CommandEngine spec.",
        confidence=0.82,
    )

    data = brief.to_dict()

    assert data["normalized_goal"] == "Consolidate command handling behind CommandEngine."
    assert data["risk_level"] == "medium"
    assert data["recommended_execution_mode"] == "single_worker"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_intent_compiler.py -q --tb=short
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.builder'`.

- [ ] **Step 3: Add contract dataclasses**

Create `src/builder/__init__.py`:

```python
"""Builder control-layer helpers for KittyBuilder."""
```

Create `src/builder/contracts.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


RiskLevel = Literal["low", "medium", "high"]
ExecutionMode = Literal[
    "answer_only",
    "intake_only",
    "scout",
    "single_worker",
    "parallel_workers",
    "review_gate",
    "human_question",
]


@dataclass(frozen=True)
class BuilderBrief:
    raw_input: str
    normalized_goal: str
    non_goals: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    blocking_question: str = ""
    context_targets: list[str] = field(default_factory=list)
    risk_level: RiskLevel = "medium"
    recommended_execution_mode: ExecutionMode = "intake_only"
    handoff_prompt: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_intent_compiler.py -q --tb=short
```

Expected: PASS.

## Task 2: Deterministic Intent Compiler

**Files:**
- Modify: `src/builder/intent_compiler.py`
- Modify: `tests/builder/test_intent_compiler.py`

- [ ] **Step 1: Add failing compiler tests**

Append to `tests/builder/test_intent_compiler.py`:

```python
from pathlib import Path

from src.builder.intent_compiler import compile_intent


def test_compile_intent_turns_brain_dump_into_contract(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text(
        "# Current Focus\n\n## Forbidden Work\n\n- MCP expansion\n- QLoRA\n",
        encoding="utf-8",
    )
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "unified-command-system-candidate-c.spec.md").write_text(
        "# Unified Command System Candidate C\n",
        encoding="utf-8",
    )

    brief = compile_intent(
        tmp_path,
        "continue the command system thing through kittybuilder, verify it works, do not do UI polish",
    )

    assert "command" in brief.normalized_goal.lower()
    assert "garage-ui/" in brief.forbidden_files
    assert "specs/unified-command-system-candidate-c.spec.md" in brief.context_targets
    assert brief.recommended_execution_mode in {"single_worker", "review_gate"}
    assert brief.blocking_question == ""


def test_compile_intent_asks_one_question_for_vague_cleanup(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text("# Current Focus\n", encoding="utf-8")

    brief = compile_intent(tmp_path, "clean up everything and make it better")

    assert brief.recommended_execution_mode == "human_question"
    assert brief.blocking_question
    assert len(brief.ambiguities) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_intent_compiler.py -q --tb=short
```

Expected: FAIL because `src.builder.intent_compiler` does not exist.

- [ ] **Step 3: Implement minimal compiler**

Create `src/builder/intent_compiler.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from src.builder.contracts import BuilderBrief


VAGUE_PATTERNS = ("clean up everything", "make it better", "fix everything", "optimize everything")


def compile_intent(project_root: str | Path, raw_input: str) -> BuilderBrief:
    root = Path(project_root).expanduser().resolve()
    raw = raw_input.strip()
    lower = raw.lower()

    forbidden_files: list[str] = []
    non_goals: list[str] = []
    context_targets = _context_targets(root, lower)

    if "do not do ui" in lower or "do not touch ui" in lower or "no ui" in lower or "ui polish" in lower:
        forbidden_files.append("garage-ui/")
        non_goals.append("Do not change UI styling or polish.")

    if any(pattern in lower for pattern in VAGUE_PATTERNS):
        return BuilderBrief(
            raw_input=raw,
            normalized_goal="Clarify the requested cleanup target.",
            ambiguities=["The request is too broad to scope safely."],
            blocking_question="What single target should KittyBuilder improve first?",
            context_targets=context_targets,
            risk_level="high",
            recommended_execution_mode="human_question",
            confidence=0.25,
        )

    goal = _goal_from_text(lower)
    mode = "single_worker" if "verify" in lower or "works" in lower else "intake_only"
    validation = ["bash scripts/run_gates.sh"] if (root / "scripts" / "run_gates.sh").exists() else []

    return BuilderBrief(
        raw_input=raw,
        normalized_goal=goal,
        non_goals=non_goals,
        success_criteria=["Implementation matches the compiled goal and validation passes."],
        validation_commands=validation,
        allowed_files=[],
        forbidden_files=forbidden_files,
        assumptions=["Use current repo authority docs and approved specs."],
        ambiguities=[],
        blocking_question="",
        context_targets=context_targets,
        risk_level="medium",
        recommended_execution_mode=mode,
        handoff_prompt=f"Execute this scoped goal: {goal}",
        confidence=0.75,
    )


def _goal_from_text(lower: str) -> str:
    if "command" in lower:
        return "Advance the Unified Command System through KittyBuilder with verification."
    if "kittybuilder" in lower:
        return "Improve KittyBuilder behavior with verification."
    return "Compile the request into one scoped KittyBuilder task."


def _context_targets(root: Path, lower: str) -> list[str]:
    targets = ["CURRENT_FOCUS.md", "TASKS.md", "docs/LAYER0_CONTROL_PLANE.md"]
    if "command" in lower:
        spec = root / "specs" / "unified-command-system-candidate-c.spec.md"
        if spec.exists():
            targets.append("specs/unified-command-system-candidate-c.spec.md")
    return list(dict.fromkeys(targets))
```

- [ ] **Step 4: Run tests**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_intent_compiler.py -q --tb=short
```

Expected: PASS.

## Task 3: Context Compiler

**Files:**
- Create: `src/builder/context_compiler.py`
- Create: `tests/builder/test_context_compiler.py`

- [ ] **Step 1: Write failing context compiler tests**

Create `tests/builder/test_context_compiler.py`:

```python
from src.builder.context_compiler import build_context_pack
from src.builder.contracts import BuilderBrief


def test_context_pack_keeps_static_rules_first_and_acceptance_last(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text("focus text\n" * 20, encoding="utf-8")

    brief = BuilderBrief(
        raw_input="do command work",
        normalized_goal="Advance command system.",
        success_criteria=["focused tests pass"],
        context_targets=["CURRENT_FOCUS.md"],
        recommended_execution_mode="single_worker",
    )

    pack = build_context_pack(tmp_path, brief, max_chars_per_file=80)

    assert pack.startswith("# KittyBuilder Context Pack")
    assert "## Static Rules" in pack
    assert "## Selected Context" in pack
    assert "## Final Acceptance Checklist" in pack
    assert "focused tests pass" in pack
    assert "[truncated]" in pack
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_context_compiler.py -q --tb=short
```

Expected: FAIL because `src.builder.context_compiler` does not exist.

- [ ] **Step 3: Implement context compiler**

Create `src/builder/context_compiler.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.builder.contracts import BuilderBrief


def build_context_pack(
    project_root: str | Path,
    brief: BuilderBrief,
    *,
    max_chars_per_file: int = 4000,
) -> str:
    root = Path(project_root).expanduser().resolve()
    lines = [
        "# KittyBuilder Context Pack",
        "",
        "## Static Rules",
        "- Follow AGENTS.md and docs/LAYER0_CONTROL_PLANE.md authority order.",
        "- Optimize for effectiveness per token, not cheap output alone.",
        "- Do not broaden scope beyond the compiled brief.",
        "",
        "## Compiled Goal",
        brief.normalized_goal,
        "",
        "## Selected Context",
    ]

    for rel in brief.context_targets:
        path = (root / rel).resolve()
        if not _inside(path, root) or not path.is_file():
            lines.extend([f"### {rel}", "[missing or outside project]"])
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n[truncated]"
        lines.extend([f"### {rel}", "```text", text, "```"])

    lines.extend(["", "## Final Acceptance Checklist"])
    for item in brief.success_criteria or ["Compiled goal is satisfied."]:
        lines.append(f"- {item}")
    for command in brief.validation_commands:
        lines.append(f"- Run: `{command}`")
    return "\n".join(lines).strip() + "\n"


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
```

- [ ] **Step 4: Run tests**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_context_compiler.py -q --tb=short
```

Expected: PASS.

## Task 4: Evidence Ledger

**Files:**
- Create: `src/builder/evidence_ledger.py`
- Create: `tests/builder/test_evidence_ledger.py`

- [ ] **Step 1: Write failing evidence ledger test**

Create `tests/builder/test_evidence_ledger.py`:

```python
import json

from src.builder.evidence_ledger import append_evidence


def test_append_evidence_writes_jsonl(tmp_path):
    ledger = tmp_path / "builder_evidence.jsonl"

    append_evidence(
        ledger,
        run_id="run-1",
        raw_input_hash="abc",
        outcome="recommended",
        workers=["single_worker"],
        files_changed=[],
        commands_run=["venv/bin/python -m pytest tests/builder -q"],
        risks=["not executed yet"],
    )

    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["run_id"] == "run-1"
    assert row["outcome"] == "recommended"
    assert row["commands_run"] == ["venv/bin/python -m pytest tests/builder -q"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_evidence_ledger.py -q --tb=short
```

Expected: FAIL because `src.builder.evidence_ledger` does not exist.

- [ ] **Step 3: Implement append-only ledger**

Create `src/builder/evidence_ledger.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def append_evidence(path: str | Path, **fields: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now().isoformat(timespec="seconds"), **fields}
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run test**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_evidence_ledger.py -q --tb=short
```

Expected: PASS.

## Task 5: Worker Health Preflight

**Files:**
- Create: `src/builder/worker_health.py`
- Create: `tests/builder/test_worker_health.py`

- [ ] **Step 1: Write failing worker health tests**

Create `tests/builder/test_worker_health.py`:

```python
from src.builder.worker_health import check_worker_health


def test_check_worker_health_reports_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)

    result = check_worker_health("not-real-cli")

    assert result.name == "not-real-cli"
    assert result.available is False
    assert "missing" in result.reason.lower()


def test_check_worker_health_reports_available_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    result = check_worker_health("python")

    assert result.available is True
    assert result.path == "/usr/bin/python"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_worker_health.py -q --tb=short
```

Expected: FAIL because `src.builder.worker_health` does not exist.

- [ ] **Step 3: Implement health check**

Create `src/builder/worker_health.py`:

```python
from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerHealth:
    name: str
    available: bool
    path: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "available": self.available,
            "path": self.path,
            "reason": self.reason,
        }


def check_worker_health(name: str) -> WorkerHealth:
    path = shutil.which(name)
    if not path:
        return WorkerHealth(name=name, available=False, reason="binary missing")
    return WorkerHealth(name=name, available=True, path=path, reason="binary found")
```

- [ ] **Step 4: Run test**

Run:

```bash
venv/bin/python -m pytest tests/builder/test_worker_health.py -q --tb=short
```

Expected: PASS.

## Task 6: Wire Compiler Into `builder_intake.py`

**Files:**
- Modify: `scripts/builder_intake.py`
- Create: `tests/test_builder_intake_compiler.py`

- [ ] **Step 1: Write failing CLI-level test**

Create `tests/test_builder_intake_compiler.py`:

```python
from scripts.builder_intake import compile_builder_brief


def test_compile_builder_brief_returns_dict(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text("# Current Focus\n", encoding="utf-8")

    data = compile_builder_brief(tmp_path, "continue command system and verify")

    assert data["raw_input"] == "continue command system and verify"
    assert "normalized_goal" in data
    assert "recommended_execution_mode" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/test_builder_intake_compiler.py -q --tb=short
```

Expected: FAIL because `compile_builder_brief` does not exist.

- [ ] **Step 3: Add wrapper in `scripts/builder_intake.py`**

Append near the existing public helper functions:

```python
def compile_builder_brief(project: str | Path, text: str) -> dict[str, object]:
    from src.builder.intent_compiler import compile_intent

    return compile_intent(project, text).to_dict()
```

- [ ] **Step 4: Run test**

Run:

```bash
venv/bin/python -m pytest tests/test_builder_intake_compiler.py -q --tb=short
```

Expected: PASS.

## Task 7: Add Read-Only KittyBuilder Commands

**Files:**
- Modify: `scripts/kitty_builder.py`
- Modify: `tests/test_kitty_builder.py`

- [ ] **Step 1: Add failing tests for read-only helpers**

Append to `tests/test_kitty_builder.py`:

```python
def test_compile_builder_request_returns_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "PROJECT_ROOT", tmp_path)
    (tmp_path / "CURRENT_FOCUS.md").write_text("# Current Focus\n", encoding="utf-8")

    text = kb.compile_builder_request("continue command system and verify")

    assert "recommended_execution_mode" in text
    assert "normalized_goal" in text


def test_worker_health_summary_marks_missing(monkeypatch):
    monkeypatch.setattr(kb, "_DELEGATE_ORDER", ("definitely-missing-worker",))

    text = kb.worker_health_summary()

    assert "definitely-missing-worker" in text
    assert "missing" in text.lower()
```

- [ ] **Step 2: Run focused tests to verify failure**

Run:

```bash
venv/bin/python -m pytest tests/test_kitty_builder.py::test_compile_builder_request_returns_brief tests/test_kitty_builder.py::test_worker_health_summary_marks_missing -q --tb=short
```

Expected: FAIL because helper functions do not exist.

- [ ] **Step 3: Add read-only helper functions**

Add to `scripts/kitty_builder.py` near other tool helpers:

```python
def compile_builder_request(text: str) -> str:
    """Compile a messy request into a structured BuilderBrief without writing files."""
    from src.builder.intent_compiler import compile_intent

    brief = compile_intent(PROJECT_ROOT, text)
    return json.dumps(brief.to_dict(), indent=2)


def worker_health_summary() -> str:
    """Return a read-only health summary for configured delegate workers."""
    from src.builder.worker_health import check_worker_health

    rows = [check_worker_health(name) for name in _DELEGATE_ORDER]
    lines = ["Worker health:"]
    for row in rows:
        status = "available" if row.available else "missing"
        detail = row.path or row.reason
        lines.append(f"- {row.name}: {status} ({detail})")
    return "\n".join(lines)
```

Register tools:

```python
TOOLS["compile_builder_request"] = compile_builder_request
TOOLS["worker_health_summary"] = worker_health_summary
```

Add interactive commands near `/health` and `/next`:

```python
elif inp.startswith("/compile "):
    print(compile_builder_request(inp.removeprefix("/compile ").strip()))
elif inp.lower() in ("/workers", "workers"):
    print(worker_health_summary())
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
venv/bin/python -m pytest tests/test_kitty_builder.py::test_compile_builder_request_returns_brief tests/test_kitty_builder.py::test_worker_health_summary_marks_missing -q --tb=short
```

Expected: PASS.

## Task 8: Evidence Ledger Hook For Recommendations

**Files:**
- Modify: `scripts/kitty_builder.py`
- Modify: `tests/test_kitty_builder.py`

- [ ] **Step 1: Add failing test for evidence hook**

Append to `tests/test_kitty_builder.py`:

```python
def test_record_builder_recommendation_writes_ledger(tmp_path, monkeypatch):
    target = tmp_path / "builder_evidence.jsonl"
    monkeypatch.setattr(kb, "BUILDER_EVIDENCE_FILE", target)

    kb.record_builder_recommendation(
        raw_input="continue command work",
        outcome="compiled",
        workers=["single_worker"],
        commands_run=["bash scripts/run_gates.sh"],
        risks=[],
    )

    assert target.exists()
    assert "continue command work" not in target.read_text(encoding="utf-8")
    assert "compiled" in target.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
venv/bin/python -m pytest tests/test_kitty_builder.py::test_record_builder_recommendation_writes_ledger -q --tb=short
```

Expected: FAIL because `record_builder_recommendation` does not exist.

- [ ] **Step 3: Implement hash-only ledger write**

Add near `TOKEN_USAGE_FILE`:

```python
BUILDER_EVIDENCE_FILE = PROJECT_ROOT / "data" / "builder_evidence.jsonl"
```

Add helper:

```python
def record_builder_recommendation(
    *,
    raw_input: str,
    outcome: str,
    workers: list[str],
    commands_run: list[str],
    risks: list[str],
) -> None:
    from src.builder.evidence_ledger import append_evidence

    append_evidence(
        BUILDER_EVIDENCE_FILE,
        run_id=datetime.now().strftime("builder-%Y%m%dT%H%M%S"),
        raw_input_hash=hashlib.sha256(raw_input.encode("utf-8")).hexdigest(),
        outcome=outcome,
        workers=workers,
        files_changed=[],
        commands_run=commands_run,
        risks=risks,
    )
```

- [ ] **Step 4: Run test**

Run:

```bash
venv/bin/python -m pytest tests/test_kitty_builder.py::test_record_builder_recommendation_writes_ledger -q --tb=short
```

Expected: PASS.

## Task 9: Promptfoo Evaluation Scaffold

**Files:**
- Create: `evals/intent_compiler/cases.jsonl`
- Create: `promptfooconfig.yaml`

- [ ] **Step 1: Create local eval cases**

Create `evals/intent_compiler/cases.jsonl`:

```jsonl
{"input":"clean up everything and make it better","expected_mode":"human_question"}
{"input":"continue unified command system through kittybuilder and verify it works","expected_mode":"single_worker"}
{"input":"research context engineering and summarize only","expected_mode":"scout"}
```

- [ ] **Step 2: Create Promptfoo config**

Create `promptfooconfig.yaml`:

```yaml
description: KittyBuilder intent compiler regression checks
prompts:
  - file://scripts/builder_intake.py
providers:
  - id: exec:venv/bin/python scripts/builder_intake.py --project . --text "{{input}}"
tests:
  - vars:
      input: clean up everything and make it better
    assert:
      - type: contains
        value: human_question
  - vars:
      input: continue unified command system through kittybuilder and verify it works
    assert:
      - type: contains
        value: single_worker
```

- [ ] **Step 3: Run Promptfoo only if installed**

Run:

```bash
command -v promptfoo && promptfoo eval || true
```

Expected: If Promptfoo is installed, evals run. If not installed, command exits without blocking Python implementation.

## Task 10: Final Verification

**Files:**
- All files touched in prior tasks.

- [ ] **Step 1: Run builder tests**

Run:

```bash
venv/bin/python -m pytest tests/builder tests/test_builder_intake_compiler.py tests/test_kitty_builder.py -q --tb=short
```

Expected: PASS.

- [ ] **Step 2: Run control-layer gate**

Run:

```bash
bash scripts/run_gates.sh
```

Expected: PASS. If blocked by unrelated dirty-tree or environment issue, record exact blocker and run the focused passing suite from Step 1.

- [ ] **Step 3: Check docs and diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Status shows only intended files plus any pre-existing unrelated dirty files.

## Self-Review Checklist

- [ ] The compiler preserves raw input only in memory/output, not in hash-only evidence logs.
- [ ] The compiler asks one blocking question for vague work.
- [ ] Context packs are bounded and cite file paths.
- [ ] Worker health checks are read-only.
- [ ] Evidence ledger is append-only JSONL.
- [ ] KittyBuilder commands are read-only unless existing `--execute` gates are used.
- [ ] No product runtime routes are changed.
- [ ] No agent is delegated by default.

## Execution Options

Plan complete. Recommended execution mode:

1. Subagent-Driven: one worker for contract/compiler modules, one worker for KittyBuilder wiring, one review pass.
2. Inline Execution: implement in one Codex 5.3 session with focused tests after each task.

Use option 2 if the dirty tree remains large, because shared-file coordination will be easier.

