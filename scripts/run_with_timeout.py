#!/usr/bin/env python3
"""Run a command with a hard timeout and no orphaned descendants."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path


_MEANINGFUL_EVENT_TYPES = {"text", "tool_use", "reasoning", "step_finish"}


def _stop_group(proc: subprocess.Popen[bytes], sig: signal.Signals) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError):
        # The group can disappear between poll() and killpg() on macOS. EPERM
        # is also observed for that race; wait() below remains authoritative.
        pass


def _valid_json(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or payload.get("contract_version") != 1:
        return False
    return payload.get("status") in {"completed", "failed"} or payload.get("verdict") in {
        "approve",
        "request_changes",
        "reject",
    }


def _stop_and_wait(proc: subprocess.Popen[bytes]) -> None:
    _stop_group(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=1)
        return
    except subprocess.TimeoutExpired:
        pass
    _stop_group(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        # Avoid turning a cleanup anomaly into an unbounded Builder hang.
        pass


def _parse_args() -> tuple[float, Path | None, bool, float | None, list[str]]:
    if len(sys.argv) < 3:
        raise SystemExit(
            "usage: run_with_timeout.py SECONDS [--success-json PATH] "
            "[--json-events] [--startup-timeout SECONDS] COMMAND [ARG ...]"
        )
    timeout = float(sys.argv[1])
    if timeout <= 0:
        raise SystemExit("timeout must be positive")

    success_json: Path | None = None
    json_events = False
    startup_timeout: float | None = None
    index = 2
    while index < len(sys.argv):
        arg = sys.argv[index]
        if arg == "--success-json":
            if index + 1 >= len(sys.argv):
                raise SystemExit("--success-json requires PATH")
            success_json = Path(sys.argv[index + 1])
            index += 2
        elif arg == "--json-events":
            json_events = True
            index += 1
        elif arg == "--startup-timeout":
            if index + 1 >= len(sys.argv):
                raise SystemExit("--startup-timeout requires SECONDS")
            startup_timeout = float(sys.argv[index + 1])
            if startup_timeout <= 0:
                raise SystemExit("startup timeout must be positive")
            index += 2
        else:
            break

    if index >= len(sys.argv):
        raise SystemExit("command is required")
    if startup_timeout is not None and not json_events:
        raise SystemExit("--startup-timeout requires --json-events")
    return timeout, success_json, json_events, startup_timeout, sys.argv[index:]


def _consume_json_output(data: bytes, buffer: bytes) -> tuple[bytes, bool, bool]:
    """Forward raw JSONL and report (new_buffer, activity, provider_error)."""
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
    buffer += data
    activity = False
    provider_error = False
    while b"\n" in buffer:
        raw, buffer = buffer.split(b"\n", 1)
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "error":
            provider_error = True
        elif event_type in _MEANINGFUL_EVENT_TYPES:
            activity = True
    return buffer, activity, provider_error


def main() -> int:
    timeout, success_json, json_events, startup_timeout, command = _parse_args()
    proc = subprocess.Popen(
        command,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if json_events else None,
    )

    def forward(signum: int, _frame: object) -> None:
        _stop_and_wait(proc)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)

    deadline = time.monotonic() + timeout
    startup_deadline = (
        time.monotonic() + startup_timeout if startup_timeout is not None else None
    )
    selector: selectors.BaseSelector | None = None
    output_buffer = b""
    if json_events:
        assert proc.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)

    def consume_events(wait_for: float) -> int | None:
        nonlocal output_buffer, startup_deadline
        if selector is None:
            return None
        for key, _mask in selector.select(wait_for):
            data = os.read(key.fileobj.fileno(), 65536)
            if not data:
                try:
                    selector.unregister(key.fileobj)
                except Exception:
                    pass
                continue
            output_buffer, activity, provider_error = _consume_json_output(
                data, output_buffer
            )
            if activity:
                startup_deadline = None
            if provider_error:
                if success_json is not None and _valid_json(success_json):
                    _stop_and_wait(proc)
                    return 0
                _stop_and_wait(proc)
                return 75
        return None

    try:
        while True:
            if success_json is not None and _valid_json(success_json):
                _stop_and_wait(proc)
                return 0

            returncode = proc.poll()
            if returncode is not None:
                if json_events and proc.stdout is not None:
                    tail = proc.stdout.read()
                    if tail:
                        output_buffer, activity, provider_error = _consume_json_output(
                            tail, output_buffer
                        )
                        if activity:
                            startup_deadline = None
                        if provider_error and not (
                            success_json is not None and _valid_json(success_json)
                        ):
                            return 75
                return returncode

            now = time.monotonic()
            if now >= deadline:
                _stop_and_wait(proc)
                return 124
            if startup_deadline is not None and now >= startup_deadline:
                # A busy host can wake us just after the deadline even though
                # meaningful provider activity was already queued. Drain any
                # immediately-readable JSON before declaring startup silence.
                event_result = consume_events(0)
                if event_result is not None:
                    return event_result
                if startup_deadline is not None:
                    _stop_and_wait(proc)
                    return 124
                now = time.monotonic()

            wait_for = min(0.1, max(0.0, deadline - now))
            if startup_deadline is not None:
                wait_for = min(wait_for, max(0.0, startup_deadline - now))

            if selector is None:
                time.sleep(wait_for)
                continue

            event_result = consume_events(wait_for)
            if event_result is not None:
                return event_result
    finally:
        if selector is not None:
            selector.close()


if __name__ == "__main__":
    raise SystemExit(main())
