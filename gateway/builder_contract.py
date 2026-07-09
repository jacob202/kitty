"""Builder contract — validate and run Ideal-State-Criteria (ISC) checks.

A contract is a goal + a list of binary success criteria + optional
validation commands. This module validates a contract's structure and
optionally runs it against the existing ISA-lite machinery in
:mod:`gateway.builder`.

Layer 1A: contract validate is safe, read-only coordination.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from gateway import builder as builder_core

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
