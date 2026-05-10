#!/usr/bin/env python3
"""Run phase eval suites and print a scorecard."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

EVAL_FILES = [
    "evals/test_memory_recall.py",
    "evals/test_knowledge_recall.py",
    "evals/test_context_injection.py",
]


def _parse_counts(output: str) -> tuple[int, int]:
    passed = 0
    failed = 0
    if match := re.search(r"(\d+)\s+passed", output):
        passed = int(match.group(1))
    if match := re.search(r"(\d+)\s+failed", output):
        failed = int(match.group(1))
    return passed, failed


def run_evals() -> int:
    root = Path(__file__).resolve().parent.parent
    pytest_bin = root / "venv" / "bin" / "pytest"

    total_passed = 0
    total_failed = 0

    for eval_file in EVAL_FILES:
        run = subprocess.run(
            [str(pytest_bin), eval_file, "-q", "--tb=short"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (run.stdout or "") + "\n" + (run.stderr or "")
        passed, failed = _parse_counts(output)
        total_passed += passed
        total_failed += failed
        status = "✓" if run.returncode == 0 else "✗"
        print(f"  {status} {eval_file} - {passed} passed, {failed} failed")
        if run.returncode != 0:
            tail = "\n".join([line for line in output.splitlines() if line.strip()][-12:])
            if tail:
                print(tail)

    total = total_passed + total_failed
    pct = round((total_passed / total) * 100) if total else 0
    print(f"\nEval score: {total_passed}/{total} ({pct}%)")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_evals())
