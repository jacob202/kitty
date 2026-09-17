#!/usr/bin/env python3
"""Serialize Kitty's heavy local gates across worktrees and lanes.

Concurrent pre-push gates thrash this host: several worktrees running full
coverage suites at once turned a six-minute gate into fifteen-plus minutes of
swap-bound noise and starved every other process on the machine. This wrapper
takes one machine-level exclusive lock before running its command, prints who
holds the lock while waiting, and releases on exit.

The lock file must be a regular file that is not a symlink; anything else
degrades to a loud unlocked run rather than writing through the path.

Usage:
    gate_lock.py -- <command> [args...]

Environment:
    KITTY_GATE_LOCK_PATH     lock file (default: <tmpdir>/kitty-gate.lock)
    KITTY_GATE_LOCK_TIMEOUT  seconds to wait before proceeding without the lock
                             (default 1800; 0 waits forever)
"""

from __future__ import annotations

import errno
import fcntl
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import IO, Optional

DEFAULT_TIMEOUT_SECONDS = 1800.0
RETRY_SECONDS = 5.0
CONTENTION_ERRNOS = (errno.EAGAIN, errno.EACCES)


def _lock_path() -> Path:
    override = os.environ.get("KITTY_GATE_LOCK_PATH")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "kitty-gate.lock"


def _open_lock(path: Path) -> Optional[IO[str]]:
    """Open the lock file without following symlinks; None means run unlocked."""
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        print(f"gate lock: unavailable ({exc}) — running without it", file=sys.stderr)
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            print("gate lock: not a regular file — running without it", file=sys.stderr)
            return None
        return os.fdopen(descriptor, "r+")
    except OSError as exc:
        os.close(descriptor)
        print(f"gate lock: unavailable ({exc}) — running without it", file=sys.stderr)
        return None


def _holder(handle: IO[str]) -> str:
    try:
        handle.seek(0)
        pid = handle.read().strip()
    except OSError:
        pid = ""
    return pid or "unknown"


def _acquire(handle: IO[str], timeout: float) -> bool:
    """Take the lock, waiting out contention; False means run unlocked."""
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as exc:
        if exc.errno not in CONTENTION_ERRNOS:
            print(f"gate lock: flock unavailable ({exc}) — running without it", file=sys.stderr)
            return False
    print(
        f"gate lock: held by PID {_holder(handle)} — waiting, so full suites do not thrash",
        file=sys.stderr,
    )
    started = time.monotonic()
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(f"gate lock: acquired after {time.monotonic() - started:.0f}s", file=sys.stderr)
            return True
        except OSError as exc:
            if exc.errno not in CONTENTION_ERRNOS:
                print(
                    f"gate lock: flock unavailable ({exc}) — running without it",
                    file=sys.stderr,
                )
                return False
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
    handle = _open_lock(_lock_path())
    if handle is None:
        return subprocess.call(command)
    with handle:
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
                # Release the lock but leave the recorded holder in place:
                # clearing it after LOCK_UN races the next holder's PID write
                # and would make queued waiters report "unknown".
                try:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
