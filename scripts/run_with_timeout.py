#!/usr/bin/env python3
"""Run a command with a hard timeout and no orphaned descendants."""

from __future__ import annotations

import os
import signal
import subprocess
import sys


def _stop_group(proc: subprocess.Popen[bytes], sig: signal.Signals) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        pass


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit("usage: run_with_timeout.py SECONDS COMMAND [ARG ...]")
    timeout = float(sys.argv[1])
    if timeout <= 0:
        raise SystemExit("timeout must be positive")
    proc = subprocess.Popen(sys.argv[2:], start_new_session=True, stdin=subprocess.DEVNULL)

    def forward(signum: int, _frame: object) -> None:
        _stop_group(proc, signal.Signals(signum))
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _stop_group(proc, signal.SIGKILL)
            proc.wait()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_group(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _stop_group(proc, signal.SIGKILL)
            proc.wait()
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
