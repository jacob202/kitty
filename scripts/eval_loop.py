#!/opt/homebrew/bin/python3.12
"""Self-improving eval loop for Kitty.

Runs pytest, hits /api/eval/run, checks for regressions, and logs
results to docs/iteration_log.md and eval_snapshots/.

Usage:
    python3.12 scripts/eval_loop.py [--max-attempts N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FLASK_PORT = 5098
FLASK_STARTUP_WAIT = 30  # max seconds to wait for Flask to accept connections
ARTIFACT_DIR = ROOT / "evals" / "artifacts"
SNAPSHOT_DIR = ROOT / "eval_snapshots"
ITERATION_LOG = ROOT / "docs" / "iteration_log.md"
PYTEST_CMD = [
    "venv/bin/python", "-m", "pytest",
    "tests/", "-q", "--tb=short",
]


def _now_ts() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _header(text: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n  {text}\n{bar}")


def _step(label: str, value: str = "") -> None:
    print(f"  [{label}] {value}" if value else f"  [{label}]")


def run_pytest() -> tuple[bool, str]:
    _header("Step 1: pytest")
    result = subprocess.run(PYTEST_CMD, capture_output=True, text=True, cwd=str(ROOT))
    print(result.stdout + result.stderr)
    passed = result.returncode == 0
    _step("pytest", "PASSED" if passed else "FAILED")
    return passed, result.stdout + result.stderr


def start_flask() -> subprocess.Popen:
    import os
    env = {**os.environ, "KITTY_PORT": str(FLASK_PORT), "KITTY_HOST": "127.0.0.1", "FLASK_DEBUG": "0"}
    proc = subprocess.Popen(
        ["venv/bin/python", "web.py"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    _step("Flask PID", str(proc.pid))
    # Poll until Flask accepts connections instead of fixed sleep
    import socket
    deadline = time.time() + FLASK_STARTUP_WAIT
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", FLASK_PORT), timeout=1):
                break
        except OSError:
            time.sleep(0.5)
    else:
        _step("WARNING", "Flask did not accept connections within timeout — continuing anyway")
    return proc


def call_eval_route() -> dict:
    import urllib.error
    import urllib.request
    url = f"http://127.0.0.1:{FLASK_PORT}/api/eval/run"
    payload = json.dumps({"suite": "smoke"}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        data: dict = {}
        try:
            data = json.loads(exc.read().decode())
        except Exception:
            pass
        data["__http_status"] = exc.code
        return data


def save_snapshot(attempt: int, ts: str, data: dict) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"attempt_{ts}.json"
    path.write_text(json.dumps({"attempt": attempt, "timestamp": ts, **data}, indent=2))
    return path


def check_regression(current_scores: dict[str, float]) -> dict:
    from evals.compare_runs import detect_regression
    return detect_regression(ARTIFACT_DIR, current_scores)


def append_log(attempt: int, score: str, status: str, change: str = "eval loop verification") -> None:
    ITERATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Integration Iteration Log\n"
        "| Attempt | Change | Eval Score | Status |\n"
        "|---------|--------|------------|--------|\n"
    )
    row = f"| {attempt} | {change} | {score} | {status} |\n"
    if ITERATION_LOG.exists():
        content = ITERATION_LOG.read_text()
        ITERATION_LOG.write_text(content.rstrip("\n") + "\n" + row)
    else:
        ITERATION_LOG.write_text(header + row)


def run_loop(max_attempts: int) -> int:
    for attempt in range(1, max_attempts + 1):
        ts = _now_ts()
        _header(f"Iteration {attempt}/{max_attempts}  [{ts}]")

        # Step 1: pytest
        passed, _ = run_pytest()
        if not passed:
            save_snapshot(attempt, ts, {"pytest": "FAILED"})
            append_log(attempt, "—", "FAILED (pytest)")
            print("\nFAIL: pytest failed — not pushing broken code")
            return 1

        # Step 2: start Flask + hit eval route
        _header("Step 2: eval route")
        flask_proc = start_flask()
        eval_data: dict = {}
        score_rate: float | None = None

        try:
            eval_data = call_eval_route()
            _step("response", json.dumps(eval_data))

            if eval_data.get("__http_status") == 422:
                save_snapshot(attempt, ts, {"pytest": "PASSED", "eval": eval_data})
                append_log(attempt, "baseline fail", "FAILED (422)")
                print(f"\nFAIL: eval baseline failed: {eval_data.get('error')}")
                return 1

            score_info = eval_data.get("score", {})
            score_rate = score_info.get("rate")
            _step("score", f"{score_rate} ({score_info.get('passed')}/{score_info.get('total')})")

        except Exception as exc:
            _step("ERROR", f"eval route unreachable: {exc}")
            save_snapshot(attempt, ts, {"pytest": "PASSED", "eval": {"error": str(exc)}})
            append_log(attempt, "—", "FAILED (unreachable)")
            return 1
        finally:
            flask_proc.terminate()
            try:
                flask_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                flask_proc.kill()
            _step("Flask", "stopped")

        # Step 3: regression check
        _header("Step 3: regression detection")
        curr = {"smoke": score_rate if score_rate is not None else 0.0}
        reg = check_regression(curr)
        _step("result", json.dumps(reg))

        snap = save_snapshot(attempt, ts, {"pytest": "PASSED", "eval": eval_data, "regression": reg})
        _step("snapshot", str(snap))

        score_str = f"{score_rate:.2%}" if score_rate is not None else "—"

        if reg.get("is_regression"):
            delta = reg.get("delta", 0.0)
            print(f"\nWARNING: REGRESSION — score dropped {abs(delta):.2%} "
                  f"(prev={reg.get('prev_rate')}, curr={score_rate})")
            append_log(attempt, score_str, "REGRESSION")
            return 1

        reason = reg.get("reason", "")
        print(f"\nPASS: no regression{f' ({reason})' if reason else ''} — score={score_str}")
        append_log(attempt, score_str, "PASS")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Kitty self-improving eval loop")
    parser.add_argument("--max-attempts", type=int, default=1, metavar="N")
    args = parser.parse_args()
    sys.exit(run_loop(args.max_attempts))


if __name__ == "__main__":
    main()
