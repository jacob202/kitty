"""Eval Runner — lightweight before/after quality measurement.

Public API:
  run_smoke() -> dict           Run the 5-gate smoke suite
  compare(before, after) -> dict   Compare two eval results
  run_and_compare(target) -> dict  Run tests, compare with baseline
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.eval_runner")

EVAL_LOG = DATA_DIR / "eval_history.jsonl"

SMOKE_GATES = [
    {
        "name": "chat_works",
        "description": "Ask who am I — responds in character",
        "test_file": "tests/test_context_injection.py",
    },
    {
        "name": "model_routing",
        "description": "Routes to correct model for domain",
        "test_file": "tests/test_domain_router.py",
    },
    {
        "name": "memory_recall",
        "description": "Facts stored and retrieved correctly",
        "test_file": "tests/test_memory.py",
    },
    {
        "name": "document_retrieval",
        "description": "Knowledge search returns relevant results",
        "test_file": "tests/test_knowledge.py",
    },
    {
        "name": "morning_brief",
        "description": "Brief generates without error",
        "test_file": "tests/test_brief.py",
    },
]


async def run_smoke() -> dict:
    """Run the 5-gate smoke eval suite. Returns results per gate."""
    results = {}
    total_passed = 0
    total_failed = 0

    for gate in SMOKE_GATES:
        test_file = gate["test_file"]
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3.12", "-m", "pytest", test_file, "-q", "--tb=line",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            passed = proc.returncode == 0
            if passed:
                total_passed += 1
            else:
                total_failed += 1

            results[gate["name"]] = {
                "description": gate["description"],
                "passed": passed,
                "output": stdout.decode()[:500],
            }
        except Exception as e:
            total_failed += 1
            results[gate["name"]] = {
                "description": gate["description"],
                "passed": False,
                "error": str(e),
            }

    record = {
        "ts": time.time(),
        "total": len(SMOKE_GATES),
        "passed": total_passed,
        "failed": total_failed,
        "gates": results,
    }
    _save_record(record)
    return record


def compare(before: dict, after: dict) -> dict:
    """Compare two eval result dicts, return delta."""
    b_passed = before.get("passed", 0)
    a_passed = after.get("passed", 0)
    delta = a_passed - b_passed
    status = "improved" if delta > 0 else "regressed" if delta < 0 else "unchanged"

    return {
        "before_passed": b_passed,
        "after_passed": a_passed,
        "delta": delta,
        "status": status,
        "total_gates": before.get("total", len(SMOKE_GATES)),
    }


async def run_and_compare(target_dir: Optional[str] = None) -> dict:
    """Run smoke suite, compare with last recorded baseline."""
    # Get baseline from last log
    baseline = _get_last_record()
    current = await run_smoke()

    result = {"current": current}
    if baseline:
        result["baseline"] = {k: v for k, v in baseline.items() if k not in ("ts",)}
        result["comparison"] = compare(baseline, current)
    else:
        result["comparison"] = {"status": "no_baseline", "note": "This is the first recorded eval run"}

    return result


def _save_record(record: dict) -> None:
    EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _get_last_record() -> dict | None:
    if not EVAL_LOG.exists():
        return None
    try:
        lines = EVAL_LOG.read_text().strip().split("\n")
        if lines:
            return json.loads(lines[-1])
    except Exception:
        logger.exception("Failed to read eval log %s", EVAL_LOG)
    return None
