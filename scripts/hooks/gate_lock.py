#!/usr/bin/env python3
"""Serialize Kitty's heavy local gates across worktrees and lanes.

Concurrent pre-push gates thrash this host: several worktrees running full
coverage suites at once turned a six-minute gate into fifteen-plus minutes of
swap-bound noise and starved every other process on the machine. This wrapper
takes one machine-level exclusive lock before running its command, prints who
holds the lock while waiting, and releases on exit.

Usage:
    gate_lock.py -- <command> [args...]

Environment:
    KITTY_GATE_LOCK_PATH     lock file (default: <tmpdir>/kitty-gate.lock)
    KITTY_GATE_LOCK_TIMEOUT  seconds to wait before proceeding without the lock
                             (default 1800; 0 waits forever)
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 1800.0
RETRY_SECONDS = 5.0


def _lock_path() -> Path:
    override = os.environ.get("KITTY_GATE_LOCK_PATH")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "kitty-gate.lock"


def _holder(handle) -> str:
    try:
        handle.seek(0)
        pid = handle.read().strip()
    except OSError:
        pid = ""
    return pid or "unknown"


def _acquire(handle, timeout: float) -> bool:
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        pass
    print(
        f"gate lock: held by PID {_holder(handle)} — waiting, so full suites do not thrash",
        file=sys.stderr,
    )
    started = time.monotonic()
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            waited = time.monotonic() - started
            print(f"gate lock: acquired after {waited:.0f}s", file=sys.stderr)
            return True
        except OSError:
            if timeout > 0 and time.monotonic() - started > timeout:
                print(
                    f"gate lock: still held after {timeout:.0f}s — running without it",
                    file=sys.stderr,
                )
                return False
            time.sleep(RETRY_SECONDS)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] != "--":
        print(f"usage: {Path(sys.argv[0]).name} -- <command> [args...]", file=sys.stderr)
        return 2
    command = argv[1:]
    timeout = float(os.environ.get("KITTY_GATE_LOCK_TIMEOUT") or DEFAULT_TIMEOUT_SECONDS)
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        holding = _acquire(handle, timeout)
        if holding:
            handle.seek(0)
            handle.truncate()
            handle.write(f"{os.getpid()}\n")
            handle.flush()
        try:
            return subprocess.call(command)
        finally:
            if holding:
                try:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                except OSError:
                    pass
                handle.seek(0)
                handle.truncate()
                handle.flush()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
