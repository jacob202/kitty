#!/usr/bin/env python3
"""Repeat a fixed set of Kitty fault scenarios and emit an exact-SHA receipt."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.reliability_metrics import summarize_repetitions  # noqa: E402

MAX_REPETITIONS = 20
RUN_TIMEOUT_SECONDS = 120
FIXED_SCENARIOS = (
    "tests/test_mcp_tool_bridge.py::test_timeout_reaps_child_before_returning_error",
    "tests/test_mcp_tool_bridge.py::test_cooldown_allows_one_probe_and_success_closes_circuit",
    "tests/test_context_assembler.py::test_context_failures_create_sanitized_model_visible_degradation_receipt",
    "tests/test_health_surface.py::test_mcp_tool_health_degrades_on_open_circuit_without_claiming_remote_probe",
)


def _bounded_repetitions(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("repetitions must be an integer") from exc
    if not 1 <= parsed <= MAX_REPETITIONS:
        raise argparse.ArgumentTypeError(
            f"repetitions must be between 1 and {MAX_REPETITIONS}"
        )
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="repeat Kitty's fixed reliability fault scenarios"
    )
    parser.add_argument("--repetitions", type=_bounded_repetitions, default=5)
    parser.add_argument("--json-out", type=Path)
    return parser


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    head = result.stdout.strip()
    if not head:
        raise RuntimeError("git rev-parse returned an empty HEAD")
    return head


def _atomic_write_json(path: Path, payload: dict) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def run_gate(repetitions: int, *, json_out: Path | None = None) -> dict:
    if not 1 <= repetitions <= MAX_REPETITIONS:
        raise ValueError(f"repetitions must be between 1 and {MAX_REPETITIONS}")

    start_head = _git_head()
    runs: list[dict] = []
    command = [sys.executable, "-m", "pytest", *FIXED_SCENARIOS, "-q", "--tb=short"]
    for _index in range(repetitions):
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
            )
            exit_code = int(result.returncode)
            stdout_tail = getattr(result, "stdout", "")[-2000:]
            stderr_tail = getattr(result, "stderr", "")[-2000:]
        except subprocess.TimeoutExpired:
            exit_code = 124
            stdout_tail = ""
            stderr_tail = (
                f"reliability repetition timed out after {RUN_TIMEOUT_SECONDS}s"
            )
        elapsed_ms = (time.monotonic() - started) * 1000
        runs.append(
            {
                "exit_code": exit_code,
                "duration_ms": elapsed_ms,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            }
        )

    end_head = _git_head()
    receipt = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **summarize_repetitions(
            runs,
            head_sha=start_head,
            scenario_ids=FIXED_SCENARIOS,
        ),
        "end_head_sha": end_head,
        "head_unchanged": start_head == end_head,
    }
    if not receipt["head_unchanged"]:
        receipt["all_passed"] = False
    if json_out is not None:
        _atomic_write_json(json_out, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    receipt = run_gate(args.repetitions, json_out=args.json_out)
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0 if receipt["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
