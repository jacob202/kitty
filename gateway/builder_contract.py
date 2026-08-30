"""Builder contract — validate and run Ideal-State-Criteria (ISC) checks.

A contract is a goal + a list of binary success criteria + optional
validation commands. This module validates a contract's structure and
optionally runs it against the canonical ISC machinery in
:mod:`gateway.builder_isc`.

Layer 1A: contract validate is safe, read-only coordination.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from gateway import builder_isc as builder_core

logger = logging.getLogger("kitty.builder_contract")


class ContractError(RuntimeError):
    """Malformed or un-runnable builder contract."""


def validate_contract(spec: dict[str, Any]) -> list[str]:
    """Return a list of validation errors; empty list means the contract is valid."""
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["contract must be a JSON object"]
    goal = spec.get("goal")
    if not goal or not isinstance(goal, str) or not goal.strip():
        errors.append("contract.goal is required and must be a non-empty string")
    criteria = spec.get("criteria")
    if criteria is None:
        pass
    elif not isinstance(criteria, list) or not all(isinstance(c, str) for c in criteria):
        errors.append("contract.criteria must be a list of strings")
    commands = spec.get("validation_commands", [])
    if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
        errors.append("contract.validation_commands must be a list of strings")
    return errors


def _workflow_string_list(value: Any, *, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ContractError(f"{label} must be a list of non-empty strings")
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ContractError(f"{label} must not contain duplicates")
    return normalized


def compile_workflow(spec: dict[str, Any]) -> dict[str, Any]:
    """Compile a Builder contract into explicit artifact/control-flow steps.

    The compiler is deliberately deterministic. It does not ask a model to
    invent a workflow: authored steps are normalized and checked, while legacy
    contracts become one explicit ``execute`` step for incremental adoption.
    """
    errors = validate_contract(spec)
    if errors:
        raise ContractError("; ".join(errors))

    inputs = _workflow_string_list(spec.get("inputs"), label="contract.inputs")
    raw_steps = spec.get("steps")
    if raw_steps is None:
        return {
            "entry_step": "execute",
            "inputs": inputs,
            "steps": [
                {
                    "id": "execute",
                    "instruction": spec["goal"].strip(),
                    "requires": list(inputs),
                    "produces": ["result"],
                    "validation_commands": _workflow_string_list(
                        spec.get("validation_commands", []),
                        label="contract.validation_commands",
                    ),
                    "on_success": None,
                }
            ],
        }

    if not isinstance(raw_steps, list) or not raw_steps:
        raise ContractError("contract.steps must be a non-empty list when provided")
    if not all(isinstance(step, dict) for step in raw_steps):
        raise ContractError("contract.steps must contain only JSON objects")

    ids: list[str] = []
    for index, raw in enumerate(raw_steps):
        step_id = raw.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise ContractError(f"contract.steps[{index}].id must be a non-empty string")
        step_id = step_id.strip()
        if step_id in ids:
            raise ContractError(f"duplicate step id: {step_id!r}")
        ids.append(step_id)

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps):
        instruction = raw.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ContractError(
                f"contract.steps[{index}].instruction must be a non-empty string"
            )
        if "on_success" in raw:
            successor = raw["on_success"]
        else:
            successor = ids[index + 1] if index + 1 < len(ids) else None
        if successor is not None and (
            not isinstance(successor, str) or not successor.strip()
        ):
            raise ContractError(
                f"contract.steps[{index}].on_success must be null or a non-empty step id"
            )
        successor = successor.strip() if isinstance(successor, str) else None
        if successor is not None and successor not in ids:
            raise ContractError(
                f"step {ids[index]!r} has unknown on_success target {successor!r}"
            )
        normalized.append(
            {
                "id": ids[index],
                "instruction": instruction.strip(),
                "requires": _workflow_string_list(
                    raw.get("requires"), label=f"step {ids[index]!r}.requires"
                ),
                "produces": _workflow_string_list(
                    raw.get("produces"), label=f"step {ids[index]!r}.produces"
                ),
                "validation_commands": _workflow_string_list(
                    raw.get("validation_commands"),
                    label=f"step {ids[index]!r}.validation_commands",
                ),
                "on_success": successor,
            }
        )

    by_id = {step["id"]: step for step in normalized}
    available = set(inputs)
    visited: list[str] = []
    current: str | None = ids[0]
    while current is not None:
        if current in visited:
            cycle = " -> ".join([*visited, current])
            raise ContractError(f"workflow contains a cycle: {cycle}")
        step = by_id[current]
        missing = [item for item in step["requires"] if item not in available]
        if missing:
            raise ContractError(
                f"step {current!r} requires unavailable artifact(s): {missing}"
            )
        visited.append(current)
        available.update(step["produces"])
        current = step["on_success"]

    if len(visited) != len(normalized):
        unreachable = [step_id for step_id in ids if step_id not in visited]
        raise ContractError(f"workflow contains unreachable step(s): {unreachable}")

    return {"entry_step": ids[0], "inputs": inputs, "steps": normalized}


def _run_command(cmd: str, cwd: Path | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """Run one shell command and return structured results."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return {
            "command": cmd,
            "passed": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:500],
        }
    except subprocess.TimeoutExpired:
        return {
            "command": cmd,
            "passed": False,
            "error": f"timed out after {timeout:.0f}s",
        }
    except Exception as exc:
        return {"command": cmd, "passed": False, "error": str(exc)}


def run_contract(
    spec: dict[str, Any],
    *,
    cwd: Path | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    """Validate and run a builder contract.

    Returns a dict with:
      - valid: bool
      - goal: str
      - criteria: list[dict] (checked results)
      - command_results: list[dict]
      - passed: bool
    """
    errors = validate_contract(spec)
    if errors:
        raise ContractError("; ".join(errors))

    workflow = compile_workflow(spec)
    goal = spec["goal"].strip()
    criteria_in = spec.get("criteria") or builder_core.derive_criteria(goal)
    commands = spec.get("validation_commands", [])

    command_results = []
    for cmd in commands:
        command_results.append(_run_command(cmd, cwd=cwd))

    all_command_output = "\n".join(
        f"$ {r['command']}\n{r.get('stdout', '')}\n{r.get('stderr', '')}"
        for r in command_results
    )

    evidence_text = evidence or all_command_output
    if not evidence_text.strip():
        evidence_text = f"Goal: {goal}\nNo validation evidence supplied."

    checked = builder_core.check_criteria(goal, criteria_in, evidence_text)
    passed = builder_core.all_criteria_passed(checked) and all(
        r.get("passed") for r in command_results
    )

    return {
        "valid": True,
        "goal": goal,
        "workflow": workflow,
        "criteria": checked,
        "command_results": command_results,
        "passed": passed,
    }


def load_contract(path: Path) -> dict[str, Any]:
    """Load a contract from a JSON or markdown file.

    For markdown, looks for a fenced JSON block under a ``## Contract`` header.
    """
    text = Path(path).read_text(encoding="utf-8")
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid JSON contract: {exc}") from exc

    contract_header = stripped.lower().find("## contract")
    if contract_header != -1:
        block = stripped[contract_header:]
        fence = block.find("```json")
        if fence != -1:
            content_start = fence + 7
            end = block.find("```", content_start)
            if end != -1:
                try:
                    return json.loads(block[content_start:end].strip())
                except json.JSONDecodeError as exc:
                    raise ContractError(f"invalid JSON contract block: {exc}") from exc

    raise ContractError("contract file must be JSON or contain a ## Contract JSON block")
